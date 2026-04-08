"""add soft delete for objects"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_soft_delete_objects"
down_revision = "0002_advanced_bucket_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("files") as batch_op:
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table("files") as batch_op:
        batch_op.alter_column("is_deleted", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("files") as batch_op:
        batch_op.drop_column("is_deleted")
