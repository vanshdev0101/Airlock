from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    hf_token: str = Field(default="", alias="HF_TOKEN")

    database_url: str = Field(
        default="sqlite+aiosqlite:///./repoguard.db",
        alias="DATABASE_URL"
    )

    environment: str = Field(
        default="development",
        alias="ENV"
    )

    max_file_size_kb: int = Field(default=500, alias="MAX_FILE_SIZE_KB")
    max_files_per_repo: int = Field(default=50, alias="MAX_FILES_PER_REPO")
    scan_timeout_seconds: int = Field(default=60, alias="SCAN_TIMEOUT_SECONDS")

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    trusted_domains: list[str] = [
        "huggingface.co",
        "github.com",
        "pypi.org",
        "pytorch.org",
        "tensorflow.org",
        "cdn.jsdelivr.net",
        "raw.githubusercontent.com",
    ]

    trusted_orgs: list[str] = [
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
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()