"""persist individual findings, and record how many files a scan read

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("pattern_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("malware_grade", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scan_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"])
    op.create_index("ix_findings_pattern_name", "findings", ["pattern_name"])

    # Rows that predate this column were scanned, we just did not record how
    # much. 0 is honest: "unknown", not "none".
    op.add_column(
        "scan_records",
        sa.Column("files_scanned", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("scan_records", "files_scanned")
    op.drop_index("ix_findings_pattern_name", table_name="findings")
    op.drop_index("ix_findings_scan_id", table_name="findings")
    op.drop_table("findings")
