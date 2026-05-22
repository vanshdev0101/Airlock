from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    github_token: str = ""
    hf_token: str = ""
    database_url: str = "sqlite+aiosqlite:///./repoguard.db"
    environment: str = "development"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    max_file_size_kb: int = 500
    max_files_per_repo: int = 50
    scan_timeout_seconds: int = 60

    trusted_domains: list[str] = [
        "huggingface.co", "github.com", "pypi.org",
        "pytorch.org", "tensorflow.org",
        "cdn.jsdelivr.net", "raw.githubusercontent.com",
    ]
    trusted_orgs: list[str] = [
        "openai", "meta-llama", "google", "microsoft", "huggingface",
        "mistralai", "anthropic", "stabilityai", "tiiuae", "EleutherAI",
    ]

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
