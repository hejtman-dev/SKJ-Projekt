from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

BUCKET_COLOR_OPTIONS = ("teal", "blue", "amber", "violet", "rose")


class FileUploadResponse(BaseModel):
    id: str
    filename: str
    size: int
    content_type: str | None = None
    bucket_id: str
    bucket_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "filename": "document.pdf",
                "size": 2048576,
                "content_type": "application/pdf",
                "bucket_id": "660e8400-e29b-41d4-a716-446655440001",
                "bucket_name": "default",
                "created_at": "2026-04-01T14:44:29.881Z",
            }
        },
    )


class FileListSummary(BaseModel):
    total_size_bytes: int = Field(..., ge=0)
    total_size_mb: float = Field(..., ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_size_bytes": 2048576,
                "total_size_mb": 1.95,
            }
        }
    )


class FileListResponse(BaseModel):
    files: list[FileUploadResponse]
    total: int
    search: str | None = None
    sort_by: Literal["created_at", "filename", "size"]
    sort_order: Literal["asc", "desc"]
    summary: FileListSummary

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "files": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "filename": "document.pdf",
                        "size": 2048576,
                        "content_type": "application/pdf",
                        "bucket_id": "660e8400-e29b-41d4-a716-446655440001",
                        "bucket_name": "default",
                        "created_at": "2026-04-01T14:44:29.881Z",
                    }
                ],
                "total": 1,
                "search": "document",
                "sort_by": "created_at",
                "sort_order": "desc",
                "summary": {
                    "total_size_bytes": 2048576,
                    "total_size_mb": 1.95,
                },
            }
        }
    )


class FileListQuery(BaseModel):
    search: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Case-insensitive filename search.",
    )
    sort_by: Literal["created_at", "filename", "size"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=100, ge=1, le=500)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "search": "invoice",
                "sort_by": "filename",
                "sort_order": "asc",
                "limit": 50,
            }
        }
    )

    @field_validator("search")
    @classmethod
    def strip_search(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ErrorResponse(BaseModel):
    detail: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Soubor nenalezen",
            }
        }
    )


class QuotaResponse(BaseModel):
    used_bytes: int
    limit_bytes: int
    remaining_bytes: int
    used_mb: float
    limit_mb: float
    remaining_mb: float
    usage_percent: float

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "used_bytes": 10485760,
                "limit_bytes": 524288000,
                "remaining_bytes": 513802240,
                "used_mb": 10.0,
                "limit_mb": 500.0,
                "remaining_mb": 490.0,
                "usage_percent": 2.0,
            }
        }
    )


class HealthResponse(BaseModel):
    status: str
    service: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "service": "s3-storage",
            }
        }
    )


class BucketCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "documents",
            }
        }
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Název bucketu musí mít alespoň 3 znaky")
        return normalized


class BucketResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    storage_limit_bytes: int
    storage_limit_mb: float
    color: str
    is_locked: bool
    current_storage_bytes: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BucketListResponse(BaseModel):
    buckets: list[BucketResponse]


class BucketUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    storage_limit_bytes: int | None = Field(default=None, ge=1)
    color: str | None = None
    is_locked: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Název bucketu musí mít alespoň 3 znaky")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in BUCKET_COLOR_OPTIONS:
            raise ValueError("Neplatná barva bucketu")
        return normalized


class BucketBillingResponse(BaseModel):
    bucket_id: str
    bucket_name: str
    current_storage_bytes: int
    current_storage_mb: float
    ingress_bytes: int
    ingress_mb: float
    egress_bytes: int
    egress_mb: float
    internal_transfer_bytes: int
    internal_transfer_mb: float
    count_write_requests: int
    count_read_requests: int
    storage_limit_bytes: int
    storage_limit_mb: float
    color: str
    is_locked: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bucket_id": "660e8400-e29b-41d4-a716-446655440001",
                "bucket_name": "documents",
                "current_storage_bytes": 2048576,
                "current_storage_mb": 1.95,
                "ingress_bytes": 2048576,
                "ingress_mb": 1.95,
                "egress_bytes": 4097152,
                "egress_mb": 3.91,
                "internal_transfer_bytes": 0,
                "internal_transfer_mb": 0.0,
                "count_write_requests": 3,
                "count_read_requests": 7,
                "storage_limit_bytes": 524288000,
                "storage_limit_mb": 500.0,
                "color": "teal",
                "is_locked": False,
            }
        }
    )


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    username_pattern: ClassVar[str] = r"^[a-zA-Z0-9._-]+$"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "jan.novak",
                "email": "jan@example.com",
                "password": "password123",
            }
        }
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Uživatelské jméno musí mít alespoň 3 znaky")
        if any(ch.isspace() for ch in normalized):
            raise ValueError("Uživatelské jméno nesmí obsahovat mezery")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
        if any(ch not in allowed for ch in normalized):
            raise ValueError("Uživatelské jméno může obsahovat pouze písmena, čísla, tečku, pomlčku a podtržítko")
        return normalized

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        local, separator, domain = normalized.partition("@")
        if not separator or not local or not domain or "." not in domain:
            raise ValueError("Neplatný email")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("Heslo nesmí začínat ani končit mezerou")
        return value


class UserResponse(BaseModel):
    id: str
    username: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class TokenRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=1, max_length=128)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "admin",
                "password": "admin123",
            }
        }
    )

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Uživatelské jméno musí mít alespoň 3 znaky")
        return normalized


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
            }
        }
    )
