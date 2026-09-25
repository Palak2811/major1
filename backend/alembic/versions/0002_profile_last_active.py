"""profiles.last_active_on for study streaks

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 builds from current metadata, so a fresh DB may already have the column.
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("profiles")}
    if "last_active_on" not in cols:
        op.add_column("profiles", sa.Column("last_active_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "last_active_on")
