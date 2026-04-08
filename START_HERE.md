# S3 Object Storage Service

Production-ready file storage service built with FastAPI, SQLAlchemy, and Pydantic v2.

## 🚀 Quick Start

### Option 1: Using the run script (Recommended)

**Linux/Mac:**
```bash
bash run.sh
```

**Windows:**
```bash
run.bat
```

### Option 2: Manual startup

```bash
alembic upgrade head
cd s3_service
source ../venv/bin/activate  # or: . ../venv/Scripts/activate (Windows)
uvicorn main:app --reload
```

### Option 3: From project root

```bash
alembic upgrade head
uvicorn s3_service.main:app --reload
```

## 📍 Access the Application

- **Web UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 🔐 Demo Credentials

- **Username**: `admin`
- **Password**: `admin123`

## 📁 Project Structure

```
s3_service/
├── main.py                 # FastAPI application
├── alembic/                # Database migrations
├── database.py             # SQLAlchemy setup
├── models.py               # User & File ORM models
├── schemas.py              # Pydantic schemas
├── auth.py                 # JWT authentication
├── routers/
│   ├── auth.py            # Login endpoint
│   └── files.py           # File operations
├── static/
│   └── index.html         # Web UI
├── storage/               # Uploaded files (gitignored)
├── storage.db             # SQLite database (gitignored)
├── README.md              # Detailed documentation
└── .env.example           # Configuration template
```

## ✨ Features

✅ JWT Bearer token authentication  
✅ Drag-and-drop file upload UI  
✅ Per-user storage quotas (500MB)  
✅ File download & deletion  
✅ Advanced bucket billing  
✅ Soft delete objektů  
✅ API request billing  
✅ Real-time quota tracking  
✅ Full REST API with Swagger docs  
✅ SQLite database  
✅ Async I/O with aiofiles  

## 📚 More Information

See `s3_service/README.md` for detailed documentation, API examples, and configuration options.

## 🔄 Database Migrations

Po změně SQLAlchemy modelů negenerujte databázi znovu mazáním `storage.db`. Místo toho:

```bash
alembic revision --autogenerate -m "popis zmeny"
alembic upgrade head
```

---

**Status**: Ready to run ✅
