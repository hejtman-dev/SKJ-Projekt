"""add bucket settings profile fields"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_bucket_settings_profile"
down_revision = "0004_bucket_request_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("buckets") as batch_op:
        batch_op.add_column(sa.Column("description", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("storage_limit_bytes", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("color", sa.String(length=32), nullable=False, server_default="teal"))
        batch_op.add_column(sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.execute(
        """
        UPDATE buckets
        SET storage_limit_bytes = COALESCE(
            (SELECT users.storage_quota_bytes FROM users WHERE users.id = buckets.user_id),
            0
        )
        """
    )

    with op.batch_alter_table("buckets") as batch_op:
        batch_op.alter_column("storage_limit_bytes", server_default=None)
        batch_op.alter_column("color", server_default=None)
        batch_op.alter_column("is_locked", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("buckets") as batch_op:
        batch_op.drop_column("is_locked")
        batch_op.drop_column("color")
        batch_op.drop_column("storage_limit_bytes")
        batch_op.drop_column("description")
