import json
import logging
from app.db.session import AsyncSessionLocal
from app.models.scan_record import ScanRecord
from app.scanner.scan import ScanResult

logger = logging.getLogger(__name__)


async def save_scan(result: ScanResult) -> None:
    """Persist a completed scan to SQLite. Non-fatal — logs on failure."""
    try:
        async with AsyncSessionLocal() as session:
            record = ScanRecord(
                repo_url=result.url,
                repo_name=result.repo_name,
                trust_level=result.trust_level.value,
                trust_score=result.trust_score,
                summary=result.summary,
            )
            session.add(record)
            await session.commit()
            logger.info(f"Saved scan record for {result.repo_name}")
    except Exception as e:
        logger.error(f"Failed to save scan record: {e}")