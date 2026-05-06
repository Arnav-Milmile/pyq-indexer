# Previous Year Paper Finder

A FastAPI web application for searching, browsing, and downloading previous year question papers from a legacy FTP archive.

The project solves the common problem of slow, hard-to-navigate FTP folders by building a local SQLite index of the remote file tree. Students interact with a fast website, while the application handles FTP traversal and download proxying behind the scenes.

## Live Demo

```text
https://rcoem-previousyearpapers.up.railway.app/
```

## Highlights

- SQLite-backed index of 11,000+ PDF papers
- Search prioritizes paper/subject title matches before branch or path matches
- Advanced filtering with multiple selection support for course, branch, exam category, and year
- Filter chips show active filters with easy removal
- Modal-based PDF preview with dedicated viewer
- Direct download endpoint that proxies files from FTP
- Responsive HTML, CSS, and vanilla JavaScript frontend
- FastAPI-generated API documentation available at `/docs`
- Railway deployment config included
- Scheduled GitHub Actions workflow for periodic index refreshes

## Architecture

```text
FTP Server
   |
   | sync_ftp.py scans folders and PDF paths
   v
SQLite Index: data/papers.db
   |
   | FastAPI reads indexed metadata
   v
Website + JSON API
   |
   | downloads are fetched from FTP on demand
   v
Student Browser
```

This keeps page loads fast because browsing and search do not contact the FTP server on every request.

## Project Structure

```text
app/
  main.py              FastAPI app entrypoint
  config.py            Environment settings
  database.py          SQLite schema and queries
  models.py            API response models
  routers/
    pages.py           HTML page routes
    papers.py          JSON API and download routes
  sync/
    ftp_sync.py        FTP traversal, retry logic, metadata parser
.github/
  workflows/
    scheduled-sync.yml Refreshes the SQLite index every two months
data/
  papers.db            SQLite paper index
  papers/              Optional local PDF cache
docs/
  implementation-plan.txt
  scheduled-sync.md
static/
  css/style.css
  js/app.js
templates/
  base.html
  index.html
  browse.html
rebuild_metadata.py    Rebuild metadata from existing FTP paths
sync_ftp.py            Rescan FTP and update SQLite
railway.json           Railway deployment config
```

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Refresh The Paper Index

Scan the FTP server and update `data/papers.db`:

```powershell
python sync_ftp.py
```

Rebuild metadata labels from existing FTP paths without scanning FTP again:

```powershell
python rebuild_metadata.py
```

The repository also includes a GitHub Actions workflow that refreshes the index every two months. See `docs/scheduled-sync.md`.

## Run Locally

```powershell
python -m uvicorn app.main:app --reload
```

Local URLs:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/browse
http://127.0.0.1:8000/docs
```

## Deployment

The repository includes `railway.json`. Railway starts the app with:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Required committed data:

- `data/papers.db`
- `data/papers/.gitkeep`

Ignored local-only files:

- `.env`
- `.venv/`
- `__pycache__/`
- `*.log`
- PDFs inside `data/papers/`

## Environment Variables

```env
APP_NAME=Previous Year Paper Finder
DATABASE_PATH=data/papers.db
PAPERS_DIR=data/papers
FTP_HOST=103.220.82.76
FTP_PORT=21
FTP_USER=anonymous
FTP_PASSWORD=
FTP_ROOT=/
FTP_TIMEOUT=60
FTP_PASSIVE=true
FTP_ENCODING=cp1252
FTP_USE_MLSD=false
FTP_RETRIES=2
FTP_TRY_ALTERNATE_MODE=true
```

## Notes

The application currently stores only the paper index in SQLite. PDF files are fetched from FTP when a download is requested. A future improvement would be object-storage caching with Cloudflare R2 or S3-compatible storage.
