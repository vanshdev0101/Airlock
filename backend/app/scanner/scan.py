from pydantic import BaseModel, HttpUrl
from enum import Enum
from datetime import datetime


class TrustLevel(str, Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    DANGEROUS = "dangerous"


class ScanRequest(BaseModel):
    url: str


class PatternMatch(BaseModel):
    category: str           # e.g. "obfuscation", "network", "system_exec"
    pattern_name: str       # e.g. "base64_decode"
    description: str        # human readable explanation
    file_path: str          # which file it was found in
    line_number: int | None = None
    severity: int           # 0-100 risk weight
    snippet: str | None = None  # the actual code snippet (truncated)


class AccountInfo(BaseModel):
    username: str
    account_age_days: int | None
    total_repos: int | None
    is_new_account: bool
    is_typosquat: bool
    typosquat_target: str | None = None


class ScanResult(BaseModel):
    url: str
    repo_name: str
    scanned_at: datetime
    trust_level: TrustLevel
    trust_score: int            # 0 = most dangerous, 100 = safest
    account_info: AccountInfo
    matches: list[PatternMatch]
    files_scanned: int
    summary: str                # LLM-generated plain English summary
    recommendations: list[str]  # what the user should do


class ScanResponse(BaseModel):
    success: bool
    result: ScanResult | None = None
    error: str | None = None
