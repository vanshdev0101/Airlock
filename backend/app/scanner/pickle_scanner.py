"""
Pickle opcode analysis.

A pickle file is a program, not data. Its opcode stream names callables and
instructs the interpreter to invoke them, which is why `torch.load()` on an
untrusted checkpoint is remote code execution with extra steps.

`pickletools.genops` walks that stream and *reports* each instruction without
running any of it. That is the whole basis of this module: nothing here calls
pickle.load, pickle.loads, or torch.load, and nothing here imports a module
named by the file being examined. We read the program; we never run it.

The signal we want is the GLOBAL opcode — "import this module, fetch this
attribute" — because a payload has to name its executor somewhere. A
state_dict has no legitimate reason to reference os.system.
"""

import io
import logging
import pickletools
import zipfile
from collections.abc import Iterator

from .scan import PatternMatch

logger = logging.getLogger(__name__)

# Opcodes that push a string; STACK_GLOBAL (protocol 4) takes its module and
# name from the stack rather than from its own argument, so we track these to
# resolve it.
_STRING_OPCODES = frozenset({
    "SHORT_BINUNICODE", "BINUNICODE", "BINUNICODE8", "UNICODE",
    "SHORT_BINSTRING", "BINSTRING", "STRING",
})

# Opcodes that name a callable.
_GLOBAL_OPCODES = frozenset({"GLOBAL", "STACK_GLOBAL", "INST"})

# Modules with no business inside serialised model weights. Any reference at
# all is treated as an exploit — `posix` and `nt` are included because
# posix.system *is* os.system and naming the backend directly is the oldest
# way around a naive os-only check.
_DANGEROUS_MODULES = frozenset({
    "os", "posix", "nt", "subprocess", "commands", "popen2",
    "socket", "shutil", "pty", "runpy", "ctypes", "cffi",
    "importlib", "imp", "multiprocessing", "webbrowser",
    "pdb", "bdb", "timeit", "platform", "getpass", "tempfile",
})

# Dangerous attributes inside modules that are otherwise legitimate.
_DANGEROUS_NAMES = {
    "builtins": {
        "eval", "exec", "execfile", "compile", "open", "input",
        "__import__", "getattr", "setattr", "delattr", "globals",
        "vars", "memoryview", "breakpoint",
    },
    "operator": {"attrgetter", "methodcaller", "itemgetter"},
    "functools": {"partial", "reduce"},
    "torch": {"load"},
    "torch.serialization": {"load"},
    "pickle": {"load", "loads", "Unpickler"},
    "sys": {"modules", "argv", "path", "exit", "settrace", "setprofile"},
    "codecs": {"decode", "open"},
    "base64": {"b64decode", "b64encode", "urlsafe_b64decode", "decodebytes"},
    "zlib": {"decompress"},
    "bz2": {"decompress"},
    "lzma": {"decompress"},
    "marshal": {"loads", "load"},
    "types": {"FunctionType", "CodeType", "ModuleType"},
}
# Python 2 spelling of builtins, same contents.
_DANGEROUS_NAMES["__builtin__"] = _DANGEROUS_NAMES["builtins"]

# Modules that routinely and legitimately appear in ML pickles. Anything
# outside this set is *reported* but not treated as an exploit — unknown is
# not the same as malicious, and a repo pickling its own classes is normal.
_EXPECTED_MODULE_PREFIXES = (
    "torch", "collections", "numpy", "_codecs", "copyreg", "copy_reg",
    "argparse", "datetime", "decimal", "fractions", "uuid", "pathlib",
    "enum", "typing", "re", "string", "math", "random", "itertools",
    "sklearn", "scipy", "pandas", "PIL", "safetensors",
    "transformers", "tokenizers", "sentencepiece", "tiktoken",
    "torchvision", "torchaudio", "timm", "einops", "omegaconf",
    "pytorch_lightning", "lightning", "peft", "accelerate", "diffusers",
    "fairseq", "gensim", "nltk", "spacy", "xgboost", "lightgbm", "catboost",
    "joblib", "cloudpickle",
)

# `_codecs.encode` is how numpy round-trips byte strings; it appears in a huge
# share of perfectly ordinary pickles and cannot execute anything on its own.
_ALWAYS_EXPECTED = frozenset({("_codecs", "encode"), ("codecs", "encode")})

# Ceilings so a hostile file cannot turn a scan into a denial of service.
MAX_OPCODES = 500_000
MAX_REPORTED_GLOBALS = 12


class PickleStream:
    """One pickle program extracted from a repository artifact.

    `path` is the repo file; `member` names the entry inside it when the
    artifact is a torch zip archive (`archive/data.pkl`) and is empty for a
    bare .pkl. `truncated` records that we only fetched a prefix, which makes
    a parse failure our fault rather than the file's.
    """

    def __init__(self, path: str, data: bytes, member: str = "", truncated: bool = False):
        self.path = path
        self.data = data
        self.member = member
        self.truncated = truncated

    @property
    def label(self) -> str:
        return f"{self.path}::{self.member}" if self.member else self.path


def iter_pickle_streams(blob: bytes, path: str, truncated: bool = False) -> Iterator[PickleStream]:
    """Yield the pickle programs inside one downloaded artifact.

    Modern `torch.save()` writes a zip archive whose `data.pkl` member holds
    the pickle while the tensors sit in separate uncompressed entries — that
    member is the part worth reading, and it is kilobytes even when the
    checkpoint is gigabytes. Older torch and plain .pkl files are a bare
    pickle stream.
    """
    if blob[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                yield from pickle_members_from_zip(zf, path)
        except zipfile.BadZipFile:
            # Truncated prefix of a zip is expected when range requests failed.
            if not truncated:
                logger.warning("%s starts like a zip but is not readable", path)
        return

    if _looks_like_pickle(blob):
        yield PickleStream(path, blob, truncated=truncated)


def pickle_members_from_zip(
    zf: zipfile.ZipFile, path: str, max_member_bytes: int = 8 * 1024 * 1024
) -> Iterator[PickleStream]:
    """Yield the pickle entries of an already-open torch archive.

    Split out so the fetcher can pass a ZipFile backed by HTTP range requests
    and read only the small `data.pkl` member out of a multi-gigabyte
    checkpoint.
    """
    for info in zf.infolist():
        if not info.filename.endswith((".pkl", ".pickle")):
            continue
        if info.file_size > max_member_bytes:
            logger.warning("skipping oversized pickle member %s in %s", info.filename, path)
            continue
        try:
            yield PickleStream(path, zf.read(info), member=info.filename)
        except Exception as exc:  # bad CRC, unsupported compression method
            logger.warning("unreadable zip member %s in %s: %s", info.filename, path, exc)


def _looks_like_pickle(blob: bytes) -> bool:
    """Cheap magic check. PROTO for protocol 2+, or a protocol-0/1 opener."""
    if not blob:
        return False
    if blob[0] == 0x80:  # PROTO
        return True
    return blob[0:1] in (b"(", b"c", b"]", b"}", b"[", b"{")


def _resolve_global(op_name: str, arg, recent: list[str]) -> tuple[str, str] | None:
    """Return (module, name) for a global-naming opcode, or None."""
    if op_name in ("GLOBAL", "INST") and isinstance(arg, str):
        module, _, name = arg.partition(" ")
        return (module, name) if module else None
    if op_name == "STACK_GLOBAL" and len(recent) >= 2:
        return (recent[-2], recent[-1])
    return None


def _classify(module: str, name: str) -> str:
    """One of 'dangerous', 'expected', 'unknown'."""
    if (module, name) in _ALWAYS_EXPECTED:
        return "expected"

    root = module.split(".")[0]
    if root in _DANGEROUS_MODULES:
        return "dangerous"

    for scope in (module, root):
        if name in _DANGEROUS_NAMES.get(scope, ()):
            return "dangerous"

    if module.startswith(_EXPECTED_MODULE_PREFIXES):
        return "expected"
    if root == "builtins" or root == "__builtin__":
        return "expected"  # dangerous builtins were caught above
    return "unknown"


def analyse_stream(stream: PickleStream) -> list[PatternMatch]:
    """Walk one pickle's opcodes and report what it would import and call."""
    dangerous: list[tuple[str, str]] = []
    unknown: list[tuple[str, str]] = []
    recent_strings: list[str] = []
    parse_error: str | None = None
    opcodes = 0

    try:
        for op, arg, _pos in pickletools.genops(stream.data):
            opcodes += 1
            if opcodes > MAX_OPCODES:
                break

            if op.name in _STRING_OPCODES and isinstance(arg, str):
                recent_strings.append(arg)
                if len(recent_strings) > 4:
                    del recent_strings[0]
                continue

            if op.name not in _GLOBAL_OPCODES:
                continue

            resolved = _resolve_global(op.name, arg, recent_strings)
            if not resolved:
                continue
            module, name = resolved
            kind = _classify(module, name)
            if kind == "dangerous" and resolved not in dangerous:
                dangerous.append(resolved)
            elif kind == "unknown" and resolved not in unknown:
                unknown.append(resolved)
    except Exception as exc:
        # genops raises on malformed or truncated streams. Truncation is
        # usually ours (we fetched a prefix), so it is only notable when we
        # held the whole file.
        parse_error = str(exc)

    matches: list[PatternMatch] = []

    if dangerous:
        listed = ", ".join(f"{m}.{n}" for m, n in dangerous[:MAX_REPORTED_GLOBALS])
        matches.append(PatternMatch(
            category="model_exploit",
            pattern_name="pickle_rce_gadget",
            description=(
                "Pickle imports an execution primitive — loading this file runs code. "
                f"References: {listed}"
            ),
            file_path=stream.label,
            severity=99,
            malware_grade=True,
            snippet=listed[:200],
        ))
    elif unknown:
        listed = ", ".join(f"{m}.{n}" for m, n in unknown[:MAX_REPORTED_GLOBALS])
        matches.append(PatternMatch(
            category="model_exploit",
            pattern_name="pickle_unexpected_global",
            description=(
                "Pickle imports code from outside the usual ML libraries. Legitimate "
                f"for a repo that pickles its own classes — worth reading: {listed}"
            ),
            file_path=stream.label,
            severity=45,
            snippet=listed[:200],
        ))

    if stream.truncated:
        # Say so. A weight file we only partly read must not look like a
        # weight file we cleared — that is the same failure as scoring an
        # unreadable repo 100.
        matches.append(PatternMatch(
            category="model_exploit",
            pattern_name="pickle_partial_scan",
            description=(
                "Weight file too large to retrieve in full — only its opening bytes "
                "were analysed. The pickle program normally sits at the front, but "
                "coverage of this file is incomplete."
            ),
            file_path=stream.label,
            severity=20,
            snippet=f"{len(stream.data):,} bytes examined",
        ))

    if parse_error and not stream.truncated:
        matches.append(PatternMatch(
            category="model_exploit",
            pattern_name="pickle_malformed",
            description=(
                "Pickle opcode stream could not be parsed. Malformed pickles are "
                "sometimes used to confuse scanners while still loading in Python."
            ),
            file_path=stream.label,
            severity=55,
            snippet=parse_error[:200],
        ))

    return matches


def scan_pickle_streams(streams: list[PickleStream]) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    for stream in streams:
        matches.extend(analyse_stream(stream))
    return matches


# ── Weight-format hygiene ─────────────────────────────────────────────────────

PICKLE_WEIGHT_EXTENSIONS = frozenset({
    ".pkl", ".pickle", ".bin", ".pt", ".pth", ".ckpt", ".joblib",
})
SAFE_WEIGHT_EXTENSIONS = frozenset({".safetensors", ".gguf", ".onnx", ".npz"})


def check_weight_formats(file_list: list[str]) -> list[PatternMatch]:
    """Flag repos that ship only the executable weight format.

    safetensors stores tensors and nothing else — loading it cannot run code.
    It has been the ecosystem default for long enough that a repo publishing
    pickle weights *and no safe equivalent* is either unmaintained or avoiding
    the format that would make tampering pointless. This is a nudge, not an
    accusation, so it is scored as informational.
    """
    pickled = [f for f in file_list if _ext(f) in PICKLE_WEIGHT_EXTENSIONS]
    if not pickled:
        return []
    if any(_ext(f) in SAFE_WEIGHT_EXTENSIONS for f in file_list):
        return []

    return [PatternMatch(
        category="model_exploit",
        pattern_name="pickle_only_weights",
        description=(
            f"Weights ship only in pickle format ({len(pickled)} file(s), no .safetensors). "
            "Loading them executes whatever the file names."
        ),
        file_path=pickled[0],
        severity=35,
        snippet=", ".join(pickled[:5]),
    )]


def _ext(path: str) -> str:
    return ("." + path.rsplit(".", 1)[-1].lower()) if "." in path else ""
