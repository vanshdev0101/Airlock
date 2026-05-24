from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import RepoGuardError, RateLimitError
from app.core.exception_handlers import (
    repoguard_exception_handler,
    rate_limit_exception_handler,
)
from app.db.init_db import init_db
from app.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="RepoGuard",
    description="AI-powered security scanner for Hugging Face and GitHub repositories",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

app.add_exception_handler(RepoGuardError, repoguard_exception_handler)
app.add_exception_handler(RateLimitError, rate_limit_exception_handler)


@app.get("/")
async def root():
    return {"message": "RepoGuard API is running. POST /api/scan to scan a repo."}