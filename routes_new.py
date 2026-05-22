from fastapi import APIRouter
from ..orchestrator import ScanOrchestrator
from ..scanner import ScanRequest, ScanResponse

router = APIRouter()
orchestrator = ScanOrchestrator()


@router.post("/scan", response_model=ScanResponse)
async def scan_repo(request: ScanRequest) -> ScanResponse:
    """
    Scan a Hugging Face or GitHub repository URL.
    Returns a trust score and detailed findings report.
    """
    return await orchestrator.scan(request.url)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "repoguard"}
