"""
Supply-chain analysis of dependency manifests.

The scanner reads a repo's own source but not what that source pulls in, which
leaves the easiest attack completely unexamined: you do not need to write
malicious code if you can make `pip install -r requirements.txt` fetch it for
you. This module reads the manifests and reports the three ways that happens —
a package resolved from somewhere other than the official index, a package
installed straight from a URL, and a name that impersonates a popular one.

Parsing only. Nothing here resolves, downloads, or installs a dependency.
"""

import json
import logging
import re
import tomllib

from ..core.text import damerau_levenshtein
from .scan import PatternMatch

logger = logging.getLogger(__name__)

REQUIREMENTS_RE = re.compile(r"^requirements[\w.-]*\.txt$", re.IGNORECASE)

# `--index-url` replaces PyPI outright; `--extra-index-url` adds a source that
# pip will happily prefer if it offers a higher version — the mechanic behind
# dependency-confusion attacks.
_INDEX_RE = re.compile(
    r"^\s*(?:-i|--index-url|--extra-index-url)[=\s]+(\S+)", re.MULTILINE
)
_FIND_LINKS_RE = re.compile(r"^\s*(?:-f|--find-links)[=\s]+(\S+)", re.MULTILINE)
_OFFICIAL_INDEX_HOSTS = ("pypi.org", "pypi.python.org", "files.pythonhosted.org")

# A requirement that names a location instead of a version.
_DIRECT_REF_RE = re.compile(
    r"^\s*(?:[A-Za-z0-9._-]+\s*@\s*)?((?:git\+|hg\+|svn\+|bzr\+)?https?://\S+)",
    re.MULTILINE,
)

_REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")

# Popular targets, per ecosystem. Kept deliberately short: every entry is a
# name an attacker has a real motive to impersonate, and a longer list buys
# more false positives than coverage.
_POPULAR_PYPI = frozenset({
    "requests", "urllib3", "numpy", "pandas", "scipy", "torch", "tensorflow",
    "transformers", "pillow", "django", "flask", "fastapi", "pydantic",
    "sqlalchemy", "boto3", "click", "jinja2", "pytest", "setuptools",
    "cryptography", "beautifulsoup4", "selenium", "matplotlib", "scikit-learn",
    "opencv-python", "python-dateutil", "colorama", "tqdm", "pyyaml",
})
_POPULAR_NPM = frozenset({
    "react", "lodash", "express", "axios", "chalk", "commander", "webpack",
    "typescript", "eslint", "moment", "debug", "dotenv", "mongoose", "vue",
    "next", "babel", "jest", "prettier", "rimraf", "uuid",
})

# Real packages that sit one edit from a popular name. Without these the
# typosquat check would flag ordinary dependencies.
_KNOWN_GOOD = frozenset({
    "boto", "panda", "request", "requests-oauthlib", "click-default-group",
    "flask-cors", "torchvision", "torchaudio", "attrs", "attr", "mock",
    "six", "nose", "pytz", "toml", "tomli", "rich", "typer", "httpx",
    "react-dom", "vue-router", "next-auth", "uuidv4", "debug-js",
})

# Below this length an edit distance of 1 is noise, not impersonation.
_MIN_TYPOSQUAT_LENGTH = 5


def scan_dependencies(files: dict[str, str]) -> list[PatternMatch]:
    """Inspect every dependency manifest among the fetched files."""
    matches: list[PatternMatch] = []
    for path, content in files.items():
        if not content:
            continue
        name = path.replace("\\", "/").rsplit("/", 1)[-1].lower()

        if REQUIREMENTS_RE.match(name) or name == "constraints.txt":
            matches.extend(_scan_requirements(path, content))
        elif name == "pyproject.toml":
            matches.extend(_scan_pyproject(path, content))
        elif name == "package.json":
            matches.extend(_scan_package_json(path, content))

    return _dedupe(matches)


# ── requirements.txt ──────────────────────────────────────────────────────────

def _scan_requirements(path: str, content: str) -> list[PatternMatch]:
    matches: list[PatternMatch] = []

    for match in _INDEX_RE.finditer(content):
        url = match.group(1)
        if _is_official_index(url):
            continue
        line = content[: match.start()].count("\n") + 1
        extra = match.group(0).lstrip().startswith(("--extra", "-i")) and "extra" in match.group(0)
        matches.append(PatternMatch(
            category="supply_chain",
            pattern_name="dependency_alternate_index",
            description=(
                "Dependencies resolve from a non-PyPI index. Whoever controls that "
                "index controls what gets installed"
                + (" — and pip prefers whichever index offers the higher version."
                   if extra else ".")
            ),
            file_path=path, line_number=line, severity=85,
            snippet=match.group(0).strip()[:200],
        ))

    for match in _FIND_LINKS_RE.finditer(content):
        url = match.group(1)
        if _is_official_index(url) or not url.startswith(("http://", "https://")):
            continue
        line = content[: match.start()].count("\n") + 1
        matches.append(PatternMatch(
            category="supply_chain",
            pattern_name="dependency_alternate_index",
            description="Packages are fetched from an arbitrary --find-links host.",
            file_path=path, line_number=line, severity=75,
            snippet=match.group(0).strip()[:200],
        ))

    for line_no, raw in enumerate(content.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue

        direct = _DIRECT_REF_RE.match(line)
        if direct:
            url = direct.group(1)
            matches.append(PatternMatch(
                category="supply_chain",
                pattern_name="dependency_direct_url",
                description=(
                    "Dependency installed straight from a URL, bypassing the index "
                    "and its versioning entirely. The contents can change without "
                    "the requirement changing."
                ),
                file_path=path, line_number=line_no,
                severity=80 if url.startswith("http://") else 70,
                snippet=line[:200],
            ))
            continue

        name_match = _REQ_NAME_RE.match(line)
        if name_match:
            squat = _typosquat_of(name_match.group(1), _POPULAR_PYPI)
            if squat:
                matches.append(_typosquat_match(path, line_no, name_match.group(1), squat, line))

    return matches


def _is_official_index(url: str) -> bool:
    return any(host in url for host in _OFFICIAL_INDEX_HOSTS)


# ── pyproject.toml ────────────────────────────────────────────────────────────

def _scan_pyproject(path: str, content: str) -> list[PatternMatch]:
    try:
        data = tomllib.loads(content)
    except Exception as exc:
        logger.debug("unparsable pyproject at %s: %s", path, exc)
        return []

    matches: list[PatternMatch] = []
    requirements: list[str] = []

    project = data.get("project", {})
    if isinstance(project.get("dependencies"), list):
        requirements.extend(str(d) for d in project["dependencies"])
    for group in (project.get("optional-dependencies") or {}).values():
        if isinstance(group, list):
            requirements.extend(str(d) for d in group)

    poetry = data.get("tool", {}).get("poetry", {})
    for key in ("dependencies", "dev-dependencies"):
        for name, spec in (poetry.get(key) or {}).items():
            requirements.append(name)
            if isinstance(spec, dict) and ("url" in spec or "git" in spec):
                matches.append(PatternMatch(
                    category="supply_chain",
                    pattern_name="dependency_direct_url",
                    description=(
                        f"'{name}' is installed from a URL or git ref rather than "
                        "the package index."
                    ),
                    file_path=path, severity=70,
                    snippet=f"{name} = {spec}"[:200],
                ))

    # Custom package sources — the pyproject spelling of --extra-index-url.
    for source in poetry.get("source", []) or []:
        url = str(source.get("url", ""))
        if url and not _is_official_index(url):
            matches.append(PatternMatch(
                category="supply_chain",
                pattern_name="dependency_alternate_index",
                description=(
                    f"Poetry resolves packages from '{source.get('name', url)}', "
                    "not the official index."
                ),
                file_path=path, severity=85, snippet=url[:200],
            ))

    for req in requirements:
        name_match = _REQ_NAME_RE.match(req)
        if not name_match:
            continue
        if "@" in req or "://" in req:
            matches.append(PatternMatch(
                category="supply_chain",
                pattern_name="dependency_direct_url",
                description="Dependency pinned to a URL instead of an index version.",
                file_path=path, severity=70, snippet=req[:200],
            ))
        squat = _typosquat_of(name_match.group(1), _POPULAR_PYPI)
        if squat:
            matches.append(_typosquat_match(path, None, name_match.group(1), squat, req))

    return matches


# ── package.json ──────────────────────────────────────────────────────────────

def _scan_package_json(path: str, content: str) -> list[PatternMatch]:
    try:
        data = json.loads(content)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []

    matches: list[PatternMatch] = []

    # npm runs these automatically on `npm install`, which makes them the most
    # directly exploitable field in the whole file.
    scripts = data.get("scripts") or {}
    for hook in ("preinstall", "install", "postinstall", "prepare"):
        command = scripts.get(hook)
        if isinstance(command, str) and command.strip():
            matches.append(PatternMatch(
                category="supply_chain",
                pattern_name="npm_install_hook",
                description=(
                    f"'{hook}' script runs automatically on npm install — "
                    "arbitrary code executes before anyone reads the package."
                ),
                file_path=path,
                severity=75 if hook != "prepare" else 55,
                snippet=f"{hook}: {command}"[:200],
            ))

    for field in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, spec in (data.get(field) or {}).items():
            if isinstance(spec, str) and _is_remote_npm_spec(spec):
                matches.append(PatternMatch(
                    category="supply_chain",
                    pattern_name="dependency_direct_url",
                    description=(
                        f"'{name}' is installed from a URL or git ref rather than "
                        "the npm registry."
                    ),
                    file_path=path, severity=70, snippet=f"{name}: {spec}"[:200],
                ))
            squat = _typosquat_of(name, _POPULAR_NPM)
            if squat:
                matches.append(_typosquat_match(path, None, name, squat, f"{name}: {spec}"))

    return matches


def _is_remote_npm_spec(spec: str) -> bool:
    lowered = spec.lower()
    if lowered.startswith(("http://", "https://", "git+", "git://", "github:")):
        return True
    # `user/repo` shorthand resolves to GitHub.
    return bool(re.fullmatch(r"[\w.-]+/[\w.-]+", spec)) and not spec.startswith("@")


# ── Typosquatting ─────────────────────────────────────────────────────────────

def _typosquat_of(name: str, popular: frozenset[str]) -> str | None:
    """The popular package this name is one edit away from, if any."""
    clean = name.strip().lower()
    if len(clean) < _MIN_TYPOSQUAT_LENGTH:
        return None
    if clean in popular or clean in _KNOWN_GOOD:
        return None
    for target in popular:
        if len(target) < _MIN_TYPOSQUAT_LENGTH:
            continue
        if abs(len(clean) - len(target)) > 1:
            continue
        if damerau_levenshtein(clean, target) == 1:
            return target
    return None


def _typosquat_match(path, line, name, target, snippet) -> PatternMatch:
    return PatternMatch(
        category="supply_chain",
        pattern_name="dependency_typosquat",
        description=(
            f"Dependency '{name}' is one character from '{target}'. Confirm it is "
            "the package you meant — this is how squatted packages get installed."
        ),
        file_path=path, line_number=line, severity=80,
        snippet=str(snippet)[:200],
    )


def _dedupe(matches: list[PatternMatch]) -> list[PatternMatch]:
    """One finding per (pattern, file, snippet); manifests repeat themselves."""
    seen: set[tuple] = set()
    unique: list[PatternMatch] = []
    for m in matches:
        key = (m.pattern_name, m.file_path, m.snippet)
        if key not in seen:
            seen.add(key)
            unique.append(m)
    return unique
