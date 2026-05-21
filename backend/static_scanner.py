"""
Static analysis scanner for RepoGuard.
Detects malicious patterns in repo files using regex + AST parsing.
Does NOT execute any code — purely reads and analyses.
"""

import re
import ast
import logging
from dataclasses import dataclass
from scan import PatternMatch

logger = logging.getLogger(__name__)


@dataclass
class Pattern:
    name: str
    category: str
    description: str
    severity: int
    regexes: list[str]
    file_types: list[str]   # which file extensions to check


# ── All patterns we detect ───────────────────────────────────────────────────

PATTERNS: list[Pattern] = [

    # ── Category 1: Obfuscation ──────────────────────────────────────────────

    Pattern(
        name="base64_decode_exec",
        category="obfuscation",
        description="Base64 decoding combined with exec/eval — classic payload hiding technique used in the OpenAI Hugging Face attack",
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
        description="Base64 encoded string being decoded at runtime — commonly used to hide URLs, commands, or payloads",
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
        description="Long hex-encoded string — used to hide binary payloads or shellcode from visual inspection",
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
        description="eval() or exec() called on a dynamic or constructed string — executing unknown code at runtime",
        severity=85,
        regexes=[
            r"eval\s*\(\s*compile\s*\(",
            r"exec\s*\(\s*__import__",
            r"eval\s*\(\s*bytes",
            r"exec\s*\(\s*bytes",
        ],
        file_types=[".py"],
    ),

    # ── Category 2: Network calls ─────────────────────────────────────────────

    Pattern(
        name="ssl_verification_disabled",
        category="network",
        description="SSL certificate verification explicitly disabled — allows connections to attacker-controlled servers with fake certs",
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
        description="Downloading and executing content from an external URL — could be fetching a payload from a C2 server",
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
        description="Fetching a URL from a paste/JSON service then executing the result — used to hide the real C2 server address one hop away",
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
        description="Reading sensitive local files (SSH keys, .env, browser data) and sending them to a remote server",
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
        description="Python script launching PowerShell — classic two-stage loader pattern where Python fetches and PowerShell executes with elevated privileges",
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
        description="Adding files to Windows Defender exclusion list — used exclusively by malware to avoid detection before executing payload",
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
        description="Attempting to gain administrator/root privileges silently — no legitimate model loader needs elevated access",
        severity=97,
        regexes=[
            r"runas\s*/user:Administrator",
            r"Start-Process.*-Verb\s+RunAs",
            r"ShellExecute.*runas",
            r"sudo\s+-S",
            r"UAC",
        ],
        file_types=[".bat", ".ps1", ".py", ".sh"],
    ),

    Pattern(
        name="persistence_mechanism",
        category="system_exec",
        description="Creating scheduled tasks or registry entries to survive reboots — only malware needs to persist on the system",
        severity=95,
        regexes=[
            r"schtasks\s*/create",
            r"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            r"HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            r"crontab\s+-[le]",
            r"launchd.*plist",
            r"systemctl\s+enable",
        ],
        file_types=[".bat", ".ps1", ".py", ".sh"],
    ),

    # ── Category 4: Suspicious file behaviour ────────────────────────────────

    Pattern(
        name="self_deletion",
        category="file_behaviour",
        description="Script deletes itself after running — used by malware to remove evidence of execution",
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
        description=".bat or .ps1 file present in an AI model repo — these have no legitimate purpose in a machine learning project",
        severity=75,
        regexes=[
            r".*",  # just the presence of the file is the signal — checked by file type
        ],
        file_types=[".bat", ".ps1"],
    ),

    # ── Category 5: Anti-analysis evasion ────────────────────────────────────

    Pattern(
        name="vm_detection",
        category="evasion",
        description="Checking for virtual machine or sandbox environment — malware does this to avoid running during security analysis",
        severity=93,
        regexes=[
            r"VMware",
            r"VirtualBox",
            r"VBOX",
            r"QEMU",
            r"Wireshark",
            r"OllyDbg",
            r"x64dbg",
            r"psutil.*cpu_count.*[<=>]=?\s*[12]",
        ],
        file_types=[".py", ".bat", ".ps1"],
    ),

    Pattern(
        name="sandbox_sleep_delay",
        category="evasion",
        description="Unusually long sleep/delay — used to outlast automated sandbox analysis timeouts before executing payload",
        severity=60,
        regexes=[
            r"time\.sleep\s*\(\s*[6-9][0-9]{1,}",   # sleep > 60 seconds
            r"time\.sleep\s*\(\s*[1-9][0-9]{2,}",    # sleep > 100 seconds
            r"Start-Sleep\s+-[sS]\s+[6-9][0-9]",
            r"timeout\s+/t\s+[6-9][0-9]",
        ],
        file_types=[".py", ".bat", ".ps1"],
    ),

    # ── Category 6: Pickle / model file exploits ──────────────────────────────

    Pattern(
        name="unsafe_pickle_load",
        category="model_exploit",
        description="Loading a pickle file from an untrusted source — .pkl files can contain executable Python code that runs on load",
        severity=85,
        regexes=[
            r"pickle\.loads?\s*\(",
            r"torch\.load\s*\(.*pickle",
            r"__reduce__",
            r"__reduce_ex__",
        ],
        file_types=[".py"],
    ),
]


# ── Scanner class ─────────────────────────────────────────────────────────────

class StaticScanner:
    """
    Scans a dict of {filename: content} and returns a list of PatternMatch.
    Uses both regex and Python AST parsing.
    """

    def __init__(self):
        self.patterns = PATTERNS

    def scan_files(self, files: dict[str, str]) -> list[PatternMatch]:
        """Main entry point. files = {path: content}"""
        matches: list[PatternMatch] = []

        for file_path, content in files.items():
            if not content:
                continue
            ext = self._get_extension(file_path)
            file_matches = self._scan_single_file(file_path, content, ext)
            matches.extend(file_matches)

        return matches

    def _scan_single_file(
        self, file_path: str, content: str, ext: str
    ) -> list[PatternMatch]:
        matches: list[PatternMatch] = []

        for pattern in self.patterns:
            if ext not in pattern.file_types:
                continue

            # Special case: .bat/.ps1 presence is itself the signal
            if pattern.name == "suspicious_bat_in_ai_repo":
                if ext in [".bat", ".ps1"]:
                    matches.append(PatternMatch(
                        category=pattern.category,
                        pattern_name=pattern.name,
                        description=pattern.description,
                        file_path=file_path,
                        severity=pattern.severity,
                        snippet=f"File type: {ext}",
                    ))
                continue

            # Regex scan
            for regex in pattern.regexes:
                found = self._regex_scan(content, regex, file_path, pattern)
                matches.extend(found)

        # AST-based scan for Python files
        if ext == ".py":
            ast_matches = self._ast_scan(content, file_path)
            matches.extend(ast_matches)

        return matches

    def _regex_scan(
        self, content: str, regex: str, file_path: str, pattern: Pattern
    ) -> list[PatternMatch]:
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
                    break  # one match per pattern per file is enough
        except re.error as e:
            logger.warning(f"Bad regex {regex!r}: {e}")
        return matches

    def _ast_scan(self, content: str, file_path: str) -> list[PatternMatch]:
        """
        Parse Python source into an AST and look for dangerous call chains
        that regex alone might miss (e.g. exec(base64.b64decode(x)) split
        across multiple lines).
        """
        matches = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return matches  # not valid Python, skip

        for node in ast.walk(tree):
            # Detect: exec(base64.b64decode(...)) or eval(base64.b64decode(...))
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name in ("exec", "eval"):
                    for arg in node.args:
                        if isinstance(arg, ast.Call):
                            inner = self._get_call_name(arg)
                            if "b64decode" in (inner or ""):
                                matches.append(PatternMatch(
                                    category="obfuscation",
                                    pattern_name="ast_exec_b64decode",
                                    description="AST confirmed: exec/eval wrapping base64.b64decode — payload execution pattern",
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    severity=95,
                                    snippet=f"{func_name}(base64.b64decode(...)) at line {node.lineno}",
                                ))

            # Detect: subprocess calls with 'powershell' in args
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name in ("subprocess.run", "subprocess.Popen", "os.system"):
                    src = ast.unparse(node)
                    if "powershell" in src.lower() or "cmd.exe" in src.lower():
                        matches.append(PatternMatch(
                            category="system_exec",
                            pattern_name="ast_subprocess_shell",
                            description="AST confirmed: subprocess launching shell (powershell/cmd.exe)",
                            file_path=file_path,
                            line_number=node.lineno,
                            severity=92,
                            snippet=src[:200],
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


# ── Score calculator ──────────────────────────────────────────────────────────

def calculate_trust_score(matches: list[PatternMatch]) -> int:
    """
    Returns 0 (most dangerous) to 100 (safest).
    Starts at 100 and deducts based on findings.
    Uses diminishing deductions so one critical finding = dangerous
    but doesn't go below 0.
    """
    if not matches:
        return 100

    score = 100
    # Sort by severity descending so worst hits first
    sorted_matches = sorted(matches, key=lambda m: m.severity, reverse=True)

    for i, match in enumerate(sorted_matches):
        # Diminishing returns: each additional finding hurts less
        multiplier = 1.0 / (1 + i * 0.3)
        deduction = (match.severity / 100) * 40 * multiplier
        score -= deduction

    return max(0, round(score))
