import re
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class TrustLevel(str, Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    DANGEROUS = "dangerous"


_URL_RE = re.compile(
    r"^https://(github\.com/[\w.\-]+/[\w.\-]+|huggingface\.co/[\w.\-]+/[\w.\-]+)"
)


class ScanRequest(BaseModel):
    repo_url: str

    @field_validator("repo_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not _URL_RE.match(v):
            raise ValueError(
                "Must be a full GitHub or HuggingFace repo URL. "
                "Example: https://github.com/owner/repo"
            )
        return v


class PatternMatch(BaseModel):
    category: str
    pattern_name: str
    description: str
    file_path: str
    line_number: int | None = None
    severity: int
    snippet: str | None = None
    # Signals with no legitimate use in a model/library repo. Only these may
    # short-circuit the trust score to "dangerous" — see calculate_trust_score.
    malware_grade: bool = False


# Fix 4: AccountInfo lives in scan.py — fetcher imports from here, no circular dep
class AccountInfo(BaseModel):
    username: str
    account_age_days: int | None = None
    total_repos: int | None = None
    is_new_account: bool
    is_typosquat: bool
    typosquat_target: str | None = None


class ScanResult(BaseModel):
    url: str
    repo_name: str
    scanned_at: datetime
    trust_level: TrustLevel
    trust_score: int
    account_info: AccountInfo
    matches: list[PatternMatch] = Field(default_factory=list)
    files_scanned: int
    summary: str
    recommendations: list[str] = Field(default_factory=list)


class ScanResponse(BaseModel):
    success: bool
    result: ScanResult | None = None
    error: str | None = None