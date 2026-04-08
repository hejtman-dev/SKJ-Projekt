"""add bucket request billing counters"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_bucket_request_billing"
down_revision = "0003_soft_delete_objects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("buckets") as batch_op:
        batch_op.add_column(sa.Column("count_write_requests", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("count_read_requests", sa.Integer(), nullable=False, server_default="0"))

    with op.batch_alter_table("buckets") as batch_op:
        batch_op.alter_column("count_write_requests", server_default=None)
        batch_op.alter_column("count_read_requests", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("buckets") as batch_op:
        batch_op.drop_column("count_read_requests")
        batch_op.drop_column("count_write_requests")
