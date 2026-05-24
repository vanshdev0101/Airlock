from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TrustLevel(str, Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    DANGEROUS = "dangerous"


class ScanRequest(BaseModel):
    repo_url: str


class PatternMatch(BaseModel):
    category: str
    pattern_name: str
    description: str
    file_path: str

    line_number: int | None = None

    severity: int

    snippet: str | None = None


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