from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm import DeclarativeBase
from pathlib import Path

try:
    from .settings import settings
except ImportError:
    from settings import settings

# Database URL
SQLALCHEMY_DATABASE_URL = settings.resolved_database_url

# Create engine with SQLite-specific settings
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base class for all ORM models
class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_storage_dir() -> Path:
    """Get or create storage directory."""
    storage_dir = settings.resolved_storage_dir
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir
