"""
Static analysis scanner for RepoGuard.
Detects malicious patterns in repo files using regex + AST parsing.
Does NOT execute any code — purely reads and analyses.
"""

import re
import ast
import logging
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


# ── Paths that reduce false positives ────────────────────────────────────────

_TEST_PATHS = {"test", "tests", "docs", "doc", "examples", "example", "fixtures"}

def _is_test_or_docs(file_path: str) -> bool:
    parts = file_path.lower().replace("\\", "/").split("/")
    return bool(_TEST_PATHS.intersection(parts))


# ── All patterns ──────────────────────────────────────────────────────────────

PATTERNS: list[Pattern] = [

    # ── Category 1: Obfuscation ──────────────────────────────────────────────

    Pattern(
        name="base64_decode_exec",
        category="obfuscation",
        description="Base64 decoding combined with exec/eval — classic payload hiding technique",
        severity=90,
        regexes=[
            r"eval\s*\(\s*base64",
            r"exec\s*\(\s*base64",
            r"base64\.b64decode.*eval",
            r"base64\.b64decode.*exec",
        ],
        file_types=[".py"],
    ),

    Pattern(
        name="base64_decode",
        category="obfuscation",
        description="Base64 encoded string decoded at runtime — commonly hides URLs or payloads",
        severity=70,
        regexes=[
            r"base64\.b64decode\s*\(",
            r"base64\.urlsafe_b64decode\s*\(",
            r"__import__\(['\"]base64['\"]",
        ],
        file_types=[".py"],
    ),

    Pattern(
        name="hex_payload",
        category="obfuscation",
        description="Long hex-encoded string — used to hide binary payloads or shellcode",
        severity=80,
        regexes=[
            r"bytes\.fromhex\s*\(['\"][0-9a-fA-F]{40,}",
            r"\\x[0-9a-fA-F]{2}(\\x[0-9a-fA-F]{2}){20,}",
        ],
        file_types=[".py", ".bat", ".ps1", ".sh"],
    ),

    Pattern(
        name="dynamic_eval",
        category="obfuscation",
        description="eval() or exec() on a dynamic string — executing unknown code at runtime",
        severity=85,
        regexes=[
            r"eval\s*\(\s*compile\s*\(",
            r"exec\s*\(\s*__import__",
            r"eval\s*\(\s*bytes",
            r"exec\s*\(\s*bytes",
        ],
        file_types=[".py"],
    ),

    # ── Category 2: Network ───────────────────────────────────────────────────

    Pattern(
        name="ssl_verification_disabled",
        category="network",
        description="SSL verification explicitly disabled — allows connections to attacker servers",
        severity=88,
        regexes=[
            r"verify\s*=\s*False",
            r"ssl\._create_unverified_context",
            r"urllib3\.disable_warnings",
            r"PYTHONHTTPSVERIFY\s*=\s*0",
            r"ssl_verify\s*=\s*False",
        ],
        file_types=[".py", ".sh"],
    ),

    Pattern(
        name="suspicious_network_download",
        category="network",
        description="Downloading and executing content from external URL — possible C2 fetch",
        severity=85,
        regexes=[
            r"urllib\.request\.urlretrieve\s*\(",
            r"requests\.(get|post)\s*\(.*http.*\).*open\s*\(",
            r"wget\s+http",
            r"curl\s+-[a-zA-Z]*o\s+.*http",
            r"Invoke-WebRequest",
            r"DownloadFile\s*\(",
        ],
        file_types=[".py", ".bat", ".ps1", ".sh"],
    ),

    Pattern(
        name="dead_drop_resolver",
        category="network",
        description="Fetching C2 address from paste service — one-hop indirection to hide real server",
        severity=90,
        regexes=[
            r"jsonkeeper\.com",
            r"pastebin\.com/raw",
            r"paste\.ee/r",
            r"gist\.github\.com/raw",
            r"hastebin\.com/raw",
            r"privatebin",
        ],
        file_types=[".py", ".bat", ".ps1", ".sh"],
    ),

    Pattern(
        name="data_exfiltration",
        category="network",
        description="Reading sensitive local files and sending to remote server",
        severity=99,
        regexes=[
            r"\.ssh[/\\]id_rsa",
            r"\.ssh[/\\]id_ed25519",
            r"glob\s*\(.*\*\.env",
            r"AppData.*Chrome.*Login Data",
            r"AppData.*Firefox.*cookies",
            r"\.aws[/\\]credentials",
            r"wallet\.dat",
            r"seed[\s_-]?phrase",
        ],
        file_types=[".py", ".bat", ".ps1", ".sh"],
    ),

    # ── Category 3: System execution ─────────────────────────────────────────

    Pattern(
        name="powershell_from_python",
        category="system_exec",
        description="Python launching PowerShell — two-stage loader pattern",
        severity=92,
        regexes=[
            r"subprocess.*powershell",
            r"os\.system.*powershell",
            r"Popen.*powershell",
            r"subprocess.*cmd\.exe",
            r"WindowStyle\s+Hidden",
            r"-WindowStyle\s+Hidden",
        ],
        file_types=[".py"],
    ),

    Pattern(
        name="defender_exclusion",
        category="system_exec",
        description="Adding to Windows Defender exclusion list — malware evasion",
        severity=100,
        regexes=[
            r"Add-MpPreference\s+-ExclusionPath",
            r"Set-MpPreference\s+-Disable",
            r"DisableRealtimeMonitoring",
            r"Add-MpPreference.*Exclusion",
        ],
        file_types=[".bat", ".ps1", ".py", ".sh"],
    ),

    Pattern(
        name="privilege_escalation",
        category="system_exec",
        description="Silently gaining admin/root privileges — no legitimate model needs this",
        severity=97,
        regexes=[
            r"runas\s*/user:Administrator",
            r"Start-Process.*-Verb\s+RunAs",
            r"ShellExecute.*runas",
            r"sudo\s+-S",
        ],
        file_types=[".bat", ".ps1", ".py", ".sh"],
    ),

    Pattern(
        name="persistence_mechanism",
        category="system_exec",
        description="Creating scheduled tasks or registry run keys — only malware needs persistence",
        severity=95,
        regexes=[
            r"schtasks\s*/create",
            r"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            r"HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            r"crontab\s+-[le]",
            r"systemctl\s+enable",
        ],
        file_types=[".bat", ".ps1", ".py", ".sh"],
    ),

    # ── Category 4: File behaviour ────────────────────────────────────────────

    Pattern(
        name="self_deletion",
        category="file_behaviour",
        description="Script deletes itself after running — evidence destruction",
        severity=98,
        regexes=[
            r"os\.remove\s*\(\s*__file__",
            r"del\s+/f\s+%~f0",
            r"Remove-Item\s+\$PSCommandPath",
            r"rm\s+-f\s+\$0",
        ],
        file_types=[".py", ".bat", ".ps1", ".sh"],
    ),

    Pattern(
        name="suspicious_bat_in_ai_repo",
        category="file_behaviour",
        description=".bat or .ps1 file in an AI model repo — no legitimate ML purpose",
        severity=75,
        regexes=[r".*"],
        file_types=[".bat", ".ps1"],
    ),

    # ── Category 5: Evasion ───────────────────────────────────────────────────

    Pattern(
        name="vm_detection",
        category="evasion",
        description="Checking for VM/sandbox environment — malware avoids running during analysis",
        severity=93,
        regexes=[
            r"VMware", r"VirtualBox", r"VBOX", r"QEMU",
            r"Wireshark", r"OllyDbg", r"x64dbg",
            r"psutil.*cpu_count.*[<=>]=?\s*[12]",
        ],
        file_types=[".py", ".bat", ".ps1"],
    ),

    Pattern(
        name="sandbox_sleep_delay",
        category="evasion",
        description="Unusually long sleep — outlasting automated sandbox timeouts",
        severity=60,
        regexes=[
            r"time\.sleep\s*\(\s*[6-9][0-9]{1,}",
            r"time\.sleep\s*\(\s*[1-9][0-9]{2,}",
            r"Start-Sleep\s+-[sS]\s+[6-9][0-9]",
            r"timeout\s+/t\s+[6-9][0-9]",
        ],
        file_types=[".py", ".bat", ".ps1"],
    ),

    # ── Category 6: Pickle / model exploits ──────────────────────────────────

    Pattern(
        name="unsafe_pickle_load",
        category="model_exploit",
        description="pickle.loads from untrusted source — .pkl files execute arbitrary Python on load",
        severity=85,
        regexes=[
            r"pickle\.loads?\s*\(",
            r"torch\.load\s*\(.*pickle",
            r"__reduce__",
            r"__reduce_ex__",
        ],
        file_types=[".py"],
    ),

    # ── Category 7: HuggingFace-specific ─────────────────────────────────────

    Pattern(
        name="trust_remote_code_enabled",
        category="hf_exploit",
        description="trust_remote_code=True — executes arbitrary code from the repo on model load",
        severity=85,
        regexes=[
            r"trust_remote_code\s*=\s*True",
        ],
        file_types=[".py", ".md", ".txt", ".yaml", ".yml", ".json"],
    ),

    Pattern(
        name="pickle_checkpoint_detected",
        category="hf_exploit",
        description=".pkl/.pickle checkpoint file present — can execute code on torch.load()",
        severity=80,
        regexes=[r".*"],   # presence-based, checked by extension
        file_types=[".pkl", ".pickle"],
    ),

    Pattern(
        name="unsafe_torch_load",
        category="hf_exploit",
        description="torch.load() without weights_only=True — executes pickle bytecode on load",
        severity=88,
        regexes=[
            r"torch\.load\s*\([^)]*\)",
        ],
        file_types=[".py"],
    ),

    Pattern(
        name="config_auto_execute",
        category="hf_exploit",
        description="auto_model or pipeline with custom code class — can trigger remote execution",
        severity=75,
        regexes=[
            r"AutoModel\.from_pretrained\s*\([^)]*trust_remote_code",
            r"pipeline\s*\([^)]*trust_remote_code",
            r"from_pretrained\s*\([^)]*trust_remote_code",
        ],
        file_types=[".py", ".md"],
    ),

    Pattern(
        name="binary_model_with_code",
        category="hf_exploit",
        description=".bin model file alongside executable Python — possible trojanized checkpoint",
        severity=70,
        regexes=[r".*"],   # presence-based, checked by extension in HF context
        file_types=[".bin"],
    ),
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
            ext = self._get_extension(file_path)
            matches.extend(self._scan_single_file(file_path, content, ext))
        return matches

    def _scan_single_file(self, file_path: str, content: str, ext: str) -> list[PatternMatch]:
        matches: list[PatternMatch] = []
        in_test = _is_test_or_docs(file_path)

        for pattern in self.patterns:
            if ext not in pattern.file_types:
                continue

            # Presence-based patterns (file extension is the signal)
            if pattern.name in (
                "suspicious_bat_in_ai_repo",
                "pickle_checkpoint_detected",
                "binary_model_with_code",
            ):
                if in_test:
                    continue
                matches.append(PatternMatch(
                    category=pattern.category,
                    pattern_name=pattern.name,
                    description=pattern.description,
                    file_path=file_path,
                    severity=pattern.severity,
                    snippet=f"File type: {ext}",
                ))
                continue

            # Regex-based patterns — skip test/docs paths for low-severity hits
            for regex in pattern.regexes:
                found = self._regex_scan(content, regex, file_path, pattern, in_test)
                matches.extend(found)

        if ext == ".py":
            matches.extend(self._ast_scan(content, file_path))

        return matches

    def _regex_scan(
        self, content: str, regex: str, file_path: str, pattern: Pattern, in_test: bool
    ) -> list[PatternMatch]:
        # Suppress low-severity hits in test/docs paths
        if in_test and pattern.severity < 90:
            return []
        matches = []
        try:
            for i, line in enumerate(content.splitlines(), start=1):
                if re.search(regex, line, re.IGNORECASE):
                    matches.append(PatternMatch(
                        category=pattern.category,
                        pattern_name=pattern.name,
                        description=pattern.description,
                        file_path=file_path,
                        line_number=i,
                        severity=pattern.severity,
                        snippet=line.strip()[:200],
                    ))
                    break  # one match per pattern per file
        except re.error as e:
            logger.warning(f"Bad regex {regex!r}: {e}")
        return matches

    def _ast_scan(self, content: str, file_path: str) -> list[PatternMatch]:
        matches = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return matches

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)

                # exec/eval wrapping b64decode
                if func_name in ("exec", "eval"):
                    for arg in node.args:
                        if isinstance(arg, ast.Call):
                            inner = self._get_call_name(arg)
                            if "b64decode" in (inner or ""):
                                matches.append(PatternMatch(
                                    category="obfuscation",
                                    pattern_name="ast_exec_b64decode",
                                    description="AST: exec/eval wrapping base64.b64decode — payload execution",
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    severity=95,
                                    snippet=f"{func_name}(base64.b64decode(...)) at line {node.lineno}",
                                ))

                # subprocess launching shell
                if func_name in ("subprocess.run", "subprocess.Popen", "os.system"):
                    src = ast.unparse(node)
                    if "powershell" in src.lower() or "cmd.exe" in src.lower():
                        matches.append(PatternMatch(
                            category="system_exec",
                            pattern_name="ast_subprocess_shell",
                            description="AST: subprocess launching shell (powershell/cmd.exe)",
                            file_path=file_path,
                            line_number=node.lineno,
                            severity=92,
                            snippet=src[:200],
                        ))

                # torch.load without weights_only=True
                if func_name == "torch.load":
                    kwargs = {kw.arg for kw in node.keywords}
                    if "weights_only" not in kwargs:
                        matches.append(PatternMatch(
                            category="hf_exploit",
                            pattern_name="ast_torch_load_unsafe",
                            description="AST: torch.load() missing weights_only=True — unsafe pickle execution",
                            file_path=file_path,
                            line_number=node.lineno,
                            severity=88,
                            snippet=f"torch.load() at line {node.lineno}",
                        ))

        return matches

    def _get_call_name(self, node: ast.Call) -> str | None:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return None

    def _get_extension(self, path: str) -> str:
        if "." not in path:
            return ""
        return "." + path.rsplit(".", 1)[-1].lower()


# ── Weighted trust scoring ────────────────────────────────────────────────────

# How much each category contributes to the final deduction
_CATEGORY_WEIGHTS = {
    "hf_exploit":     1.4,   # HF-specific attacks weighted up
    "model_exploit":  1.3,
    "system_exec":    1.3,
    "network":        1.2,
    "obfuscation":    1.1,
    "evasion":        1.0,
    "file_behaviour": 0.6,   # presence signals weighted down
    "account":        0.5,
}

# Single finding in these categories is an instant ceiling
_INSTANT_DANGEROUS = {"system_exec", "hf_exploit"}
_INSTANT_DANGEROUS_THRESHOLD = 90   # severity must also be >= this


def calculate_trust_score(matches: list[PatternMatch]) -> int:
    """
    Returns 0 (dangerous) to 100 (safe).
    Uses category-weighted deductions with diminishing returns.
    High-severity hits in critical categories trigger instant DANGEROUS ceiling.
    """
    if not matches:
        return 100

    # Instant dangerous: one critical finding in a high-risk category
    for m in matches:
        if (
            m.category in _INSTANT_DANGEROUS
            and m.severity >= _INSTANT_DANGEROUS_THRESHOLD
        ):
            return 15  # DANGEROUS range, not zero (leaves room for gradation)

    score = 100.0
    sorted_matches = sorted(matches, key=lambda m: m.severity, reverse=True)

    for i, match in enumerate(sorted_matches):
        weight = _CATEGORY_WEIGHTS.get(match.category, 1.0)
        diminish = 1.0 / (1 + i * 0.3)
        deduction = (match.severity / 100) * 40 * weight * diminish
        score -= deduction

    return max(0, round(score))