from fastapi import APIRouter
from app.orchestrator.orchestrator import ScanOrchestrator
from app.scanner.scan import ScanRequest, ScanResponse
from app.db.crud import get_recent_scans

router = APIRouter()
_orchestrator = ScanOrchestrator()


@router.post("/scan", response_model=ScanResponse)
async def scan_repo(request: ScanRequest) -> ScanResponse:
    """Scan a Hugging Face or GitHub repository URL."""
    return await _orchestrator.scan(request.repo_url)


# Fix 6: scan history endpoint
@router.get("/scans")
async def scan_history(limit: int = 20):
    """Return the most recent scan records from DB."""
    records = await get_recent_scans(limit=limit)
    return {"scans": records}


@router.get("/health")
async def health():
    return {"status": "ok", "service": "repoguard"}