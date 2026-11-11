# Vaya Job Board Indexer: Final Report

Date: 2026-11-10

## Executive summary

This repository implements a multi-tenant job board indexer with:

- 11 ATS connectors, each live-tested against two real employer tenants.
- 22 configured source instances.
- Normalized job listings with source and application URLs.
- SQLite persistence with idempotent upserts.
- Conservative lifecycle tracking, change history, and closure detection.
- Conservative cross-source deduplication into canonical jobs.
- FTS5 search, a read-only JSON API, and a minimal HTML UI.
- Fixture tests, live tests, raw evidence, and handoff documentation.

The implemented platforms are Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, Pinpoint, Personio, Teamtailor, Rippling, and Workday.

Coverage is 11 of 78 platforms (14.1%). This is a tested vertical slice, not a claim of full challenge coverage. The remaining 60 researched platforms, 6 access-blocked platforms, and 1 not-researched platform are documented in `docs/platform_matrix.csv`.

## What was delivered

### Connectors

Each connector implements a common contract:

- `fetch(source)` returns raw jobs, request URLs, raw payloads, pagination metadata, and a completeness flag.
- `normalize(raw_job, source, checked_at)` returns a normalized `JobListing`.
- Partial fetches preserve already-fetched jobs.
- Failed or partial fetches never drive closure.

Connector details are in `docs/connectors.md`.

### Data model

SQLite tables:

- `source_instances`: configured platform/tenant instances.
- `job_listings`: source-level normalized jobs with lifecycle fields.
- `canonical_jobs`: deduplicated cross-source jobs.
- `canonical_job_search`: FTS5 search index.
- `job_changes`: field-level change history.
- `fetch_runs`: per-run status, counts, errors, pagination, and evidence paths.

### Lifecycle and closure

- Each listing tracks `source_status`, `missing_scans`, `last_seen_at`, `last_missing_at`, and `closed_at`.
- First complete successful scan with a missing job marks it `missing`.
- Second complete successful scan marks it `closed`.
- Failed, blocked, partial, rate-limited, timed-out, or schema-changed scans never change lifecycle state.

### Deduplication

- Exact source or application URL match first.
- Normalized company + title + location with description similarity threshold `0.55`.
- Ambiguous matches remain separate.
- Canonical jobs preserve all source listings.

### API and UI

The API uses Python's standard library HTTP server:

- `GET /health`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{id}`
- `GET /api/v1/sources`
- `GET /api/v1/coverage`
- `GET /api/v1/fetch-runs`
- `GET /` HTML search UI
- `GET /coverage` HTML coverage page

The API is read-only and unauthenticated. Deploy behind a TLS reverse proxy with access control if exposed.

### Operations

- CLI: `fetch`, `fetch-all`, `list-sources`, `coverage`, `rebuild-dedup`, `serve`.
- Live evidence: `scripts/live_check.py`.
- Scheduling: cron or systemd timers.
- Deployment guidance: `docs/deployment.md`.
- Cost estimates: `docs/operating_costs.md`.

## Verification

Deterministic suite:

```text
110 passed, 22 deselected
```

Command:

```bash
.venv/bin/python -m pytest -q
```

Full live suite:

```text
22 passed
```

Command:

```bash
.venv/bin/python -m pytest -q -m live -o addopts=""
```

Live evidence for all configured sources:

```bash
.venv/bin/python scripts/live_check.py
```

Latest evidence summary: `artifacts/live_runs/summary.json`.

## Coverage

| Status | Count |
| --- | ---: |
| `LIVE_TESTED_MULTI_TENANT` | 11 |
| `RESEARCHED` | 60 |
| `ACCESS_BLOCKED` | 6 |
| `NOT_RESEARCHED` | 1 |
| Total | 78 |

Implemented: 11 ATS platforms, 0 job boards.

Detailed coverage: `docs/coverage_report.md`.

## Key limitations

- Workday uses an undocumented API and is capped at 5 jobs per board in the live configuration. Its fetches are `PARTIAL_SUCCESS`.
- Rippling, Workday, and SmartRecruiters use N+1 detail requests.
- Teamtailor RSS may be truncated and truncation is not detected.
- Recruitee has a documented auth-token requirement starting 2027-02-10.
- Personio may omit direct apply URLs and descriptions.
- The API has no application-level authentication, authorization, or rate limiting.
- SQLite is suitable for the current scale, not for high-concurrency distributed workers.
- Deduplication is deliberately conservative and can leave duplicates.
- Closure requires two complete successful scans.

Full list: `docs/known_limitations.md`.

## Defects found and fixed

- Legacy database migration created indexes before adding referenced columns.
- API `source_count` `KeyError`.
- API broad `LookupError` catch masking missing jobs.
- Teamtailor nested location parsing.
- Workday detail URL prefix.
- Workday truncation status.
- Live-check uppercase status comparison and summary overwrite behavior.

Details: `docs/EXECUTION_LOG.md`.

## Recommended next steps

1. Implement additional verified public feeds from the 60 `RESEARCHED` rows.
2. Add rate limiting and bounded concurrency for detail-heavy connectors.
3. Raise Workday coverage after adding request budgets and concurrency controls.
4. Add scheduler/worker execution and monitoring.
5. Add API authentication and TLS termination for non-local deployment.
6. Resolve or document the 6 `ACCESS_BLOCKED` platforms.
7. Add more tenant coverage for existing platforms.
8. Add retention and backup automation for raw artifacts and SQLite.

## Repository map

- `config/sources.json`: 22 configured sources.
- `src/job_indexer/connectors/`: 11 connector modules plus registry.
- `src/job_indexer/db.py`: schema, migration, lifecycle, deduplication, search.
- `src/job_indexer/runner.py`: fetch orchestration and status classification.
- `src/job_indexer/api.py`: HTTP API and HTML UI.
- `src/job_indexer/coverage.py`: coverage reporting.
- `src/job_indexer/cli.py`: command-line interface.
- `tests/`: deterministic and live tests.
- `artifacts/live_runs/`: live evidence.
- `docs/`: research, architecture, connector reference, deployment, costs, limitations, coverage, execution log.

## Status

The implementation is complete for the 11-platform batch and verified by deterministic tests, live connector tests, and live evidence. Changes remain uncommitted unless explicitly requested.
