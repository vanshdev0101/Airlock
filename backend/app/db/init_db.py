"""Bring the database up to the current schema at startup.

This used to call `Base.metadata.create_all`, which silently does nothing when
a table already exists — fine for adding a table, useless for changing one.
Migrations replace it so schema changes are explicit and reversible.

Databases created by the old `create_all` have the 0001 schema but no
`alembic_version` table, so they are *stamped* at the baseline rather than
upgraded to it; otherwise the first migration would try to create a
scan_records table that is already there.
"""

import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db.session import engine

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
BASELINE_REVISION = "0001"


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


def _table_names(sync_conn) -> set[str]:
    return set(inspect(sync_conn).get_table_names())


async def init_db() -> None:
    async with engine.begin() as conn:
        tables = await conn.run_sync(_table_names)

    cfg = _alembic_config()

    if "scan_records" in tables and "alembic_version" not in tables:
        logger.info("Adopting pre-migration database at revision %s", BASELINE_REVISION)
        await asyncio.to_thread(command.stamp, cfg, BASELINE_REVISION)

    # Alembic's env.py opens its own engine and calls asyncio.run, so it has
    # to run off the event loop.
    await asyncio.to_thread(command.upgrade, cfg, "head")
