"""
Findings must survive the scan that produced them.

Scans used to persist only the score and summary, which meant a history row
could never be drilled into and the scanner could not be measured against its
own past results. These tests pin the round trip.
"""

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import crud
from app.db.base import Base
from app.models import finding as _finding  # noqa: F401 — registers the table
from app.models import scan_record as _scan_record  # noqa: F401
from app.scanner.scan import AccountInfo, PatternMatch, ScanResult, TrustLevel


@pytest_asyncio.fixture
async def db(tmp_path, monkeypatch):
    """A throwaway database wired into the crud module for one test."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(
        crud,
        "AsyncSessionLocal",
        async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False),
    )
    yield
    await engine.dispose()


def _result(matches=(), score=42, level=TrustLevel.SUSPICIOUS) -> ScanResult:
    return ScanResult(
        url="https://github.com/someone/thing",
        repo_name="someone/thing",
        scanned_at=datetime.now(timezone.utc),
        trust_level=level,
        trust_score=score,
        account_info=AccountInfo(username="someone", is_new_account=False, is_typosquat=False),
        matches=list(matches),
        files_scanned=17,
        summary="a summary",
        recommendations=[],
    )


def _match(**kw) -> PatternMatch:
    base = dict(
        category="system_exec",
        pattern_name="defender_exclusion",
        description="Adding Windows Defender exclusion",
        file_path="install.ps1",
        line_number=12,
        severity=100,
        snippet="Add-MpPreference -ExclusionPath C:\\",
        malware_grade=True,
    )
    return PatternMatch(**{**base, **kw})


@pytest.mark.asyncio
async def test_findings_round_trip(db):
    scan_id = await crud.save_scan(_result([_match()]))
    assert scan_id is not None

    stored = await crud.get_scan(scan_id)
    assert stored is not None
    assert len(stored["findings"]) == 1

    f = stored["findings"][0]
    assert f["pattern_name"] == "defender_exclusion"
    assert f["file_path"] == "install.ps1"
    assert f["line_number"] == 12
    assert f["severity"] == 100
    assert f["malware_grade"] is True


@pytest.mark.asyncio
async def test_files_scanned_is_recorded(db):
    scan_id = await crud.save_scan(_result())
    assert (await crud.get_scan(scan_id))["files_scanned"] == 17


@pytest.mark.asyncio
async def test_findings_come_back_severest_first(db):
    matches = [
        _match(pattern_name="low_one", severity=30),
        _match(pattern_name="high_one", severity=95),
        _match(pattern_name="mid_one", severity=60),
    ]
    scan_id = await crud.save_scan(_result(matches))
    severities = [f["severity"] for f in (await crud.get_scan(scan_id))["findings"]]
    assert severities == [95, 60, 30]


@pytest.mark.asyncio
async def test_clean_scan_stores_no_findings(db):
    scan_id = await crud.save_scan(_result(score=100, level=TrustLevel.SAFE))
    assert (await crud.get_scan(scan_id))["findings"] == []


@pytest.mark.asyncio
async def test_history_carries_a_finding_count(db):
    await crud.save_scan(_result([_match(), _match(pattern_name="other")]))
    scans = await crud.get_recent_scans()
    assert len(scans) == 1
    assert scans[0]["finding_count"] == 2


@pytest.mark.asyncio
async def test_history_counts_zero_for_a_clean_scan(db):
    """An outer join must not drop scans that found nothing."""
    await crud.save_scan(_result(score=100, level=TrustLevel.SAFE))
    scans = await crud.get_recent_scans()
    assert len(scans) == 1
    assert scans[0]["finding_count"] == 0


@pytest.mark.asyncio
async def test_missing_scan_returns_none(db):
    assert await crud.get_scan(9999) is None
