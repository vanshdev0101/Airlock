import logging

from sqlalchemy import desc, func, select

from app.db.session import AsyncSessionLocal
from app.models.finding import Finding
from app.models.scan_record import ScanRecord
from app.scanner.scan import ScanResult

logger = logging.getLogger(__name__)


async def save_scan(result: ScanResult) -> int | None:
    """Persist a completed scan and its findings. Non-fatal on failure.

    Returns the new scan id so the caller can link to it.
    """
    try:
        async with AsyncSessionLocal() as session:
            record = ScanRecord(
                repo_url=result.url,
                repo_name=result.repo_name,
                trust_level=result.trust_level.value,
                trust_score=result.trust_score,
                summary=result.summary,
                files_scanned=result.files_scanned,
                findings=[
                    Finding(
                        category=m.category,
                        pattern_name=m.pattern_name,
                        description=m.description,
                        file_path=m.file_path,
                        line_number=m.line_number,
                        severity=m.severity,
                        snippet=m.snippet,
                        malware_grade=m.malware_grade,
                    )
                    for m in result.matches
                ],
            )
            session.add(record)
            await session.commit()
            logger.info(
                "Saved scan %s (%d findings)", result.repo_name, len(result.matches)
            )
            return record.id
    except Exception as e:
        logger.error(f"Failed to save scan: {e}")
        return None


# Fix 6: query for history
async def get_recent_scans(limit: int = 20) -> list[dict]:
    try:
        async with AsyncSessionLocal() as session:
            # Count findings per scan in the query rather than loading them
            # all — the history list only needs the number.
            counts = (
                select(Finding.scan_id, func.count(Finding.id).label("n"))
                .group_by(Finding.scan_id)
                .subquery()
            )
            rows = await session.execute(
                select(ScanRecord, func.coalesce(counts.c.n, 0))
                .outerjoin(counts, counts.c.scan_id == ScanRecord.id)
                .order_by(desc(ScanRecord.created_at))
                .limit(limit)
            )
            return [
                {
                    "id": r.id,
                    "repo_name": r.repo_name,
                    "repo_url": r.repo_url,
                    "trust_level": r.trust_level,
                    "trust_score": r.trust_score,
                    "summary": r.summary,
                    "files_scanned": r.files_scanned,
                    "finding_count": n,
                    "scanned_at": r.created_at.isoformat() + "Z",
                }
                for r, n in rows.all()
            ]
    except Exception as e:
        logger.error(f"Failed to fetch scan history: {e}")
        return []


async def get_scan(scan_id: int) -> dict | None:
    """One scan with its findings, severest first."""
    try:
        async with AsyncSessionLocal() as session:
            record = await session.get(ScanRecord, scan_id)
            if record is None:
                return None
            findings = sorted(record.findings, key=lambda f: f.severity, reverse=True)
            return {
                "id": record.id,
                "repo_name": record.repo_name,
                "repo_url": record.repo_url,
                "trust_level": record.trust_level,
                "trust_score": record.trust_score,
                "summary": record.summary,
                "files_scanned": record.files_scanned,
                "scanned_at": record.created_at.isoformat() + "Z",
                "findings": [
                    {
                        "category": f.category,
                        "pattern_name": f.pattern_name,
                        "description": f.description,
                        "file_path": f.file_path,
                        "line_number": f.line_number,
                        "severity": f.severity,
                        "snippet": f.snippet,
                        "malware_grade": f.malware_grade,
                    }
                    for f in findings
                ],
            }
    except Exception as e:
        logger.error(f"Failed to fetch scan {scan_id}: {e}")
        return None
