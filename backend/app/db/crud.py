import logging
from sqlalchemy import select, desc
from app.db.session import AsyncSessionLocal
from app.models.scan_record import ScanRecord
from app.scanner.scan import ScanResult

logger = logging.getLogger(__name__)


async def save_scan(result: ScanResult) -> None:
    """Persist a completed scan. Non-fatal on failure."""
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
            logger.info(f"Saved scan: {result.repo_name}")
    except Exception as e:
        logger.error(f"Failed to save scan: {e}")


# Fix 6: query for history
async def get_recent_scans(limit: int = 20) -> list[dict]:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ScanRecord)
                .order_by(desc(ScanRecord.created_at))
                .limit(limit)
            )
            records = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "repo_name": r.repo_name,
                    "repo_url": r.repo_url,
                    "trust_level": r.trust_level,
                    "trust_score": r.trust_score,
                    "summary": r.summary,
                    "scanned_at": r.created_at.isoformat() + "Z",
                }
                for r in records
            ]
    except Exception as e:
        logger.error(f"Failed to fetch scan history: {e}")
        return []