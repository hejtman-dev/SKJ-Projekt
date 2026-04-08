from fastapi import APIRouter, Body, Depends, Form, HTTPException, Query, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

try:
    from ..auth import get_current_user
    from ..billing import increment_read_requests
    from ..database import get_db
    from ..models import Bucket, File as FileModel, User
    from ..schemas import (
        BucketBillingResponse,
        BucketCreate,
        BucketListResponse,
        BucketResponse,
        BucketUpdate,
        FileListQuery,
        FileListResponse,
        FileListSummary,
        FileUploadResponse,
    )
except ImportError:
    from auth import get_current_user
    from billing import increment_read_requests
    from database import get_db
    from models import Bucket, File as FileModel, User
    from schemas import (
        BucketBillingResponse,
        BucketCreate,
        BucketListResponse,
        BucketResponse,
        BucketUpdate,
        FileListQuery,
        FileListResponse,
        FileListSummary,
        FileUploadResponse,
    )

router = APIRouter(prefix="/buckets", tags=["buckets"])


DEFAULT_BUCKET_COLOR = "teal"


def serialize_bucket(bucket: Bucket) -> BucketResponse:
    return BucketResponse(
        id=bucket.id,
        name=bucket.name,
        description=bucket.description,
        storage_limit_bytes=bucket.storage_limit_bytes,
        storage_limit_mb=round(bucket.storage_limit_bytes / (1024 * 1024), 2),
        color=bucket.color,
        is_locked=bucket.is_locked,
        current_storage_bytes=bucket.current_storage_bytes,
        created_at=bucket.created_at,
    )


def serialize_bucket_billing(bucket: Bucket) -> BucketBillingResponse:
    return BucketBillingResponse(
        bucket_id=bucket.id,
        bucket_name=bucket.name,
        current_storage_bytes=bucket.current_storage_bytes,
        current_storage_mb=round(bucket.current_storage_bytes / (1024 * 1024), 2),
        ingress_bytes=bucket.ingress_bytes,
        ingress_mb=round(bucket.ingress_bytes / (1024 * 1024), 2),
        egress_bytes=bucket.egress_bytes,
        egress_mb=round(bucket.egress_bytes / (1024 * 1024), 2),
        internal_transfer_bytes=bucket.internal_transfer_bytes,
        internal_transfer_mb=round(bucket.internal_transfer_bytes / (1024 * 1024), 2),
        count_write_requests=bucket.count_write_requests,
        count_read_requests=bucket.count_read_requests,
        storage_limit_bytes=bucket.storage_limit_bytes,
        storage_limit_mb=round(bucket.storage_limit_bytes / (1024 * 1024), 2),
        color=bucket.color,
        is_locked=bucket.is_locked,
    )


def _raise_validation_error(exc: ValidationError) -> None:
    raise RequestValidationError(exc.errors())


def parse_bucket_form(
    name: str = Form(...),
) -> BucketCreate:
    try:
        return BucketCreate(name=name)
    except ValidationError as exc:
        _raise_validation_error(exc)


def parse_file_list_query(
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    limit: int = Query(default=100),
) -> FileListQuery:
    try:
        return FileListQuery(
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
        )
    except ValidationError as exc:
        _raise_validation_error(exc)


def serialize_file(file: FileModel, bucket_name: str | None = None) -> FileUploadResponse:
    return FileUploadResponse(
        id=file.id,
        filename=file.filename,
        size=file.size,
        content_type=file.content_type,
        bucket_id=file.bucket_id,
        bucket_name=bucket_name,
        created_at=file.created_at,
    )


@router.get("/", response_model=BucketListResponse)
async def list_buckets(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BucketListResponse:
    buckets = db.execute(
        select(Bucket)
        .where(Bucket.user_id == user_id)
        .order_by(Bucket.created_at.asc(), Bucket.id.asc())
    ).scalars().all()

    return BucketListResponse(
        buckets=[serialize_bucket(bucket) for bucket in buckets]
    )


@router.post("/", response_model=BucketResponse, status_code=status.HTTP_201_CREATED)
async def create_bucket(
    payload: BucketCreate = Depends(parse_bucket_form),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BucketResponse:
    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Uživatel nenalezen")

    existing_bucket = db.execute(
        select(Bucket).where(Bucket.user_id == user_id, Bucket.name == payload.name)
    ).scalar_one_or_none()
    if existing_bucket:
        raise HTTPException(status_code=400, detail="Bucket s tímto názvem již existuje")

    bucket = Bucket(
        user_id=user_id,
        name=payload.name,
        storage_limit_bytes=user.storage_quota_bytes,
        color=DEFAULT_BUCKET_COLOR,
        is_locked=False,
    )
    db.add(bucket)
    db.commit()
    db.refresh(bucket)

    return serialize_bucket(bucket)


@router.patch("/{bucket_id}", response_model=BucketResponse)
async def update_bucket(
    bucket_id: str,
    payload: BucketUpdate = Body(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BucketResponse:
    bucket = db.execute(
        select(Bucket).where(Bucket.id == bucket_id, Bucket.user_id == user_id)
    ).scalar_one_or_none()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket nenalezen")

    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Uživatel nenalezen")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return serialize_bucket(bucket)

    if bucket.is_locked:
        allowed_unlock_only = set(changes.keys()) == {"is_locked"} and changes.get("is_locked") is False
        if not allowed_unlock_only:
            raise HTTPException(
                status_code=423,
                detail="Zamčený bucket lze pouze odemknout",
            )

    new_name = changes.get("name")
    if new_name and new_name != bucket.name:
        existing_bucket = db.execute(
            select(Bucket).where(
                Bucket.user_id == user_id,
                Bucket.name == new_name,
                Bucket.id != bucket.id,
            )
        ).scalar_one_or_none()
        if existing_bucket:
            raise HTTPException(status_code=400, detail="Bucket s tímto názvem již existuje")

    new_limit = changes.get("storage_limit_bytes")
    if new_limit is not None:
        if new_limit < bucket.current_storage_bytes:
            raise HTTPException(
                status_code=400,
                detail="Limit bucketu nemůže být menší než aktuálně uložená data",
            )
        if new_limit > user.storage_quota_bytes:
            raise HTTPException(
                status_code=400,
                detail="Limit bucketu nemůže překročit uživatelskou kvótu",
            )

    for field, value in changes.items():
        setattr(bucket, field, value)

    db.commit()
    db.refresh(bucket)
    return serialize_bucket(bucket)


@router.get("/{bucket_id}/objects/", response_model=FileListResponse)
async def list_bucket_objects(
    bucket_id: str,
    query: FileListQuery = Depends(parse_file_list_query),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileListResponse:
    bucket = db.execute(
        select(Bucket).where(Bucket.id == bucket_id, Bucket.user_id == user_id)
    ).scalar_one_or_none()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket nenalezen")

    filters = [
        FileModel.user_id == user_id,
        FileModel.bucket_id == bucket_id,
        FileModel.is_deleted.is_(False),
    ]
    if query.search:
        filters.append(func.lower(FileModel.filename).like(f"%{query.search.lower()}%"))

    sort_column = {
        "created_at": FileModel.created_at,
        "filename": FileModel.filename,
        "size": FileModel.size,
    }[query.sort_by]
    order_clause = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    files = db.execute(
        select(FileModel)
        .where(*filters)
        .order_by(order_clause, FileModel.id.asc())
        .limit(query.limit)
    ).scalars().all()

    totals = db.execute(
        select(
            func.count(FileModel.id),
            func.coalesce(func.sum(FileModel.size), 0),
        ).where(*filters)
    ).one()

    if files:
        increment_read_requests(bucket)
        db.commit()

    total = int(totals[0] or 0)
    total_size_bytes = int(totals[1] or 0)

    return FileListResponse(
        files=[serialize_file(file, bucket.name) for file in files],
        total=total,
        search=query.search,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
        summary=FileListSummary(
            total_size_bytes=total_size_bytes,
            total_size_mb=round(total_size_bytes / (1024 * 1024), 2),
        ),
    )


@router.get("/{bucket_id}/billing/", response_model=BucketBillingResponse)
async def get_bucket_billing(
    bucket_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BucketBillingResponse:
    bucket = db.execute(
        select(Bucket).where(Bucket.id == bucket_id, Bucket.user_id == user_id)
    ).scalar_one_or_none()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket nenalezen")

    return serialize_bucket_billing(bucket)
