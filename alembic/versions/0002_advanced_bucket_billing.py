"""add advanced bucket billing counters"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_advanced_bucket_billing"
down_revision = "0001_add_buckets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("buckets") as batch_op:
        batch_op.add_column(sa.Column("current_storage_bytes", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("ingress_bytes", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("egress_bytes", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("internal_transfer_bytes", sa.Integer(), nullable=False, server_default="0"))

    op.execute(
        sa.text(
            """
            UPDATE buckets
            SET current_storage_bytes = COALESCE((
                SELECT SUM(files.size)
                FROM files
                WHERE files.bucket_id = buckets.id
            ), 0)
            """
        )
    )

    with op.batch_alter_table("buckets") as batch_op:
        batch_op.alter_column("current_storage_bytes", server_default=None)
        batch_op.alter_column("ingress_bytes", server_default=None)
        batch_op.alter_column("egress_bytes", server_default=None)
        batch_op.alter_column("internal_transfer_bytes", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("buckets") as batch_op:
        batch_op.drop_column("internal_transfer_bytes")
        batch_op.drop_column("egress_bytes")
        batch_op.drop_column("ingress_bytes")
        batch_op.drop_column("current_storage_bytes")
