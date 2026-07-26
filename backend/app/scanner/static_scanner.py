"""
Static analysis scanner for RepoGuard.
Regex + AST — no code execution.
"""

import ast
import logging
import re
from dataclasses import dataclass

from .scan import PatternMatch

logger = logging.getLogger(__name__)


@dataclass
class Pattern:
    name: str
    category: str
    description: str
    severity: int
    regexes: list[str]
    file_types: list[str]
    # True only for signals with no legitimate use in a model or library repo.
    # `systemctl enable` and `sudo` are risky in context but ship in ordinary
    # install scripts; disabling Defender does not. Only malware-grade signals
    # may short-circuit the score to "dangerous".
    malware_grade: bool = False


# ── Path helpers ──────────────────────────────────────────────────────────────

_TEST_PATHS = {"test", "tests", "docs", "doc", "examples", "example", "fixtures"}


def _is_test_or_docs(path: str) -> bool:
    parts = path.lower().replace("\\", "/").split("/")
    return bool(_TEST_PATHS.intersection(parts))


# Fix 5: allowlist known-safe bat files, skip docs/
_BAT_ALLOWLIST = {"make.bat", "build.bat", "clean.bat", "install.bat"}


def _is_suspicious_bat(path: str) -> bool:
    lower = path.lower().replace("\\", "/")
    filename = lower.split("/")[-1]
    return filename not in _BAT_ALLOWLIST and not _is_test_or_docs(path)


# ── Pattern registry ──────────────────────────────────────────────────────────

PATTERNS: list[Pattern] = [

    # Obfuscation
    Pattern("base64_decode_exec", "obfuscation",
            "Base64 + exec/eval — classic payload hiding", 90,
            [r"eval\s*\(\s*base64", r"exec\s*\(\s*base64",
             r"base64\.b64decode.*eval", r"base64\.b64decode.*exec"],
            [".py"], malware_grade=True),

    Pattern("base64_decode", "obfuscation",
            "Base64 decoded at runtime — commonly hides URLs or payloads", 70,
            [r"base64\.b64decode\s*\(", r"base64\.urlsafe_b64decode\s*\(",
             r"__import__\(['\"]base64['\"]"], [".py"]),

    Pattern("hex_payload", "obfuscation",
            "Long hex-encoded string — possible shellcode", 80,
            [r"bytes\.fromhex\s*\(['\"][0-9a-fA-F]{40,}",
             r"\\x[0-9a-fA-F]{2}(\\x[0-9a-fA-F]{2}){20,}"],
            [".py", ".bat", ".ps1", ".sh"]),

    Pattern("dynamic_eval", "obfuscation",
            "eval/exec on dynamic string — executing unknown code at runtime", 85,
            [r"eval\s*\(\s*compile\s*\(", r"exec\s*\(\s*__import__",
             r"eval\s*\(\s*bytes", r"exec\s*\(\s*bytes"], [".py"]),

    # Network
    Pattern("ssl_verification_disabled", "network",
            "SSL verification disabled — allows fake-cert MITM attacks", 88,
            [r"verify\s*=\s*False", r"ssl\._create_unverified_context",
             r"urllib3\.disable_warnings", r"PYTHONHTTPSVERIFY\s*=\s*0"],
            [".py", ".sh"]),

    Pattern("suspicious_network_download", "network",
            "Downloading + executing from external URL — possible C2 fetch", 85,
            [r"urllib\.request\.urlretrieve\s*\(", r"wget\s+http",
             r"curl\s+-[a-zA-Z]*o\s+.*http", r"Invoke-WebRequest",
             r"DownloadFile\s*\("],
            [".py", ".bat", ".ps1", ".sh"]),

    Pattern("dead_drop_resolver", "network",
            "Fetching C2 address from paste service", 90,
            [r"pastebin\.com/raw", r"paste\.ee/r", r"hastebin\.com/raw",
             r"gist\.github\.com/raw", r"jsonkeeper\.com"],
            [".py", ".bat", ".ps1", ".sh"], malware_grade=True),

    Pattern("data_exfiltration", "network",
            "Reading sensitive local files + sending to remote server", 99,
            [r"\.ssh[/\\]id_rsa", r"\.ssh[/\\]id_ed25519",
             r"glob\s*\(.*\*\.env", r"\.aws[/\\]credentials",
             r"wallet\.dat", r"seed[\s_-]?phrase"],
            [".py", ".bat", ".ps1", ".sh"], malware_grade=True),

    # System execution
    Pattern("powershell_from_python", "system_exec",
            "Python launching PowerShell — two-stage loader", 92,
            [r"subprocess.*powershell", r"os\.system.*powershell",
             r"Popen.*powershell", r"subprocess.*cmd\.exe",
             r"-WindowStyle\s+Hidden"], [".py"], malware_grade=True),

    Pattern("defender_exclusion", "system_exec",
            "Adding Windows Defender exclusion — malware evasion", 100,
            [r"Add-MpPreference\s+-ExclusionPath", r"Set-MpPreference\s+-Disable",
             r"DisableRealtimeMonitoring"],
            [".bat", ".ps1", ".py", ".sh"], malware_grade=True),

    Pattern("privilege_escalation", "system_exec",
            "Silently gaining Windows admin — no legitimate model needs this", 97,
            [r"runas\s*/user:Administrator", r"Start-Process.*-Verb\s+RunAs"],
            [".bat", ".ps1", ".py", ".sh"], malware_grade=True),

    # Split out of privilege_escalation: `sudo -S` pipes a password from stdin,
    # which is sketchy but also how plenty of legitimate install scripts work.
    Pattern("sudo_noninteractive", "system_exec",
            "Non-interactive sudo — review what it installs or modifies", 45,
            [r"sudo\s+-S"], [".sh", ".py"]),

    Pattern("persistence_mechanism", "system_exec",
            "Scheduled tasks or registry run keys — only malware needs persistence", 95,
            [r"schtasks\s*/create",
             r"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
             r"reg\s+add.*CurrentVersion\\Run"],
            [".bat", ".ps1", ".py", ".sh"], malware_grade=True),

    # Split out of persistence_mechanism: services and cron jobs are the normal
    # way to run anything on a server, so they are context, not a verdict.
    Pattern("service_or_cron_install", "system_exec",
            "Installs a service or cron job — confirm this is expected", 40,
            [r"crontab\s+-[le]", r"systemctl\s+enable"],
            [".sh", ".py"]),

    # File behaviour
    Pattern("self_deletion", "file_behaviour",
            "Script deletes itself after running — evidence destruction", 98,
            [r"os\.remove\s*\(\s*__file__", r"del\s+/f\s+%~f0",
             r"Remove-Item\s+\$PSCommandPath", r"rm\s+-f\s+\$0"],
            [".py", ".bat", ".ps1", ".sh"], malware_grade=True),

    # Fix 5: presence-based, filtered by _is_suspicious_bat
    Pattern("suspicious_bat_in_ai_repo", "file_behaviour",
            ".bat/.ps1 script present — review for unexpected shell execution", 75,
            [r".*"], [".bat", ".ps1"]),

    # Evasion
    # Bare "VMware"/"QEMU" matched any passing mention in a comment or docstring.
    # Require the surrounding shape of an actual hypervisor check instead.
    Pattern("vm_detection", "evasion",
            "VM/sandbox detection — malware avoids running during analysis", 93,
            [r"(platform|wmi|dmidecode|systeminfo|uname|getoutput|check_output|manufacturer|BIOS)"
             r"[^\n]*\b(VMware|VirtualBox|VBOX|QEMU|Xen)\b",
             r"\b(VMware|VirtualBox|VBOX|QEMU)\b[^\n]*\b(in|==|!=)\b",
             r"psutil.*cpu_count.*[<=>]=?\s*[12]"],
            [".py", ".bat", ".ps1"]),

    Pattern("sandbox_sleep_delay", "evasion",
            "Unusually long sleep — outlasting sandbox timeouts", 60,
            [r"time\.sleep\s*\(\s*[6-9][0-9]{1,}",
             r"time\.sleep\s*\(\s*[1-9][0-9]{2,}"],
            [".py", ".bat", ".ps1"]),

    # Pickle / model
    Pattern("unsafe_pickle_load", "model_exploit",
            "pickle.loads — arbitrary Python executes on deserialization", 85,
            [r"pickle\.loads?\s*\("], [".py"]),

    # Bare __reduce__/__reduce_ex__ was removed: defining them is the standard
    # way to make a class picklable (requests/exceptions.py does it). What
    # matters is a __reduce__ that returns an executor — that is the exploit.
    Pattern("malicious_reduce_payload", "model_exploit",
            "__reduce__ returning os.system/eval — pickle RCE gadget", 96,
            [r"__reduce__.*\b(os\.system|subprocess|eval|exec|commands\.getoutput)\b",
             r"return\s*\(\s*(os\.system|subprocess\.\w+|eval|exec)\s*,"],
            [".py"], malware_grade=True),

    # HuggingFace
    Pattern("trust_remote_code_enabled", "hf_exploit",
            "trust_remote_code=True — executes arbitrary repo code on model load", 85,
            [r"trust_remote_code\s*=\s*True",
             r"from_pretrained\s*\([^)]*trust_remote_code"],
            [".py", ".yaml", ".yml", ".json"]),

    # Same string in a model card is documentation, not an executed call.
    # Worth surfacing so the reader knows to check, but not a threat by itself.
    Pattern("trust_remote_code_documented", "hf_exploit",
            "Docs instruct loading with trust_remote_code=True — verify the repo's own code", 30,
            [r"trust_remote_code\s*=\s*True"], [".md", ".txt"]),

    Pattern("pickle_checkpoint_detected", "hf_exploit",
            ".pkl file present — executes code on torch.load()", 80,
            [r".*"], [".pkl", ".pickle"]),

    Pattern("binary_model_with_code", "hf_exploit",
            ".bin model alongside Python — possible trojanized checkpoint", 70,
            [r".*"], [".bin"]),
]


# ── Scanner ───────────────────────────────────────────────────────────────────

class StaticScanner:
    def __init__(self):
        self.patterns = PATTERNS

    def scan_files(self, files: dict[str, str]) -> list[PatternMatch]:
        matches: list[PatternMatch] = []
        for file_path, content in files.items():
            if not content:
                continue
            ext = self._ext(file_path)
            matches.extend(self._scan_file(file_path, content, ext))
        return matches

    def _scan_file(self, path: str, content: str, ext: str) -> list[PatternMatch]:
        matches: list[PatternMatch] = []
        in_test = _is_test_or_docs(path)

        for pattern in self.patterns:
            if ext not in pattern.file_types:
                continue

            # Presence-based: extension is the signal
            if pattern.name in ("pickle_checkpoint_detected", "binary_model_with_code"):
                if not in_test:
                    matches.append(self._presence_match(pattern, path, ext))
                continue

            # Fix 5: smarter bat filtering
            if pattern.name == "suspicious_bat_in_ai_repo":
                if _is_suspicious_bat(path):
                    matches.append(self._presence_match(pattern, path, ext))
                continue

            # One finding per pattern per file. A pattern's regexes are
            # alternative spellings of the same threat, so emitting one match
            # per regex both double-reports it in the UI and compounds the
            # score penalty. Report the earliest line instead.
            hits: list[PatternMatch] = []
            for regex in pattern.regexes:
                hits.extend(self._regex_scan(content, regex, path, pattern, in_test))
            if hits:
                matches.append(min(hits, key=lambda m: m.line_number or 0))

        # Fix 1: pass existing matches so AST skips already-reported lines
        if ext == ".py":
            matches.extend(self._ast_scan(content, path, existing=matches))

        return matches

    def _presence_match(self, pattern: Pattern, path: str, ext: str) -> PatternMatch:
        return PatternMatch(
            category=pattern.category, pattern_name=pattern.name,
            description=pattern.description, file_path=path,
            severity=pattern.severity, snippet=f"File type: {ext}",
            malware_grade=pattern.malware_grade,
        )

    def _regex_scan(self, content, regex, path, pattern, in_test) -> list[PatternMatch]:
        if in_test and pattern.severity < 90:
            return []
        matches = []
        try:
            for i, line in enumerate(content.splitlines(), start=1):
                if re.search(regex, line, re.IGNORECASE):
                    matches.append(PatternMatch(
                        category=pattern.category, pattern_name=pattern.name,
                        description=pattern.description, file_path=path,
                        line_number=i, severity=pattern.severity,
                        snippet=line.strip()[:200],
                        malware_grade=pattern.malware_grade,
                    ))
                    break  # one hit per pattern per file
        except re.error as e:
            logger.warning(f"Bad regex {regex!r}: {e}")
        return matches

    def _ast_scan(self, content: str, path: str, existing: list[PatternMatch]) -> list[PatternMatch]:
        # Fix 1: skip lines already reported by regex pass
        reported: set[tuple[str, int]] = {
            (m.file_path, m.line_number)
            for m in existing if m.line_number is not None
        }
        matches = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return matches

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = self._call_name(node)

            if fn in ("exec", "eval"):
                for arg in node.args:
                    if isinstance(arg, ast.Call) and "b64decode" in (self._call_name(arg) or ""):
                        key = (path, node.lineno)
                        if key not in reported:
                            matches.append(PatternMatch(
                                category="obfuscation",
                                pattern_name="ast_exec_b64decode",
                                description="exec/eval wrapping base64.b64decode — payload execution",
                                file_path=path, line_number=node.lineno, severity=95,
                                malware_grade=True,
                                snippet=f"{fn}(base64.b64decode(...)) at line {node.lineno}",
                            ))
                            reported.add(key)

            if fn in ("subprocess.run", "subprocess.Popen", "os.system"):
                src = ast.unparse(node)
                if "powershell" in src.lower() or "cmd.exe" in src.lower():
                    key = (path, node.lineno)
                    if key not in reported:
                        matches.append(PatternMatch(
                            category="system_exec", pattern_name="ast_subprocess_shell",
                            description="subprocess launching shell (powershell/cmd.exe)",
                            file_path=path, line_number=node.lineno, severity=92,
                            malware_grade=True, snippet=src[:200],
                        ))
                        reported.add(key)

            # Fix 1: torch.load is AST-only — regex version removed from PATTERNS
            if fn == "torch.load":
                if "weights_only" not in {kw.arg for kw in node.keywords}:
                    key = (path, node.lineno)
                    if key not in reported:
                        matches.append(PatternMatch(
                            category="hf_exploit", pattern_name="ast_torch_load_unsafe",
                            description="torch.load() missing weights_only=True — unsafe pickle execution",
                            # Context-dependent, not malware-grade: omitting
                            # weights_only is the default in most tutorials and
                            # pre-2.6 code. Real risk, but far too common to
                            # push a repo toward "dangerous" on its own.
                            file_path=path, line_number=node.lineno, severity=55,
                            snippet=f"torch.load() at line {node.lineno}",
                        ))
                        reported.add(key)

        return matches

    def _call_name(self, node: ast.Call) -> str | None:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            parts, cur = [], node.func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            return ".".join(reversed(parts))
        return None

    def _ext(self, path: str) -> str:
        return ("." + path.rsplit(".", 1)[-1].lower()) if "." in path else ""


# ── Trust scoring ─────────────────────────────────────────────────────────────

_WEIGHTS = {
    "hf_exploit": 1.4, "model_exploit": 1.3, "system_exec": 1.3,
    "network": 1.2, "obfuscation": 1.1, "evasion": 1.0,
    "file_behaviour": 0.6, "account": 0.5,
}
# A single finding may short-circuit the score only if it is malware-grade
# (no legitimate use in a model/library repo) *and* severe. The old rule keyed
# off category alone, so `systemctl enable` in a deploy script scored the same
# 15 as disabling Windows Defender. It also named "hf_exploit", a category no
# pattern ever reached at this threshold.
_INSTANT_THRESHOLD = 95

# Points a single maximum-severity finding can remove, before category weight.
_MAX_PENALTY = 50


def calculate_trust_score(matches: list[PatternMatch]) -> int:
    if not matches:
        return 100
    for m in matches:
        if m.malware_grade and m.severity >= _INSTANT_THRESHOLD:
            return 15
    score = 100.0
    for i, m in enumerate(sorted(matches, key=lambda x: x.severity, reverse=True)):
        # Quadratic in severity, so a 90-severity finding costs ~9x a
        # 30-severity one rather than 3x. Under the old linear curve four
        # merely-informational findings (a cron job, a sudo call, a docs
        # mention) summed to "dangerous" on a repo with nothing wrong with it.
        penalty = (m.severity / 100) ** 2 * _MAX_PENALTY
        score -= penalty * _WEIGHTS.get(m.category, 1.0) * (1 / (1 + i * 0.3))
    return max(0, round(score))