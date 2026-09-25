"""submissions.mode (practice | run | submit | test)

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("submissions")}
    if "mode" not in cols:
        op.add_column("submissions", sa.Column("mode", sa.String(16), nullable=False,
                                               server_default="practice"))
        op.create_index("ix_submissions_mode", "submissions", ["mode"])


def downgrade() -> None:
    op.drop_index("ix_submissions_mode", "submissions")
    op.drop_column("submissions", "mode")
