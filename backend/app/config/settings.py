from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ─────────────────────────────────────────────────────────────
    # App
    # ─────────────────────────────────────────────────────────────

    app_name: str = Field(
        default="RepoGuard",
        alias="APP_NAME",
    )

    app_version: str = Field(
        default="0.1.0",
        alias="APP_VERSION",
    )

    env: str = Field(
        default="development",
        alias="ENV",
    )

    debug: bool = Field(
        default=False,
        alias="DEBUG",
    )

    # ─────────────────────────────────────────────────────────────
    # API Keys
    # ─────────────────────────────────────────────────────────────

    anthropic_api_key: str | None = Field(
        default=None,
        alias="ANTHROPIC_API_KEY",
    )

    github_token: str | None = Field(
        default=None,
        alias="GITHUB_TOKEN",
    )

    hf_token: str | None = Field(
        default=None,
        alias="HF_TOKEN",
    )

    # ─────────────────────────────────────────────────────────────
    # API URLs
    # ─────────────────────────────────────────────────────────────

    github_api_url: str = Field(
        default="https://api.github.com",
        alias="GITHUB_API_URL",
    )

    hf_api_url: str = Field(
        default="https://huggingface.co/api",
        alias="HF_API_URL",
    )

    # ─────────────────────────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────────────────────────

    database_url: str = Field(
        default="sqlite+aiosqlite:///./repoguard.db",
        alias="DATABASE_URL",
    )

    # ─────────────────────────────────────────────────────────────
    # Rate Limiting
    # ─────────────────────────────────────────────────────────────

    rate_limit_requests: int = Field(
        default=10,
        alias="RATE_LIMIT_REQUESTS",
    )

    rate_limit_window: int = Field(
        default=60,
        alias="RATE_LIMIT_WINDOW",
    )

    # ─────────────────────────────────────────────────────────────
    # Cache
    # ─────────────────────────────────────────────────────────────

    cache_ttl_seconds: int = Field(
        default=3600,
        alias="CACHE_TTL_SECONDS",
    )

    cache_max_size: int = Field(
        default=500,
        alias="CACHE_MAX_SIZE",
    )

    # ─────────────────────────────────────────────────────────────
    # CORS
    # ─────────────────────────────────────────────────────────────

    # Browsers treat localhost and 127.0.0.1 as distinct origins, and Vite
    # prints both. Allow both spellings or the app silently 400s on every
    # request depending on which URL the developer happened to open.
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        alias="CORS_ORIGINS",
    )

    # ─────────────────────────────────────────────────────────────
    # Scanner Limits
    # ─────────────────────────────────────────────────────────────

    max_files_per_scan: int = Field(
        default=100,
        alias="MAX_FILES_PER_SCAN",
    )

    max_file_size_kb: int = Field(
        default=512,
        alias="MAX_FILE_SIZE_KB",
    )

    scan_timeout_seconds: int = Field(
        default=30,
        alias="SCAN_TIMEOUT_SECONDS",
    )

    # ─────────────────────────────────────────────────────────────
    # Trust / Reputation
    # ─────────────────────────────────────────────────────────────

    trusted_domains: list[str] = Field(
        default_factory=lambda: [
            "huggingface.co",
            "github.com",
            "pypi.org",
            "pytorch.org",
            "tensorflow.org",
            "cdn.jsdelivr.net",
            "raw.githubusercontent.com",
        ],
        alias="TRUSTED_DOMAINS",
    )

    trusted_orgs: list[str] = Field(
        default_factory=lambda: [
            "openai",
            "meta-llama",
            "google",
            "microsoft",
            "huggingface",
            "mistralai",
            "anthropic",
            "stabilityai",
            "tiiuae",
            "EleutherAI",
        ],
        alias="TRUSTED_ORGS",
    )

    # ─────────────────────────────────────────────────────────────
    # Validators
    # ─────────────────────────────────────────────────────────────

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {
            "development",
            "staging",
            "production",
            "test",
        }

        if v not in allowed:
            raise ValueError(
                f"Invalid ENV '{v}'. Must be one of: {sorted(allowed)}"
            )

        return v

    # ─────────────────────────────────────────────────────────────
    # Environment Helpers
    # ─────────────────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_development(self) -> bool:
        return self.env == "development"

    # ─────────────────────────────────────────────────────────────
    # Pydantic Settings Config
    # ─────────────────────────────────────────────────────────────

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        frozen=True,
    )


@lru_cache
def get_settings() -> "Settings":
    return Settings()


settings: Settings = get_settings()