"""Custom exception hierarchy for RepoGuard."""


class RepoGuardError(Exception):
    """Base exception for all RepoGuard errors."""


class FetchError(RepoGuardError):
    """Failed to fetch repository content."""


class ScanError(RepoGuardError):
    """Scan execution failed."""


class RateLimitError(RepoGuardError):
    """Too many requests from this client."""
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s.")


class CacheError(RepoGuardError):
    """Cache read/write failure (non-fatal, log and continue)."""


class InputValidationError(RepoGuardError):
    """Invalid input URL or parameters."""