"""
Retrieval of pickle programs out of model weight files.

The problem this solves: a checkpoint can be tens of gigabytes, but the part
that decides whether loading it is dangerous is the pickle program inside,
which is measured in kilobytes. Modern `torch.save()` writes a zip archive
whose `data.pkl` member holds that program while the tensor storages sit in
separate entries — so with HTTP range requests we can read the zip's central
directory from the tail of the file, seek to the one member we care about, and
pull a few KB instead of the whole checkpoint.

Everything here is byte retrieval. No pickle is ever loaded — see
scanner/pickle_scanner.py for why that distinction is the entire point.
"""

import asyncio
import logging
import zipfile

import httpx

from ..scanner.pickle_scanner import (
    PickleStream,
    iter_pickle_streams,
    pickle_members_from_zip,
)

logger = logging.getLogger(__name__)

# Enough to identify the format and to hold a small bare pickle outright.
PROBE_BYTES = 32 * 1024
# How much of an oversized *bare* pickle to read. Legacy `torch.save()` (pre
# 1.6) writes the pickle program first and the raw tensor storages after it,
# so the opcodes — including any payload's — sit near the front. The program
# scales with the number of tensors, not their size; 2 MB covers very large
# state dicts while still skipping gigabytes of weights.
PICKLE_PREFIX_BYTES = 2 * 1024 * 1024
# Ceiling on a whole-artifact download when range requests are unavailable.
MAX_WHOLE_FILE_BYTES = 16 * 1024 * 1024
# Ceiling on one decompressed pickle member.
MAX_MEMBER_BYTES = 8 * 1024 * 1024
# Ceiling on total bytes pulled through a single range-backed file object,
# so a hostile archive cannot walk us through the whole checkpoint.
MAX_RANGE_BUDGET = 24 * 1024 * 1024
# How many weight artifacts to inspect per scan.
MAX_ARTIFACTS = 12

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class HttpRangeFile:
    """A minimal seekable file over HTTP range requests, for `zipfile`.

    Implements only what ZipFile touches: read, seek, tell, seekable. Reads
    are counted against a budget so a crafted archive that seeks endlessly
    still cannot make us download the whole file.
    """

    def __init__(self, client: httpx.Client, url: str, size: int,
                 budget: int = MAX_RANGE_BUDGET):
        self._client = client
        self._url = url
        self._size = size
        self._pos = 0
        self._budget = budget

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._pos = offset
        elif whence == 1:
            self._pos += offset
        elif whence == 2:
            self._pos = self._size + offset
        self._pos = max(0, min(self._pos, self._size))
        return self._pos

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self._size - self._pos
        n = min(n, self._size - self._pos)
        if n <= 0:
            return b""
        if n > self._budget:
            raise IOError("range read budget exhausted")

        start, end = self._pos, self._pos + n - 1
        resp = self._client.get(self._url, headers={"Range": f"bytes={start}-{end}"})
        if resp.status_code not in (200, 206):
            raise IOError(f"range request failed with {resp.status_code}")
        # A server that ignores Range answers 200 with the whole body; slice
        # out the window we asked for rather than trusting the offset.
        data = resp.content[start:start + n] if resp.status_code == 200 else resp.content
        self._budget -= len(data)
        self._pos += len(data)
        return data

    def close(self) -> None:
        pass


def _probe(client: httpx.Client, url: str) -> tuple[bytes, bool]:
    """Fetch the first PROBE_BYTES. Returns (prefix, server_supports_ranges)."""
    resp = client.get(url, headers={"Range": f"bytes=0-{PROBE_BYTES - 1}"})
    resp.raise_for_status()
    if resp.status_code == 206:
        return resp.content, True
    return resp.content[:PROBE_BYTES], False


def extract_streams(client: httpx.Client, url: str, path: str, size: int) -> list[PickleStream]:
    """Retrieve the pickle programs in one artifact, using as few bytes as possible."""
    try:
        prefix, ranges_ok = _probe(client, url)
    except Exception as exc:
        logger.warning("could not probe %s: %s", path, exc)
        return []

    if not prefix:
        return []

    is_zip = prefix[:4] == b"PK\x03\x04"

    # Torch archive, range requests available: read the central directory
    # from the tail and pull only the data.pkl member.
    if is_zip and ranges_ok and size > len(prefix):
        try:
            handle = HttpRangeFile(client, url, size)
            with zipfile.ZipFile(handle) as zf:
                return list(pickle_members_from_zip(zf, path, MAX_MEMBER_BYTES))
        except Exception as exc:
            logger.warning("range read of %s failed, falling back: %s", path, exc)

    # Small enough to hold outright.
    if size and size <= MAX_WHOLE_FILE_BYTES:
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return list(iter_pickle_streams(resp.content, path))
        except Exception as exc:
            logger.warning("could not download %s: %s", path, exc)
            return []

    # Oversized and not a zip — a legacy torch checkpoint. Pull a bigger
    # prefix so the whole pickle program is likely covered even though the
    # tensor data after it is not.
    if ranges_ok:
        try:
            resp = client.get(url, headers={"Range": f"bytes=0-{PICKLE_PREFIX_BYTES - 1}"})
            if resp.status_code in (200, 206):
                prefix = resp.content[:PICKLE_PREFIX_BYTES]
        except Exception as exc:
            logger.warning("prefix read of %s failed: %s", path, exc)

    # We saw only the front of the file. `truncated` records that, so a parse
    # failure is not blamed on the file and the caller can say the scan was
    # partial rather than implying the whole artifact came back clean.
    return list(iter_pickle_streams(prefix, path, truncated=True))


def _fetch_one_sync(url: str, path: str, size: int) -> list[PickleStream]:
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
        return extract_streams(client, url, path, size)


async def fetch_pickle_streams(candidates: list[dict]) -> list[PickleStream]:
    """Retrieve pickle programs for the given artifacts.

    `candidates` are dicts of {"path", "url", "size"}. Runs the blocking
    zipfile work in threads because ZipFile needs a synchronous seekable
    file, and there is no async equivalent worth writing here.
    """
    selected = candidates[:MAX_ARTIFACTS]
    if not selected:
        return []

    results = await asyncio.gather(
        *[
            asyncio.to_thread(_fetch_one_sync, c["url"], c["path"], c.get("size") or 0)
            for c in selected
        ],
        return_exceptions=True,
    )

    streams: list[PickleStream] = []
    for candidate, result in zip(selected, results):
        if isinstance(result, BaseException):
            logger.warning("pickle fetch failed for %s: %s", candidate["path"], result)
            continue
        streams.extend(result)
    return streams
