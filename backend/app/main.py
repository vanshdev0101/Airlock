from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router          # was: from app.api.routes import router
from .config import settings        # was: hardcoded list

app = FastAPI(
    title="RepoGuard",
    description="AI-powered security scanner for Hugging Face and GitHub repositories",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,   # driven by config now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "RepoGuard API is running. POST /api/scan to scan a repo."}