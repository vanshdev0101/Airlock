"""baseline: scan_records as create_all left it

This revision describes the schema that existed *before* migrations were
introduced, when app startup called `Base.metadata.create_all`. Databases
created that way are stamped at this revision rather than upgraded to it, so
the first real migration (0002) applies cleanly to both an existing dev
database and a brand new one.

Revision ID: 0001
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repo_url", sa.String(length=500), nullable=False),
        sa.Column("repo_name", sa.String(length=255), nullable=False),
        sa.Column("trust_level", sa.String(length=50), nullable=False),
        sa.Column("trust_score", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("scan_records")
