"""Tests for supply-chain manifest analysis."""

import json

from app.scanner.dependency_scanner import scan_dependencies
from app.scanner.static_scanner import calculate_trust_score


def _names(matches):
    return {m.pattern_name for m in matches}


# ── Alternate indexes ─────────────────────────────────────────────────────────

def test_extra_index_url_is_flagged():
    files = {"requirements.txt": "--extra-index-url https://pkgs.evil.test/simple\nrequests==2.31.0\n"}
    matches = scan_dependencies(files)
    assert "dependency_alternate_index" in _names(matches)


def test_official_index_is_not_flagged():
    files = {"requirements.txt": "--index-url https://pypi.org/simple\nrequests==2.31.0\n"}
    assert scan_dependencies(files) == []


def test_pythonhosted_mirror_is_not_flagged():
    files = {"requirements.txt": "-f https://files.pythonhosted.org/packages\nnumpy\n"}
    assert scan_dependencies(files) == []


def test_index_url_reports_its_line_number():
    content = "# deps\nrequests\n--index-url https://evil.test/simple\n"
    match = scan_dependencies({"requirements.txt": content})[0]
    assert match.line_number == 3


# ── Direct URL installs ───────────────────────────────────────────────────────

def test_git_dependency_is_flagged():
    files = {"requirements.txt": "somelib @ git+https://github.com/someone/somelib.git\n"}
    assert "dependency_direct_url" in _names(scan_dependencies(files))


def test_plain_http_url_scores_above_https():
    http = scan_dependencies({"requirements.txt": "http://evil.test/pkg.tar.gz\n"})[0]
    https = scan_dependencies({"requirements.txt": "https://ok.test/pkg.tar.gz\n"})[0]
    assert http.severity > https.severity


def test_ordinary_pins_are_silent():
    content = "requests==2.31.0\nnumpy>=1.24\npydantic~=2.0\n# a comment\n\n"
    assert scan_dependencies({"requirements.txt": content}) == []


def test_requirements_dev_variant_is_scanned():
    files = {"requirements-dev.txt": "--extra-index-url https://evil.test/s\n"}
    assert "dependency_alternate_index" in _names(scan_dependencies(files))


# ── Typosquatting ─────────────────────────────────────────────────────────────

def test_typosquatted_package_is_flagged():
    matches = scan_dependencies({"requirements.txt": "reqeusts==2.31.0\n"})
    assert "dependency_typosquat" in _names(matches)
    assert "requests" in matches[0].description


def test_real_popular_package_is_not_a_typosquat():
    assert scan_dependencies({"requirements.txt": "requests\nnumpy\ntorch\n"}) == []


def test_known_good_near_miss_is_allowed():
    """boto is one edit from boto3 and is a real, legitimate package."""
    assert scan_dependencies({"requirements.txt": "boto\n"}) == []


def test_short_names_are_not_typosquat_candidates():
    assert scan_dependencies({"requirements.txt": "six\ntqdm\n"}) == []


# ── pyproject.toml ────────────────────────────────────────────────────────────

def test_pyproject_dependencies_are_scanned():
    content = '[project]\nname = "x"\ndependencies = ["reqeusts>=2.0", "numpy"]\n'
    assert "dependency_typosquat" in _names(scan_dependencies({"pyproject.toml": content}))


def test_poetry_custom_source_is_flagged():
    content = (
        '[[tool.poetry.source]]\nname = "internal"\nurl = "https://pkgs.evil.test/simple"\n'
    )
    assert "dependency_alternate_index" in _names(scan_dependencies({"pyproject.toml": content}))


def test_clean_pyproject_is_silent():
    content = '[project]\nname = "repoguard"\ndependencies = ["fastapi", "httpx", "pydantic"]\n'
    assert scan_dependencies({"pyproject.toml": content}) == []


def test_unparsable_pyproject_is_not_a_finding():
    assert scan_dependencies({"pyproject.toml": "this is not toml ==="}) == []


# ── package.json ──────────────────────────────────────────────────────────────

def test_npm_postinstall_hook_is_flagged():
    content = json.dumps({"name": "x", "scripts": {"postinstall": "node steal.js"}})
    matches = scan_dependencies({"package.json": content})
    assert "npm_install_hook" in _names(matches)


def test_ordinary_npm_scripts_are_ignored():
    content = json.dumps({"scripts": {"build": "vite build", "test": "vitest"}})
    assert scan_dependencies({"package.json": content}) == []


def test_npm_git_dependency_is_flagged():
    content = json.dumps({"dependencies": {"thing": "git+https://evil.test/thing.git"}})
    assert "dependency_direct_url" in _names(scan_dependencies({"package.json": content}))


def test_npm_semver_ranges_are_silent():
    content = json.dumps({"dependencies": {"react": "^19.0.0", "axios": "~1.6.0"}})
    assert scan_dependencies({"package.json": content}) == []


def test_malformed_package_json_is_not_a_finding():
    assert scan_dependencies({"package.json": "{ not json"}) == []


# ── Scoring ───────────────────────────────────────────────────────────────────

def test_alternate_index_alone_is_suspicious_not_dangerous():
    """A private index is a real risk but plenty of companies have one."""
    matches = scan_dependencies({"requirements.txt": "--extra-index-url https://evil.test/s\n"})
    assert 40 <= calculate_trust_score(matches) < 100


def test_findings_are_deduplicated_per_file():
    content = "--extra-index-url https://evil.test/s\n--extra-index-url https://evil.test/s\n"
    matches = scan_dependencies({"requirements.txt": content})
    assert len(matches) == 1
