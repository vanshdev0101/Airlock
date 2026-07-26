"""Tests for which files get the scan budget.

The budget used to be "whatever the API listed first". These pin down that it
is now ranked, because a payload in file 101 was previously invisible while
the slots went to translation files.
"""

from app.config import get_settings
from app.fetcher.fetcher import _budgeted, _scan_priority

settings = get_settings()


def test_install_scripts_outrank_documentation():
    assert _scan_priority("setup.py") < _scan_priority("README.md")
    assert _scan_priority("install.sh") < _scan_priority("docs/guide.md")


def test_manifests_outrank_ordinary_source():
    assert _scan_priority("requirements.txt") < _scan_priority("src/utils.py")
    assert _scan_priority("package.json") < _scan_priority("src/utils.py")


def test_lockfiles_come_last():
    """Machine-generated, enormous, and never where anything hides."""
    assert _scan_priority("package-lock.json") > _scan_priority("docs/notes.md")
    assert _scan_priority("poetry.lock") > _scan_priority("tests/test_x.py")


def test_tests_and_docs_are_deprioritised():
    assert _scan_priority("tests/test_thing.py") > _scan_priority("src/thing.py")
    assert _scan_priority("examples/demo.py") > _scan_priority("src/thing.py")


def test_shallow_files_beat_deep_ones_at_the_same_tier():
    assert _scan_priority("main.py") < _scan_priority("a/b/c/main.py")


def test_budget_keeps_the_dangerous_file_when_truncating():
    """The regression this exists for: a payload past the cap was unreachable."""
    filler = [f"locales/lang_{i}.json" for i in range(settings.max_files_per_scan + 50)]
    selected = _budgeted(filler + ["setup.py"])

    assert len(selected) == settings.max_files_per_scan
    assert "setup.py" in selected
    assert selected[0] == "setup.py"


def test_manifests_survive_a_crowded_repo():
    """Dependency scanning is useless if the manifest never gets fetched."""
    filler = [f"data/file_{i}.json" for i in range(settings.max_files_per_scan * 2)]
    selected = _budgeted(filler + ["requirements.txt", "package.json"])
    assert "requirements.txt" in selected
    assert "package.json" in selected


def test_unscannable_extensions_never_enter_the_budget():
    assert _budgeted(["model.safetensors", "weights.bin", "notes.md"]) == ["notes.md"]


def test_budget_is_capped():
    many = [f"src/mod_{i}.py" for i in range(settings.max_files_per_scan + 25)]
    assert len(_budgeted(many)) == settings.max_files_per_scan
