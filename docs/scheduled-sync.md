# Scheduled Sync

The app does not run FTP indexing inside the web server. That keeps the deployed FastAPI process simple and responsive.

Instead, `.github/workflows/scheduled-sync.yml` refreshes the SQLite index on a schedule:

1. GitHub Actions checks out the repository.
2. Python dependencies are installed.
3. `python sync_ftp.py` scans the FTP server.
4. `python rebuild_metadata.py` normalizes display labels.
5. If `data/papers.db` changed, the workflow commits the updated database.
6. Railway redeploys from the new commit.

The workflow runs every two months and can also be started manually from the GitHub Actions tab.

This approach is easier to explain and safer than running a timer inside FastAPI:

- the web server only serves requests
- sync work happens outside user traffic
- SQLite remains the source of truth
- Railway redeploys normally when the index changes

If GitHub Actions cannot reach the FTP server, run `python sync_ftp.py` locally, commit `data/papers.db`, and push.
