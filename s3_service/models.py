from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
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

    files = relationship("File", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class File(Base):
    __tablename__ = "files"

    id: str = Column(String(64), primary_key=True, default=lambda: str(uuid4()))
    user_id: str = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    filename: str = Column(String(255), nullable=False)
    content_type: str = Column(String(128), nullable=True)
    path: str = Column(String(512), nullable=False)
    size: int = Column(Integer, nullable=False)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    owner = relationship("User", back_populates="files")

    def __repr__(self) -> str:
        return f"<File(id={self.id}, user_id={self.user_id}, filename={self.filename}, size={self.size})>"
