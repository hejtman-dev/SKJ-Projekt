from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, Response
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

try:
    from ..auth import get_current_user
    from ..billing import (
        adjust_storage_bytes,
        apply_download_billing,
        apply_transfer_billing,
        commit_bucket_billing,
        increment_read_requests,
        increment_write_requests,
        is_internal_request,
    )
    from ..database import get_db, get_storage_dir
    from ..models import Bucket, File as FileModel, User
    from ..schemas import FileListQuery, FileListResponse, FileListSummary, FileUploadResponse, QuotaResponse
    from ..settings import settings
except ImportError:
    from auth import get_current_user
    from billing import (
        adjust_storage_bytes,
        apply_download_billing,
        apply_transfer_billing,
        commit_bucket_billing,
        increment_read_requests,
        increment_write_requests,
        is_internal_request,
    )
    from database import get_db, get_storage_dir
    from models import Bucket, File as FileModel, User
    from schemas import FileListQuery, FileListResponse, FileListSummary, FileUploadResponse, QuotaResponse
    from settings import settings

MAX_FILE_SIZE = settings.max_file_size_bytes
STORAGE_QUOTA = settings.storage_quota_bytes
UPLOAD_CHUNK_SIZE = 1024 * 1024

router = APIRouter(prefix="/files", tags=["files"])
objects_router = APIRouter(prefix="/objects", tags=["objects"])


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
        raise RequestValidationError(exc.errors())


def cleanup_partial_upload(file_path: Path, user_dir: Path) -> None:
    """Remove partial files and empty user directories after failed uploads."""
    if file_path.exists():
        file_path.unlink()

    try:
        user_dir.rmdir()
    except OSError:
        pass


def serialize_file(file: FileModel, bucket_name: str | None = None) -> FileUploadResponse:
    resolved_bucket_name = bucket_name
    if resolved_bucket_name is None and getattr(file, "bucket", None) is not None:
        resolved_bucket_name = file.bucket.name

    return FileUploadResponse(
        id=file.id,
        filename=file.filename,
        size=file.size,
        content_type=file.content_type,
        bucket_id=file.bucket_id,
        bucket_name=resolved_bucket_name,
        created_at=file.created_at,
    )


def active_file_filters(user_id: str) -> list:
    return [FileModel.user_id == user_id, FileModel.is_deleted.is_(False)]


def get_bucket_for_user(db: Session, bucket_id: str, user_id: str) -> Bucket | None:
    return db.execute(
        select(Bucket).where(Bucket.id == bucket_id, Bucket.user_id == user_id)
    ).scalar_one_or_none()


def get_user_for_id(db: Session, user_id: str) -> User | None:
    return db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()


def get_buckets_for_ids(db: Session, bucket_ids: set[str], user_id: str) -> list[Bucket]:
    if not bucket_ids:
        return []

    return db.execute(
        select(Bucket).where(Bucket.user_id == user_id, Bucket.id.in_(bucket_ids))
    ).scalars().all()


def get_file_for_user(
    db: Session,
    file_id: str,
    user_id: str,
    *,
    include_deleted: bool = False,
) -> FileModel | None:
    filters = [FileModel.id == file_id, FileModel.user_id == user_id]
    if not include_deleted:
        filters.append(FileModel.is_deleted.is_(False))

    return db.execute(select(FileModel).where(*filters)).scalar_one_or_none()


async def upload_file_impl(
    file: UploadFile,
    bucket_id: str,
    x_internal_source: str | None,
    user_id: str,
    db: Session,
) -> FileUploadResponse:
    if not file.filename or not file.filename.strip():
        raise HTTPException(status_code=400, detail="Soubor musí mít název")

    bucket = get_bucket_for_user(db, bucket_id, user_id)
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket nenalezen")
    if bucket.is_locked:
        raise HTTPException(status_code=423, detail="Bucket je zamčený a je pouze pro čtení")

    user = get_user_for_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Uživatel nenalezen")

    result = db.execute(
        select(func.coalesce(func.sum(FileModel.size), 0)).where(FileModel.user_id == user_id)
    )
    used_bytes = int(result.scalar() or 0)

    file_id = str(uuid4())
    storage_dir = get_storage_dir()
    user_dir = storage_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    file_path = user_dir / file_id
    total_written = 0

    try:
        async with aiofiles.open(file_path, "wb") as buffer:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                total_written += len(chunk)

                if total_written > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Soubor je příliš velký (maximum {settings.max_file_size_mb}MB)",
                    )

                if used_bytes + total_written > STORAGE_QUOTA:
                    raise HTTPException(
                        status_code=507,
                        detail="Překročena kvóta úložiště",
                    )

                if bucket.current_storage_bytes + total_written > bucket.storage_limit_bytes:
                    raise HTTPException(
                        status_code=409,
                        detail="Překročen limit bucketu",
                    )

                if used_bytes + total_written > user.storage_quota_bytes:
                    raise HTTPException(
                        status_code=507,
                        detail="Překročena kvóta uživatele",
                    )

                await buffer.write(chunk)
    except HTTPException:
        cleanup_partial_upload(file_path, user_dir)
        raise
    except Exception:
        cleanup_partial_upload(file_path, user_dir)
        raise
    finally:
        await file.close()

    db_file = FileModel(
        id=file_id,
        user_id=user_id,
        bucket_id=bucket_id,
        filename=file.filename,
        content_type=file.content_type,
        path=str(file_path),
        size=total_written,
        is_deleted=False,
    )
    db.add(db_file)
    adjust_storage_bytes(bucket, total_written)
    apply_transfer_billing(bucket, total_written, is_internal_request(x_internal_source))
    increment_write_requests(bucket)
    db.commit()
    db.refresh(db_file)

    return serialize_file(db_file, bucket.name)


def list_files_impl(
    query: FileListQuery,
    user_id: str,
    db: Session,
) -> FileListResponse:
    filters = active_file_filters(user_id)
    if query.search:
        filters.append(func.lower(FileModel.filename).like(f"%{query.search.lower()}%"))

    sort_column = {
        "created_at": FileModel.created_at,
        "filename": FileModel.filename,
        "size": FileModel.size,
    }[query.sort_by]
    order_clause = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    files = db.execute(
        select(FileModel, Bucket.name)
        .join(Bucket, Bucket.id == FileModel.bucket_id)
        .where(*filters)
        .order_by(order_clause, FileModel.id.asc())
        .limit(query.limit)
    ).all()

    totals = db.execute(
        select(
            func.count(FileModel.id),
            func.coalesce(func.sum(FileModel.size), 0),
        ).where(*filters)
    ).one()

    visible_bucket_ids = {file.bucket_id for file, _bucket_name in files}
    for bucket in get_buckets_for_ids(db, visible_bucket_ids, user_id):
        increment_read_requests(bucket)
    if visible_bucket_ids:
        db.commit()

    total = int(totals[0] or 0)
    total_size_bytes = int(totals[1] or 0)
    return FileListResponse(
        files=[serialize_file(file, bucket_name) for file, bucket_name in files],
        total=total,
        search=query.search,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
        summary=FileListSummary(
            total_size_bytes=total_size_bytes,
            total_size_mb=round(total_size_bytes / (1024 * 1024), 2),
        ),
    )


def download_file_impl(
    file_id: str,
    x_internal_source: str | None,
    user_id: str,
    db: Session,
):
    db_file = get_file_for_user(db, file_id, user_id, include_deleted=False)
    if not db_file:
        raise HTTPException(status_code=404, detail="Soubor nenalezen")

    bucket = get_bucket_for_user(db, db_file.bucket_id, user_id)
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket nenalezen")

    file_path = Path(db_file.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Soubor nenalezen na disku")

    apply_download_billing(bucket, db_file.size, is_internal_request(x_internal_source))
    increment_read_requests(bucket)
    commit_bucket_billing(db)

    return FileResponse(
        path=file_path,
        filename=db_file.filename,
        media_type=db_file.content_type or "application/octet-stream",
    )


def delete_file_impl(
    file_id: str,
    user_id: str,
    db: Session,
):
    db_file = get_file_for_user(db, file_id, user_id, include_deleted=True)
    if not db_file:
        raise HTTPException(status_code=404, detail="Soubor nenalezen")

    if db_file.is_deleted:
        bucket = get_bucket_for_user(db, db_file.bucket_id, user_id)
        if bucket:
            increment_write_requests(bucket)
            db.commit()
        return Response(status_code=204)

    bucket = get_bucket_for_user(db, db_file.bucket_id, user_id)
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket nenalezen")
    if bucket.is_locked:
        raise HTTPException(status_code=423, detail="Bucket je zamčený a je pouze pro čtení")

    db_file.is_deleted = True
    increment_write_requests(bucket)
    db.commit()
    return Response(status_code=204)


@router.post("/upload", response_model=FileUploadResponse, status_code=201)
@objects_router.post("/upload", response_model=FileUploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    bucket_id: str = Form(...),
    x_internal_source: str | None = Header(default=None),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    """Upload a file for the current user."""
    return await upload_file_impl(file, bucket_id, x_internal_source, user_id, db)


@router.get("/", response_model=FileListResponse)
@objects_router.get("/", response_model=FileListResponse)
async def list_files(
    query: FileListQuery = Depends(parse_file_list_query),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileListResponse:
    """List all active files for the current user."""
    return list_files_impl(query, user_id, db)


@router.get("/{file_id}", response_class=FileResponse)
@objects_router.get("/{file_id}", response_class=FileResponse)
async def download_file(
    file_id: str,
    x_internal_source: str | None = Header(default=None),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download an active file."""
    return download_file_impl(file_id, x_internal_source, user_id, db)


@router.delete("/{file_id}", status_code=204)
@objects_router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft delete a file."""
    return delete_file_impl(file_id, user_id, db)


@router.get("/quota/info", response_model=QuotaResponse)
async def get_quota(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuotaResponse:
    """Get storage quota information for the current user."""
    result = db.execute(
        select(func.coalesce(func.sum(FileModel.size), 0)).where(FileModel.user_id == user_id)
    )
    used_bytes = int(result.scalar() or 0)
    user = get_user_for_id(db, user_id)
    limit_bytes = user.storage_quota_bytes if user else settings.storage_quota_bytes
    remaining_bytes = max(limit_bytes - used_bytes, 0)
    usage_percent = round((used_bytes / limit_bytes) * 100, 2) if limit_bytes else 0.0

    return QuotaResponse(
        used_bytes=used_bytes,
        limit_bytes=limit_bytes,
        remaining_bytes=remaining_bytes,
        used_mb=used_bytes / (1024 * 1024),
        limit_mb=limit_bytes / (1024 * 1024),
        remaining_mb=remaining_bytes / (1024 * 1024),
        usage_percent=usage_percent,
    )
