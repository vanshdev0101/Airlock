import asyncio
import logging
from datetime import datetime, timezone

import httpx

from ..config import get_settings
from ..core.exceptions import FetchError
from ..core.text import levenshtein
from ..scanner.pickle_scanner import PICKLE_WEIGHT_EXTENSIONS
from ..scanner.scan import AccountInfo
from .pickle_fetch import fetch_pickle_streams

logger = logging.getLogger(__name__)
settings = get_settings()

SCANNABLE_EXTENSIONS = {
    ".py", ".sh", ".bat", ".ps1", ".js", ".ts",
    ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".md", ".txt", ".json",
}

MAX_FILE_BYTES = settings.max_file_size_kb * 1024
_SEMAPHORE = asyncio.Semaphore(10)

# ── Scan budget priority ──────────────────────────────────────────────────────
# The file budget used to be "whatever the API listed first", which is not a
# budget so much as an accident: a payload in file 101 was invisible while the
# 100 slots went to translation files. Rank by where malicious code actually
# lives, so truncation drops the least interesting files instead of arbitrary
# ones. Lower number = looked at first.

# Executed on install or import — the classic drop point for a payload.
_CRITICAL_NAMES = {
    "setup.py", "setup.cfg", "conftest.py", "__init__.py", "manage.py",
    "install.sh", "install.py", "postinstall.js", "preinstall.js",
    "docker-entrypoint.sh", "entrypoint.sh", "run.sh", "start.sh",
}
# Declares what gets pulled in — the supply-chain surface.
_MANIFEST_NAMES = {
    "requirements.txt", "pyproject.toml", "package.json", "pipfile",
    "environment.yml", "environment.yaml", "setup.py",
}
# Enormous, machine-generated, and never where an attacker hides anything.
_LOCKFILE_NAMES = {
    "package-lock.json", "yarn.lock", "poetry.lock", "pnpm-lock.yaml",
    "pdm.lock", "uv.lock",
}
_EXECUTABLE_EXTENSIONS = {".sh", ".bat", ".ps1"}


def _scan_priority(path: str) -> tuple[int, int]:
    """Sort key for the file budget: (tier, directory depth)."""
    lower = path.lower().replace("\\", "/")
    name = lower.rsplit("/", 1)[-1]
    ext = ("." + name.rsplit(".", 1)[-1]) if "." in name else ""
    depth = lower.count("/")

    if name in _LOCKFILE_NAMES:
        tier = 8
    elif _is_test_or_docs_path(lower):
        tier = 7
    elif name in _CRITICAL_NAMES:
        tier = 0
    elif name in _MANIFEST_NAMES:
        tier = 1
    elif ext in _EXECUTABLE_EXTENSIONS:
        tier = 2
    elif ext == ".py":
        tier = 3
    elif ext in (".js", ".ts"):
        tier = 4
    elif ext in (".yaml", ".yml", ".toml", ".cfg", ".ini", ".json"):
        tier = 5
    else:  # .md, .txt — documentation, read last
        tier = 6

    return (tier, depth)


def _is_test_or_docs_path(lower_path: str) -> bool:
    parts = lower_path.split("/")
    return any(
        p in ("test", "tests", "docs", "doc", "examples", "example", "fixtures")
        for p in parts[:-1]
    ) or parts[-1].startswith("test_")


def _budgeted(file_list: list[str]) -> list[str]:
    """The files worth spending the scan budget on, best first."""
    scannable = [f for f in file_list if _ext_of(f) in SCANNABLE_EXTENSIONS]
    scannable.sort(key=_scan_priority)
    return scannable[: settings.max_files_per_scan]


def _ext_of(path: str) -> str:
    return ("." + path.rsplit(".", 1)[-1].lower()) if "." in path else ""


class RepoFetcher:

    def __init__(self):
        self.hf_base = "https://huggingface.co/api"
        self.gh_base = "https://api.github.com"
        self.gh_headers = {}
        if settings.github_token:
            self.gh_headers["Authorization"] = f"Bearer {settings.github_token}"

    def parse_url(self, url: str) -> dict:
        url = url.rstrip("/")
        if "huggingface.co" in url:
            parts = url.split("huggingface.co/")[-1].split("/")
            return {"platform": "huggingface", "owner": parts[0],
                    "repo": parts[1] if len(parts) > 1 else ""}
        if "github.com" in url:
            parts = url.split("github.com/")[-1].split("/")
            return {"platform": "github", "owner": parts[0],
                    "repo": parts[1] if len(parts) > 1 else ""}
        raise ValueError(f"Unsupported URL: {url}")

    async def fetch_repo(self, url: str) -> dict:
        info = self.parse_url(url)
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            if info["platform"] == "huggingface":
                return await self._fetch_hf(client, info)
            return await self._fetch_github(client, info)

    async def _fetch_hf(self, client: httpx.AsyncClient, info: dict) -> dict:
        owner, repo = info["owner"], info["repo"]
        repo_id = f"{owner}/{repo}"

        # Try model → dataset → space in order. One request per type: the
        # blobs=True response carries both the metadata and the `siblings`
        # file list, so there is no need to fetch the endpoint twice.
        meta = None
        for rtype in ("models", "datasets", "spaces"):
            resp = await client.get(
                f"{self.hf_base}/{rtype}/{repo_id}",
                params={"blobs": True},
            )
            if resp.status_code == 200:
                meta = resp.json()
                break
            if resp.status_code == 429:
                raise FetchError("Hugging Face rate limit hit. Wait a minute and try again.")
            # 401/403 is not conclusive: Hugging Face returns it for gated,
            # private *and* nonexistent repos so as not to leak existence.
            # Keep trying the other repo types before giving up.

        # A repo we cannot read is not a repo we can vouch for. Never fall
        # through to an empty file set — that would score a clean 100.
        if meta is None:
            raise FetchError(
                f"Could not read '{repo_id}' on Hugging Face — it does not exist, "
                "or it is private/gated. RepoGuard can only scan public repos."
            )

        siblings = meta.get("siblings", [])
        file_list = [s["rfilename"] for s in siblings]
        sizes = {s["rfilename"]: s.get("size") or 0 for s in siblings}
        scannable = _budgeted(file_list)

        # Always try README
        for readme in ["README.md", "readme.md", "MODEL_CARD.md"]:
            if readme not in scannable:
                scannable.append(readme)

        def resolve(f: str) -> str:
            return f"https://huggingface.co/{repo_id}/resolve/main/{f}"

        files_content = await self._download_many(
            client, {f: resolve(f) for f in scannable}
        )
        self._require_readable_files(files_content, repo_id)

        pickle_streams = await fetch_pickle_streams(
            self._pickle_candidates(file_list, sizes, resolve)
        )

        author_info = await self._fetch_hf_author(client, owner)
        return {
            "repo_name": repo_id, "platform": "huggingface",
            "account_info": self._build_account_info(owner, author_info),
            "files": files_content, "raw_metadata": meta,
            "all_files": file_list, "pickle_streams": pickle_streams,
            "downloads": meta.get("downloads", 0), "likes": meta.get("likes", 0),
        }

    async def _fetch_hf_author(self, client, owner):
        resp = await client.get(f"{self.hf_base}/users/{owner}/overview")
        return resp.json() if resp.status_code == 200 else {}

    async def _fetch_github(self, client: httpx.AsyncClient, info: dict) -> dict:
        owner, repo = info["owner"], info["repo"]

        meta_resp = await client.get(
            f"{self.gh_base}/repos/{owner}/{repo}", headers=self.gh_headers)
        self._raise_for_github(meta_resp, f"{owner}/{repo}")
        meta = meta_resp.json()

        tree_resp = await client.get(
            f"{self.gh_base}/repos/{owner}/{repo}/git/trees/HEAD",
            params={"recursive": "1"}, headers=self.gh_headers)
        self._raise_for_github(tree_resp, f"{owner}/{repo}")
        blobs = [i for i in tree_resp.json().get("tree", []) if i["type"] == "blob"]
        file_list = [i["path"] for i in blobs]
        sizes = {i["path"]: i.get("size") or 0 for i in blobs}

        scannable = _budgeted(file_list)
        base = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD"
        files_content = await self._download_many(client, {f: f"{base}/{f}" for f in scannable})
        self._require_readable_files(files_content, f"{owner}/{repo}")

        pickle_streams = await fetch_pickle_streams(
            self._pickle_candidates(file_list, sizes, lambda f: f"{base}/{f}")
        )

        user_resp = await client.get(f"{self.gh_base}/users/{owner}", headers=self.gh_headers)
        user_data = user_resp.json() if user_resp.status_code == 200 else {}

        return {
            "repo_name": f"{owner}/{repo}", "platform": "github",
            "account_info": self._build_account_info(owner, user_data, platform="github"),
            "files": files_content, "raw_metadata": meta,
            "all_files": file_list, "pickle_streams": pickle_streams,
            "downloads": meta.get("stargazers_count", 0),
            "likes": meta.get("watchers_count", 0),
        }

    def _pickle_candidates(self, file_list, sizes: dict, url_for) -> list[dict]:
        """Weight artifacts worth probing, biggest-signal first.

        Ordered smallest-first: a small pickle is cheap to read in full, and
        the tiny `data.pkl`-style files are where a hand-written payload
        usually lives.
        """
        candidates = [
            {"path": f, "url": url_for(f), "size": sizes.get(f, 0)}
            for f in file_list
            if self._ext(f) in PICKLE_WEIGHT_EXTENSIONS
        ]
        candidates.sort(key=lambda c: c["size"])
        return candidates

    def _raise_for_github(self, resp: httpx.Response, repo_id: str) -> None:
        """Turn a non-200 GitHub response into a FetchError with a usable message."""
        if resp.status_code == 200:
            return
        if resp.status_code == 404:
            raise FetchError(
                f"'{repo_id}' was not found on GitHub. "
                "Check the spelling and that the repo is public."
            )
        if resp.status_code == 403 and resp.headers.get("x-ratelimit-remaining") == "0":
            raise FetchError(
                "GitHub rate limit hit. Set GITHUB_TOKEN in .env to raise the limit, "
                "or wait a few minutes."
            )
        if resp.status_code in (401, 403):
            raise FetchError(
                f"'{repo_id}' is private — RepoGuard can only scan public repos."
            )
        raise FetchError(f"GitHub returned {resp.status_code} for '{repo_id}'.")

    def _require_readable_files(self, files: dict[str, str], repo_id: str) -> None:
        """A scan that read nothing proves nothing — refuse to score it as safe."""
        if not files:
            raise FetchError(
                f"No readable source files found in '{repo_id}'. "
                "RepoGuard cannot assess a repo it could not read."
            )

    async def _download_many(self, client, url_map: dict[str, str]) -> dict[str, str]:
        async def fetch_one(filename, url):
            async with _SEMAPHORE:
                return filename, await self._download_text(client, url)

        results = await asyncio.gather(
            *[fetch_one(f, u) for f, u in url_map.items()],
            return_exceptions=True
        )
        return {
            fname: content
            for r in results
            if not isinstance(r, Exception)
            for fname, content in [r]
            if content is not None
        }

    async def _download_text(self, client, url) -> str | None:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            if len(resp.content) > MAX_FILE_BYTES:
                return None
            return resp.text
        except Exception as e:
            logger.warning(f"Failed: {url}: {e}")
            return None

    def _build_account_info(self, username, data, platform="huggingface") -> AccountInfo:
        created_str = data.get("createdAt") or data.get("created_at", "")
        account_age_days = None
        if created_str:
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                account_age_days = (datetime.now(timezone.utc) - created).days
            except Exception:
                pass
        total_repos = data.get("numModels") or data.get("public_repos") or data.get("numRepos") or 0
        is_new = account_age_days is not None and account_age_days < 30
        is_typo, typo_target = self._check_typosquat(username)
        return AccountInfo(
            username=username, account_age_days=account_age_days, total_repos=total_repos,
            is_new_account=is_new, is_typosquat=is_typo, typosquat_target=typo_target,
        )

    def _check_typosquat(self, username):
        clean = username.lower().replace("-", "").replace("_", "")
        for trusted in settings.trusted_orgs:
            t = trusted.lower().replace("-", "").replace("_", "")
            if clean == t:
                return False, None
            dist = levenshtein(clean, t)
            if dist <= 2 and abs(len(clean) - len(t)) <= 3 and dist > 0:
                return True, trusted
        return False, None

    def _ext(self, path):
        return _ext_of(path)