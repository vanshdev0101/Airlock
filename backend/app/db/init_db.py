from app.db.base import Base
from app.db.session import engine
import app.models.scan_record  # noqa: F401 — registers ScanRecord with Base


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)