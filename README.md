# vaya-job-board-indexer

Multi-tenant job board indexer with lifecycle tracking, conservative deduplication, FTS search, a read-only JSON API, and a minimal HTML UI.

Current coverage: **11 ATS platforms**, each live-tested with two employer tenants. Coverage is 11 of 78 challenge platforms (14.1%). See `docs/coverage_report.md` for the honest coverage breakdown.

Implemented platforms:

- Greenhouse
- Lever
- Ashby
- Workable
- SmartRecruiters
- Recruitee
- Pinpoint
- Personio
- Teamtailor
- Rippling
- Workday

## Requirements

- Python 3.12+
- SQLite with FTS5 support
- Public network access to the configured job board APIs

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
```

## Commands

List configured sources:

```bash
.venv/bin/python -m job_indexer list-sources --config config/sources.json
```

Fetch one source:

```bash
.venv/bin/python -m job_indexer fetch \
  --platform greenhouse \
  --source greenhouse-stripe \
  --config config/sources.json
```

Fetch all configured sources:

```bash
.venv/bin/python -m job_indexer fetch-all \
  --config config/sources.json \
  --db data/jobs.db \
  --artifacts-dir artifacts
```

Exit codes: `0` all success, `2` partial success, `1` hard failure or configuration error.

Start the API and UI:

```bash
.venv/bin/python -m job_indexer serve --db data/jobs.db --host 127.0.0.1 --port 8000
```

Other commands:

```bash
.venv/bin/python -m job_indexer coverage --db data/jobs.db
.venv/bin/python -m job_indexer rebuild-dedup --db data/jobs.db
```

## Tests

Deterministic tests:

```bash
.venv/bin/python -m pytest -q
```

Live tests:

```bash
.venv/bin/python -m pytest -q -m live -o addopts=""
```

Live evidence for all configured sources:

```bash
.venv/bin/python scripts/live_check.py
```

`live_check.py` merges evidence into `artifacts/live_runs/summary.json` and returns `0` for all success, `2` for partial success, and `1` for hard failure.

## API

Routes:

- `GET /health`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{id}`
- `GET /api/v1/sources`
- `GET /api/v1/coverage`
- `GET /api/v1/fetch-runs`
- `GET /` HTML search UI
- `GET /coverage` HTML coverage page

`/api/v1/jobs` supports `q`, `company`, `location`, `platform`, `status`, `limit`, `offset`, and `sort`. `limit` is capped at 100. `sort` is `relevance`, `newest`, or `oldest`. `status` is `open` or `closed`.

The API is read-only and unauthenticated. Bind it to localhost and use a TLS reverse proxy with access control if exposed.

## Outputs

- `data/jobs.db`: SQLite database with `source_instances`, `job_listings`, `canonical_jobs`, `job_changes`, `fetch_runs`, and FTS5 `canonical_job_search`.
- `artifacts/raw/{source_instance}/{run_id}.json`: raw API payloads for each fetch.
- `artifacts/live_runs/{source_instance}.json`: per-source live evidence.
- `artifacts/live_runs/summary.json`: merged live-check summary.

`data/` and `artifacts/raw/` are ignored by git.

## Configuration

Add employer instances to `config/sources.json`:

```json
{
  "name": "greenhouse-stripe",
  "platform": "greenhouse",
  "tenant": "stripe",
  "company": "Stripe",
  "options": {}
}
```

Platform options:

- Lever: `options.api_host`, optional `options.page_size`.
- SmartRecruiters: optional `options.page_size` from 1 to 100.
- Rippling: optional `options.page_size` from 1 to 1000, optional `options.max_pages`.
- Workday: required `options.host`, required `options.site`, optional `options.max_jobs` (default 500).

## Behavior

- Fetch statuses are uppercase: `SUCCESS`, `PARTIAL_SUCCESS`, `RATE_LIMITED`, `UNAUTHORIZED`, `BLOCKED`, `TIMEOUT`, `SCHEMA_CHANGED`, `FAILED`.
- Failed or partial scans never mark jobs missing or closed.
- First complete successful scan with a missing job marks it `missing`; the second marks it `closed`.
- Deduplication uses exact URL match first, then normalized company + title + location with description similarity threshold `0.55`.
- Ambiguous matches remain separate.

## Current limitations

- Workday uses an undocumented CXS API and is capped at 5 jobs per board in the live configuration. Those fetches are `PARTIAL_SUCCESS` and do not drive closure.
- Rippling, Workday, and SmartRecruiters require one detail request per posting.
- Teamtailor RSS may cap around 100 items; truncation is not detected.
- Recruitee documents an auth-token requirement starting 2027-02-10.
- Personio may omit direct apply URLs and descriptions.
- The API has no application-level authentication, authorization, or rate limiting.
- SQLite is suitable for the current scale, not high-concurrency distributed workers.

See `docs/known_limitations.md` for the full list.

## Documentation

- `docs/platform_matrix.csv`: 78-platform source of truth.
- `docs/research_notes.md`: research evidence and field observations.
- `docs/architecture.md`: architecture and design.
- `docs/connectors.md`: connector reference and field mappings.
- `docs/deployment.md`: deployment, scheduling, backup, and security.
- `docs/operating_costs.md`: cost and request-volume estimates.
- `docs/known_limitations.md`: coverage, data, API, and operational limitations.
- `docs/coverage_report.md`: coverage status and evidence.
- `docs/EXECUTION_LOG.md`: phase-by-phase execution history and defects fixed.
- `docs/final_report.md`: final handoff report.
- `docs/phase2_report.md` and `docs/phase3_report.md`: historical phase reports.
