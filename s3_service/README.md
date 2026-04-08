# S3 Object Storage Service

Pokročilejší S3-like služba pro ukládání souborů postavená na FastAPI, SQLAlchemy a Pydantic v2. Metadata souborů jsou perzistentně ukládána do SQLite databáze přes ORM modely a všechny hlavní vstupy i výstupy API používají Pydantic schémata.

## Instalace

```bash
pip install -r requirements.txt
```

## Spuštění

Před startem aplikace vždy aplikujte migrace:

```bash
alembic upgrade head
```

### Vývojový server

```bash
uvicorn s3_service.main:app --reload
```

Server poběží na `http://localhost:8000`

- Web rozhraní: `http://localhost:8000/`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

## Demo účet

Po startu aplikace se automaticky vytvoří demo uživatel:

- Uživatelské jméno: `admin`
- Heslo: `admin123`

## Hlavní funkce

- perzistentní metadata přes SQLAlchemy ORM a SQLite
- JWT autentizace a registrace uživatelů
- drag-and-drop upload souborů
- buckety pro organizaci objektů
- advanced billing pro storage, ingress, egress a internal transfer
- billing za API requesty (read/write counters po bucketu)
- soft delete ochrana proti nechtěnému smazání
- živý quota panel s procenty a zbývajícím místem
- vyhledávání a řazení souborů podle názvu, data a velikosti
- izolace dat mezi uživateli
- validace requestů i response modelů přes Pydantic

## API příklady

### Přihlášení

```bash
curl -X POST http://localhost:8000/auth/token \
  -F "username=admin" \
  -F "password=admin123"
```

### Registrace

```bash
curl -X POST http://localhost:8000/auth/register \
  -F "username=jan.novak" \
  -F "email=jan@example.com" \
  -F "password=password123"
```

### Upload souboru

```bash
curl -X POST http://localhost:8000/objects/upload \
  -F "bucket_id=<BUCKET_ID>" \
  -F "file=@/path/to/file.txt" \
  -H "Authorization: Bearer <TOKEN>"
```

Endpoint `/files/upload` zůstává jako kompatibilní alias.

Interní provoz lze simulovat hlavičkou:

```bash
-H "X-Internal-Source: true"
```

### Vytvoření bucketu

```bash
curl -X POST http://localhost:8000/buckets/ \
  -F "name=documents" \
  -H "Authorization: Bearer <TOKEN>"
```

### Výpis objektů v bucketu

```bash
curl "http://localhost:8000/buckets/<BUCKET_ID>/objects/?sort_by=filename&sort_order=asc" \
  -H "Authorization: Bearer <TOKEN>"
```

Ve výchozím stavu vrací jen objekty, které nejsou soft-deleted.

### Billing bucketu

```bash
curl "http://localhost:8000/buckets/<BUCKET_ID>/billing/" \
  -H "Authorization: Bearer <TOKEN>"
```

Billing snapshot nově obsahuje i:

- `count_write_requests`
- `count_read_requests`

### Výpis souborů se search/sort

```bash
curl "http://localhost:8000/objects/?search=report&sort_by=filename&sort_order=asc" \
  -H "Authorization: Bearer <TOKEN>"
```

Endpoint `/files/` zůstává jako kompatibilní alias.

### Soft delete objektu

```bash
curl -X DELETE http://localhost:8000/objects/<OBJECT_ID> \
  -H "Authorization: Bearer <TOKEN>"
```

Objekt se v databázi jen označí jako smazaný a přestane se zobrazovat v běžných výpisech.

Příklad odpovědi:

```json
{
  "files": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "annual-report.pdf",
      "size": 2048576,
      "content_type": "application/pdf",
      "created_at": "2026-04-01T14:44:29.881Z"
    }
  ],
  "total": 1,
  "search": "report",
  "sort_by": "filename",
  "sort_order": "asc",
  "summary": {
    "total_size_bytes": 2048576,
    "total_size_mb": 1.95
  }
}
```

### Quota informace

```bash
curl "http://localhost:8000/files/quota/info" \
  -H "Authorization: Bearer <TOKEN>"
```

Příklad odpovědi:

```json
{
  "used_bytes": 10485760,
  "limit_bytes": 524288000,
  "remaining_bytes": 513802240,
  "used_mb": 10.0,
  "limit_mb": 500.0,
  "remaining_mb": 490.0,
  "usage_percent": 2.0
}
```

## Validace dat

Pydantic modely pokrývají:

- registraci uživatele
- login request
- odpovědi s tokenem a uživatelem
- upload metadata
- buckety a listování obsahu bucketu
- billing snapshot bucketu
- seznam souborů včetně summary
- query parametry pro search/sort/limit
- quota response
- health response

Příklady validačních pravidel:

- `username`: 3-32 znaků, bez mezer, povoleno `a-z`, `A-Z`, `0-9`, `.`, `_`, `-`
- `email`: základní validace formátu
- `password`: minimálně 8 znaků
- `sort_by`: pouze `created_at`, `filename`, `size`
- `sort_order`: pouze `asc`, `desc`

## Struktura projektu

```text
s3_service/
├── main.py
├── database.py
├── models.py
├── schemas.py
├── auth.py
├── routers/
│   ├── auth.py
│   └── files.py
├── static/
│   └── index.html
└── README.md
```

## Poznámky

- soubory se fyzicky ukládají do `storage/{user_id}/{file_id}`
- metadata se ukládají do SQLite databáze `storage.db`
- schéma databáze se mění přes Alembic migrace, ne přes mazání DB
- metadata listy se v advanced billing neúčtují, počítá se upload/download objektu
- request billing se počítá jen pro úspěšné bucket-aware object endpointy
- soft-deleted objekty zůstávají fyzicky uložené a dál se počítají do storage billingu
- UI je čisté statické HTML/CSS/JS bez dalšího frameworku
- lokální dokumentace ve Swaggeru odpovídá Pydantic modelům
