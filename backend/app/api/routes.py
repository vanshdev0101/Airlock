from fastapi import APIRouter, HTTPException

from app.orchestrator.orchestrator import ScanOrchestrator
from app.scanner.scan import ScanRequest, ScanResponse

router = APIRouter()
_orchestrator = ScanOrchestrator()


@router.post("/scan", response_model=ScanResponse)
async def scan_repo(request: ScanRequest) -> ScanResponse:
    """Scan a Hugging Face or GitHub repository URL."""
    result = await _orchestrator.scan(request.repo_url)
    return result


@router.get("/health")
async def health():
    return {"status": "ok", "service": "repoguard"}