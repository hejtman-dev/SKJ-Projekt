from typing import Optional

from sqlalchemy.orm import Session

try:
    from .models import Bucket
except ImportError:
    from models import Bucket


def is_internal_request(header_value: Optional[str]) -> bool:
    """Treat only the explicit true header value as internal traffic."""
    return (header_value or "").strip().lower() == "true"


def apply_transfer_billing(
    bucket: Bucket,
    size_bytes: int,
    internal: bool,
) -> None:
    """Account transfer bytes on the bucket in place."""
    if size_bytes <= 0:
        return

    if internal:
        bucket.internal_transfer_bytes += size_bytes
    else:
        bucket.ingress_bytes += size_bytes


def apply_download_billing(
    bucket: Bucket,
    size_bytes: int,
    internal: bool,
) -> None:
    """Account download bytes on the bucket in place."""
    if size_bytes <= 0:
        return

    if internal:
        bucket.internal_transfer_bytes += size_bytes
    else:
        bucket.egress_bytes += size_bytes


def adjust_storage_bytes(bucket: Bucket, delta_bytes: int) -> None:
    """Update current storage while never allowing negative totals."""
    bucket.current_storage_bytes = max(bucket.current_storage_bytes + delta_bytes, 0)


def increment_write_requests(bucket: Bucket, count: int = 1) -> None:
    """Increment write request counter on the bucket."""
    if count <= 0:
        return
    bucket.count_write_requests += count


def increment_read_requests(bucket: Bucket, count: int = 1) -> None:
    """Increment read request counter on the bucket."""
    if count <= 0:
        return
    bucket.count_read_requests += count


def commit_bucket_billing(db: Session) -> None:
    """Persist bucket billing updates."""
    db.commit()
