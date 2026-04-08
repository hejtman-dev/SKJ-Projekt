from sqlalchemy import Boolean, Column, String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import UTC, datetime
from uuid import uuid4

try:
    from .database import Base
    from .settings import settings
except ImportError:
    from database import Base
    from settings import settings


class User(Base):
    __tablename__ = "users"

    id: str = Column(String(64), primary_key=True, default=lambda: str(uuid4()))
    username: str = Column(String(64), unique=True, nullable=False, index=True)
    email: str = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password: str = Column(String(255), nullable=False)
    storage_quota_bytes: int = Column(Integer, default=settings.storage_quota_bytes)

    buckets = relationship("Bucket", back_populates="owner", cascade="all, delete-orphan")
    files = relationship("File", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class Bucket(Base):
    __tablename__ = "buckets"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_buckets_user_id_name"),)

    id: str = Column(String(64), primary_key=True, default=lambda: str(uuid4()))
    user_id: str = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    name: str = Column(String(255), nullable=False)
    description: str | None = Column(String(500), nullable=True)
    storage_limit_bytes: int = Column(Integer, nullable=False, default=0)
    color: str = Column(String(32), nullable=False, default="teal")
    is_locked: bool = Column(Boolean, nullable=False, default=False)
    current_storage_bytes: int = Column(Integer, nullable=False, default=0)
    ingress_bytes: int = Column(Integer, nullable=False, default=0)
    egress_bytes: int = Column(Integer, nullable=False, default=0)
    internal_transfer_bytes: int = Column(Integer, nullable=False, default=0)
    count_write_requests: int = Column(Integer, nullable=False, default=0)
    count_read_requests: int = Column(Integer, nullable=False, default=0)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    owner = relationship("User", back_populates="buckets")
    files = relationship("File", back_populates="bucket")

    def __repr__(self) -> str:
        return (
            f"<Bucket(id={self.id}, user_id={self.user_id}, name={self.name}, "
            f"description={self.description}, storage_limit={self.storage_limit_bytes}, "
            f"color={self.color}, is_locked={self.is_locked}, "
            f"storage={self.current_storage_bytes}, ingress={self.ingress_bytes}, "
            f"egress={self.egress_bytes}, internal={self.internal_transfer_bytes}, "
            f"write_requests={self.count_write_requests}, read_requests={self.count_read_requests})>"
        )


class File(Base):
    __tablename__ = "files"

    id: str = Column(String(64), primary_key=True, default=lambda: str(uuid4()))
    user_id: str = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    bucket_id: str = Column(String(64), ForeignKey("buckets.id"), nullable=False, index=True)
    filename: str = Column(String(255), nullable=False)
    content_type: str = Column(String(128), nullable=True)
    path: str = Column(String(512), nullable=False)
    size: int = Column(Integer, nullable=False)
    is_deleted: bool = Column(Boolean, nullable=False, default=False)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    owner = relationship("User", back_populates="files")
    bucket = relationship("Bucket", back_populates="files")

    def __repr__(self) -> str:
        return (
            f"<File(id={self.id}, user_id={self.user_id}, bucket_id={self.bucket_id}, "
            f"filename={self.filename}, size={self.size}, is_deleted={self.is_deleted})>"
        )
