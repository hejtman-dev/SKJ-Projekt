"""add buckets and bucket-backed files"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "0001_add_buckets"
down_revision = None
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def _create_users_table() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("storage_quota_bytes", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def _create_buckets_table() -> None:
    op.create_table(
        "buckets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_buckets_user_id_name"),
    )
    op.create_index(op.f("ix_buckets_user_id"), "buckets", ["user_id"], unique=False)


def _create_files_table() -> None:
    op.create_table(
        "files",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("bucket_id", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["buckets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_files_bucket_id"), "files", ["bucket_id"], unique=False)
    op.create_index(op.f("ix_files_user_id"), "files", ["user_id"], unique=False)


def _create_default_buckets(connection) -> dict[str, str]:
    user_ids = [
        row[0]
        for row in connection.execute(sa.text("SELECT id FROM users")).fetchall()
    ]
    bucket_by_user: dict[str, str] = {}
    timestamp = datetime.now(UTC).isoformat()

    for user_id in user_ids:
        bucket_id = str(uuid4())
        bucket_by_user[user_id] = bucket_id
        connection.execute(
            sa.text(
                """
                INSERT INTO buckets (id, user_id, name, created_at)
                VALUES (:id, :user_id, :name, :created_at)
                """
            ),
            {
                "id": bucket_id,
                "user_id": user_id,
                "name": "default",
                "created_at": timestamp,
            },
        )

    return bucket_by_user


def _backfill_file_buckets(connection, bucket_by_user: dict[str, str]) -> None:
    for user_id, bucket_id in bucket_by_user.items():
        connection.execute(
            sa.text(
                """
                UPDATE files
                SET bucket_id = :bucket_id
                WHERE user_id = :user_id
                """
            ),
            {"bucket_id": bucket_id, "user_id": user_id},
        )


def upgrade() -> None:
    bind = op.get_bind()
    table_names = _table_names(bind)

    if "users" not in table_names:
        _create_users_table()
        table_names.add("users")

    if "buckets" not in table_names:
        _create_buckets_table()
        table_names.add("buckets")

    if "files" not in table_names:
        _create_files_table()
        return

    file_columns = {column["name"] for column in sa.inspect(bind).get_columns("files")}
    if "bucket_id" not in file_columns:
        with op.batch_alter_table("files") as batch_op:
            batch_op.add_column(sa.Column("bucket_id", sa.String(length=64), nullable=True))

        bucket_by_user = _create_default_buckets(bind)
        _backfill_file_buckets(bind, bucket_by_user)

        with op.batch_alter_table("files") as batch_op:
            batch_op.alter_column("bucket_id", existing_type=sa.String(length=64), nullable=False)
            batch_op.create_foreign_key("fk_files_bucket_id_buckets", "buckets", ["bucket_id"], ["id"])
            batch_op.create_index("ix_files_bucket_id", ["bucket_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    table_names = _table_names(bind)

    if "files" in table_names:
        file_columns = {column["name"] for column in sa.inspect(bind).get_columns("files")}
        if "bucket_id" in file_columns:
            with op.batch_alter_table("files") as batch_op:
                batch_op.drop_index("ix_files_bucket_id")
                batch_op.drop_constraint("fk_files_bucket_id_buckets", type_="foreignkey")
                batch_op.drop_column("bucket_id")

    if "buckets" in table_names:
        op.drop_index(op.f("ix_buckets_user_id"), table_name="buckets")
        op.drop_table("buckets")
