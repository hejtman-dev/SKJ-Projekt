from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

try:
    from ..database import get_db, get_storage_dir
    from ..schemas import FileListQuery, FileListResponse, FileListSummary, FileUploadResponse, QuotaResponse
    from ..models import File as FileModel
    from ..auth import get_current_user
    from ..settings import settings
except ImportError:
    from database import get_db, get_storage_dir
    from schemas import FileListQuery, FileListResponse, FileListSummary, FileUploadResponse, QuotaResponse
    from models import File as FileModel
    from auth import get_current_user
    from settings import settings

MAX_FILE_SIZE = settings.max_file_size_bytes
STORAGE_QUOTA = settings.storage_quota_bytes
UPLOAD_CHUNK_SIZE = 1024 * 1024

router = APIRouter(prefix="/files", tags=["files"])


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


@router.post("/upload", response_model=FileUploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    """Upload a file for the current user."""
    if not file.filename or not file.filename.strip():
        raise HTTPException(status_code=400, detail="Soubor musí mít název")

    result = db.execute(
        select(func.coalesce(func.sum(FileModel.size), 0)).where(
            FileModel.user_id == user_id
        )
    )
    used_bytes = int(result.scalar() or 0)

    # Generate file ID and create user directory
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

                await buffer.write(chunk)
    except HTTPException:
        cleanup_partial_upload(file_path, user_dir)
        raise
    except Exception:
        cleanup_partial_upload(file_path, user_dir)
        raise
    finally:
        await file.close()

    # Store metadata in database
    db_file = FileModel(
        id=file_id,
        user_id=user_id,
        filename=file.filename,
        content_type=file.content_type,
        path=str(file_path),
        size=total_written,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    return FileUploadResponse.model_validate(db_file)


@router.get("/", response_model=FileListResponse)
async def list_files(
    query: FileListQuery = Depends(parse_file_list_query),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileListResponse:
    """List all files for the current user."""
    filters = [FileModel.user_id == user_id]
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

    total = int(totals[0] or 0)
    total_size_bytes = int(totals[1] or 0)
    return FileListResponse(
        files=[FileUploadResponse.model_validate(f) for f in files],
        total=total,
        search=query.search,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
        summary=FileListSummary(
            total_size_bytes=total_size_bytes,
            total_size_mb=round(total_size_bytes / (1024 * 1024), 2),
        ),
    )


@router.get("/{file_id}", response_class=FileResponse)
async def download_file(
    file_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a file (stream)."""
    db_file = db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.user_id == user_id
        )
    ).scalar_one_or_none()

    if not db_file:
        raise HTTPException(status_code=404, detail="Soubor nenalezen")

    file_path = Path(db_file.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Soubor nenalezen na disku")

    return FileResponse(
        path=file_path,
        filename=db_file.filename,
        media_type=db_file.content_type or "application/octet-stream"
    )


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a file."""
    db_file = db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.user_id == user_id
        )
    ).scalar_one_or_none()

    if not db_file:
        raise HTTPException(status_code=404, detail="Soubor nenalezen")

    # Delete physical file
    file_path = Path(db_file.path)
    if file_path.exists():
        file_path.unlink()

    # Delete database record
    db.delete(db_file)
    db.commit()

    return Response(status_code=204)


@router.get("/quota/info", response_model=QuotaResponse)
async def get_quota(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuotaResponse:
    """Get storage quota information for the current user."""
    result = db.execute(
        select(func.coalesce(func.sum(FileModel.size), 0)).where(
            FileModel.user_id == user_id
        )
    )
    used_bytes = int(result.scalar() or 0)
    limit_bytes = settings.storage_quota_bytes
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
