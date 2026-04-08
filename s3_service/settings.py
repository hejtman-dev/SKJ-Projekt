from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "s3_service/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sqlalchemy_database_url: str = "sqlite:///./storage.db"
    jwt_secret_key: str = "super-secret-key-change-in-production"
    token_expiry_minutes: int = 60
    max_file_size_mb: int = 100
    storage_quota_mb: int = 500
    storage_dir: str = "storage"
    demo_username: str = "admin"
    demo_email: str = "admin@example.com"
    demo_password: str = "admin123"

    @property
    def app_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def resolved_database_url(self) -> str:
        if self.sqlalchemy_database_url.startswith("sqlite:///./"):
            database_name = self.sqlalchemy_database_url.removeprefix("sqlite:///./")
            return f"sqlite:///{(self.app_dir / database_name).as_posix()}"
        return self.sqlalchemy_database_url

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def storage_quota_bytes(self) -> int:
        return self.storage_quota_mb * 1024 * 1024

    @property
    def resolved_storage_dir(self) -> Path:
        storage_dir = Path(self.storage_dir)
        if storage_dir.is_absolute():
            return storage_dir
        return self.app_dir / storage_dir


settings = Settings()
