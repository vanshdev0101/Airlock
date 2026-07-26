from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Finding(Base):
    """One pattern match belonging to a scan.

    Scans used to persist only the score and summary, which meant history
    rows could not be drilled into, a repo could not be diffed against its
    previous scan, and the scanner's own false-positive rate could not be
    measured after the fact. Keeping the individual findings is what makes
    those possible.
    """

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)

    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scan_records.id", ondelete="CASCADE"),
        index=True,
    )

    category: Mapped[str] = mapped_column(String(50))
    pattern_name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(String(500))
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[int] = mapped_column(Integer)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    malware_grade: Mapped[bool] = mapped_column(Boolean, default=False)

    scan = relationship("ScanRecord", back_populates="findings")
