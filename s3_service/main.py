from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

try:
    from .database import get_storage_dir, SessionLocal
    from .models import Bucket, User
    from .auth import hash_password
    from .routers import auth, buckets, files
    from .schemas import ErrorResponse, HealthResponse
    from .settings import settings
except ImportError:
    from database import get_storage_dir, SessionLocal
    from models import Bucket, User
    from auth import hash_password
    from routers import auth, buckets, files
    from schemas import ErrorResponse, HealthResponse
    from settings import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize storage and ensure the demo user exists after migrations are applied."""
    get_storage_dir()

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.username == settings.demo_username).first()
        if not existing_user:
            demo_user = User(
                username=settings.demo_username,
                email=settings.demo_email,
                hashed_password=hash_password(settings.demo_password),
                storage_quota_bytes=settings.storage_quota_bytes,
            )
            db.add(demo_user)
            db.commit()
            db.refresh(demo_user)
            db.add(
                Bucket(
                    user_id=demo_user.id,
                    name="default",
                    storage_limit_bytes=demo_user.storage_quota_bytes,
                    color="teal",
                    is_locked=False,
                )
            )
            db.commit()
        else:
            existing_bucket = db.query(Bucket).filter(
                Bucket.user_id == existing_user.id,
                Bucket.name == "default",
            ).first()
            if not existing_bucket:
                db.add(
                    Bucket(
                        user_id=existing_user.id,
                        name="default",
                        storage_limit_bytes=existing_user.storage_quota_bytes,
                        color="teal",
                        is_locked=False,
                    )
                )
                db.commit()
    finally:
        db.close()

    yield

app = FastAPI(
    title="S3 Object Storage Service",
    version="1.0.0",
    description="Production-ready object storage service inspired by Amazon S3",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers BEFORE static mount
app.include_router(auth.router)
app.include_router(buckets.router)
app.include_router(files.router)
app.include_router(files.objects_router)


@app.get("/health", tags=["health"], response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok", service="s3-storage")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(detail="Vnitřní chyba serveru").model_dump(),
    )


# Mount static files LAST so API routes are matched first
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
