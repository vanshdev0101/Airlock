from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    RepoGuardError,
    RateLimitError,
)


async def repoguard_exception_handler(
    request: Request,
    exc: RepoGuardError,
):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": str(exc),
        },
    )


async def rate_limit_exception_handler(
    request: Request,
    exc: RateLimitError,
):
    return JSONResponse(
        status_code=429,
        headers={
            "Retry-After": str(exc.retry_after)
        },
        content={
            "success": False,
            "error": str(exc),
            "retry_after": exc.retry_after,
        },
    )