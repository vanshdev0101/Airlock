from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScanRecord(Base):
    __tablename__ = "scan_records"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    repo_url: Mapped[str] = mapped_column(
        String(500)
    )

    repo_name: Mapped[str] = mapped_column(
        String(255)
    )

    trust_level: Mapped[str] = mapped_column(
        String(50)
    )

    trust_score: Mapped[int] = mapped_column(
        Integer
    )

    summary: Mapped[str] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )