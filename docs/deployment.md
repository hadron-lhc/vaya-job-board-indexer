# Deployment Guide

## Requirements

- Python 3.12+
- SQLite 3.35+ with FTS5 support
- Outbound HTTPS access to public job-board endpoints
- A writable directory for `data/jobs.db` and `artifacts/`
- A reverse proxy for TLS if the API is exposed outside localhost

No API keys, credentials, or browser automation are required for the implemented connectors.

## Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
```

## Initialize and test

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m job_indexer list-sources --config config/sources.json
```

## First fetch

```bash
.venv/bin/python -m job_indexer fetch-all \
  --config config/sources.json \
  --db data/jobs.db \
  --artifacts-dir artifacts
```

Exit codes:

- `0`: all selected sources succeeded.
- `2`: at least one source returned `PARTIAL_SUCCESS`.
- `1`: at least one hard failure or configuration error.

Workday sources are intentionally capped by `max_jobs=5`, so they return `PARTIAL_SUCCESS` and make `fetch-all` exit with `2`. This is expected until the cap is raised.

## Serve the API and UI

```bash
.venv/bin/python -m job_indexer serve \
  --db data/jobs.db \
  --host 127.0.0.1 \
  --port 8000
```

Routes:

- `GET /health`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{id}`
- `GET /api/v1/sources`
- `GET /api/v1/coverage`
- `GET /api/v1/fetch-runs`
- `GET /` (HTML search UI)
- `GET /coverage` (HTML coverage page)

Query parameters for `/api/v1/jobs`: `q`, `company`, `location`, `platform`, `status`, `limit`, `offset`, `sort`.

`limit` is capped at 100. `sort` is `relevance`, `newest`, or `oldest`. `status` is `open` or `closed`.

## Scheduling

Use cron for the MVP. Run a full refresh a few times per day and keep one process per database.

```cron
17 */6 * * * cd /opt/vaya-job-board-indexer && .venv/bin/python -m job_indexer fetch-all --config config/sources.json --db data/jobs.db --artifacts-dir artifacts >> logs/fetch.log 2>&1
```

Do not run overlapping full refreshes against the same SQLite database. Use `flock` if cron overlap is possible.

```bash
flock -n /tmp/vaya-indexer.lock .venv/bin/python -m job_indexer fetch-all
```

## systemd example

`/etc/systemd/system/vaya-indexer.service`:

```ini
[Unit]
Description=Vaya Job Board Indexer API
After=network-online.target

[Service]
Type=simple
User=vaya
WorkingDirectory=/opt/vaya-job-board-indexer
ExecStart=/opt/vaya-job-board-indexer/.venv/bin/python -m job_indexer serve --db /opt/vaya-job-board-indexer/data/jobs.db --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/vaya-indexer-fetch.service`:

```ini
[Unit]
Description=Vaya Job Board Indexer Fetch
After=network-online.target

[Service]
Type=oneshot
User=vaya
WorkingDirectory=/opt/vaya-job-board-indexer
ExecStart=/opt/vaya-job-board-indexer/.venv/bin/python -m job_indexer fetch-all --config /opt/vaya-job-board-indexer/config/sources.json --db /opt/vaya-job-board-indexer/data/jobs.db --artifacts-dir /opt/vaya-job-board-indexer/artifacts
```

`/etc/systemd/system/vaya-indexer-fetch.timer`:

```ini
[Unit]
Description=Run Vaya indexer every six hours

[Timer]
OnCalendar=*-*-* 00/6:17:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vaya-indexer.service
sudo systemctl enable --now vaya-indexer-fetch.timer
```

## Reverse proxy

The API has no built-in authentication. Bind it to `127.0.0.1` and put Caddy, nginx, or another reverse proxy in front of it. Add TLS, access control, and rate limiting at the proxy.

Example Caddyfile:

```caddyfile
jobs.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

## Data and backup

- Primary database: `data/jobs.db`
- SQLite WAL files: `data/jobs.db-wal`, `data/jobs.db-shm`
- Raw evidence: `artifacts/raw/{source_instance}/{run_id}.json`
- Live evidence: `artifacts/live_runs/`

Back up the database with SQLite's backup command or a consistent file copy while the API is idle.

```bash
sqlite3 data/jobs.db ".backup '/backups/jobs-$(date +%F).db'"
```

Raw payloads can be large. Apply retention if disk usage matters.

## Upgrade and migration

`init_db()` creates missing tables, adds missing columns, and creates indexes after migration. It is safe to run against older databases. Always back up `data/jobs.db` before upgrading.

## Operational checks

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/v1/sources
curl -s 'http://127.0.0.1:8000/api/v1/jobs?limit=1'
.venv/bin/python -m job_indexer coverage --db data/jobs.db
```

Inspect recent runs:

```bash
sqlite3 data/jobs.db "SELECT source_instance, status, jobs_discovered, jobs_processed, error_class FROM fetch_runs ORDER BY started_at DESC LIMIT 20;"
```

## Security notes

- No secrets are stored in the repository or fixtures.
- The API is read-only but unauthenticated.
- Do not expose SQLite or the artifacts directory through the reverse proxy.
- Keep the service user unprivileged and restrict write access to `data/` and `artifacts/`.
