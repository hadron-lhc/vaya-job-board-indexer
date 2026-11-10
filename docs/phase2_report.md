# Phase 2 Report: Greenhouse and Lever Vertical Slice

## Status

The first Phase 2 vertical slice is implemented and verified for review. It covers Greenhouse and Lever only, with two real employer instances per platform, normalized records, SQLite persistence, fetch-run tracking, deterministic tests, live tests, CLI support, and saved live evidence.

No additional platforms were implemented. No commits were made.

## Scope Delivered

- Greenhouse connector for:
  - `greenhouse-stripe` / Stripe
  - `greenhouse-airbnb` / Airbnb
- Lever connector for:
  - `lever-palantir` / Palantir
  - `lever-spotify` / Spotify
- Minimal connector interface with `fetch` and `normalize`.
- Source configuration through `config/sources.json`.
- SQLite tables:
  - `source_instances`
  - `job_listings`
  - `fetch_runs`
- Fetch-run statuses: `success`, `partial`, `failed`.
- Idempotent upserts keyed by `(platform, source_instance, external_job_id)`.
- Raw payload preservation under `artifacts/raw/`.
- CLI commands:
  - `list-sources`
  - `fetch --platform ... --source ...`
- Deterministic fixture tests and separate live tests.
- Live evidence under `artifacts/live_runs/`.

## Files Added

- `pyproject.toml`
- `.gitignore`
- `config/sources.json`
- `src/job_indexer/__init__.py`
- `src/job_indexer/__main__.py`
- `src/job_indexer/cli.py`
- `src/job_indexer/config.py`
- `src/job_indexer/db.py`
- `src/job_indexer/errors.py`
- `src/job_indexer/http.py`
- `src/job_indexer/models.py`
- `src/job_indexer/runner.py`
- `src/job_indexer/utils.py`
- `src/job_indexer/connectors/__init__.py`
- `src/job_indexer/connectors/base.py`
- `src/job_indexer/connectors/greenhouse.py`
- `src/job_indexer/connectors/lever.py`
- `src/job_indexer/connectors/registry.py`
- `tests/conftest.py`
- `tests/fixtures/README.md`
- `tests/fixtures/greenhouse_stripe.json`
- `tests/fixtures/lever_palantir.json`
- `tests/test_greenhouse.py`
- `tests/test_lever.py`
- `tests/test_db.py`
- `tests/test_runner.py`
- `tests/test_cli.py`
- `tests/live/test_live_sources.py`
- `scripts/live_check.py`
- `README.md` updated from title-only stub.
- `docs/platform_matrix.csv` updated for Greenhouse and Lever only.
- `docs/research_notes.md` status counts updated for the two live-tested platforms.
- `docs/phase2_report.md` added.

## Architecture Decisions

- Used synchronous `httpx` with connection reuse, explicit timeout, User-Agent, bounded retries, `Retry-After` handling, and clear `HttpError` messages.
- Used Python dataclasses instead of Pydantic to keep the dependency surface minimal.
- Used stdlib `sqlite3` instead of SQLAlchemy.
- Kept a minimal connector protocol: `fetch(source)` and `normalize(raw_job, source, checked_at)`.
- Kept one source instance per configured employer tenant; no cross-company merging.
- Preserved raw API payloads for auditability.
- Recorded failed fetches explicitly and never converted them into zero-job success.
- Preserved `first_seen_at` on updates and refreshed `last_checked_at`.
- Stored partial Lever results when later pages fail.
- Restricted Lever API hosts to `api.lever.co` and `api.eu.lever.co`, with page size capped at 100.
- Kept closure detection, deduplication, scheduling, workers, and frontend out of this phase.

## Live Verification

Pre-implementation evidence remains at `artifacts/live_runs/preflight.json`.

Latest live-check summary: `artifacts/live_runs/summary.json`.

Latest live-check results:

| Source | Platform | Status | Discovered | Processed | Inserted | Updated |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `greenhouse-stripe` | Greenhouse | success | 775 | 775 | 0 | 775 |
| `greenhouse-airbnb` | Greenhouse | success | 201 | 201 | 0 | 201 |
| `lever-palantir` | Lever | success | 304 | 304 | 0 | 304 |
| `lever-spotify` | Lever | success | 85 | 85 | 0 | 85 |

The `inserted=0` values are expected because these sources had already been persisted by earlier runs. The repeat run updated existing rows and did not create duplicates.

Current database counts:

| Source | Rows |
| --- | ---: |
| `greenhouse-stripe` | 775 |
| `greenhouse-airbnb` | 202 |
| `lever-palantir` | 304 |
| `lever-spotify` | 85 |

`greenhouse-airbnb` has 202 rows while the latest live response returned 201 jobs. This is expected: closure detection is not implemented, so disappeared jobs remain in the database.

Per-source evidence:

- `artifacts/live_runs/greenhouse-stripe.json`
- `artifacts/live_runs/greenhouse-airbnb.json`
- `artifacts/live_runs/lever-palantir.json`
- `artifacts/live_runs/lever-spotify.json`

Raw payloads were saved under `artifacts/raw/` and are ignored by git.

## Test Results

Deterministic tests:

```text
24 passed, 4 deselected
```

Command:

```bash
.venv/bin/python -m pytest -q
```

Live tests:

```text
4 passed, 24 deselected
```

Live test duration varies with network and API response time.

Command:

```bash
.venv/bin/python -m pytest -q -m live -o addopts=""
```

Coverage includes:

- Greenhouse fetch, normalization, missing optional fields, empty responses, invalid top-level shape, and missing required job fields.
- Lever fetch, normalization, missing optional fields, empty responses, invalid top-level shape, pagination, HTTP partial failure, invalid-JSON partial failure, and invalid API host.
- SQLite idempotency, duplicate IDs in one batch, `first_seen_at` preservation, and fetch-run lifecycle.
- Runner success, repeat-run idempotency, failed fetch recording, normalization failure recording, and partial fetch persistence.
- CLI source listing and unknown-source rejection.
- Live fetch and normalization for all four configured sources.

## Acceptance Criteria

- [x] Greenhouse connector works against two real employer instances.
- [x] Lever connector works against two real employer instances.
- [x] Normalized records include all required fields.
- [x] SQLite stores source instances, job listings, and fetch runs.
- [x] Fetch runs distinguish success, partial, and failed.
- [x] Failed fetch does not create zero-job success.
- [x] Upserts are idempotent and preserve `first_seen_at`.
- [x] HTTP client has timeout, User-Agent, bounded retries, and `Retry-After` handling.
- [x] Deterministic fixture tests exist.
- [x] Live tests are separated by marker.
- [x] CLI can fetch one configured source.
- [x] Live evidence is saved for all four sources.
- [x] No closure, deduplication, scheduler, worker, or frontend was added.
- [x] Matrix statuses were updated only for Greenhouse and Lever.

## Known Limitations

- Greenhouse does not expose a separate application URL in the jobs response; `application_url` is `null`.
- Lever EU host was not verified for real employers. Both configured Lever sources use the global `api.lever.co` host.
- No closure detection. Jobs missing from a later successful fetch remain in the database.
- No cross-company or cross-platform deduplication.
- No scheduler, background worker, or retry queue.
- No frontend or dashboard.
- Descriptions are stored as source HTML where provided.
- Live tests depend on public API availability and can change in duration or result count.
- The CLI prints sample descriptions, so output can be large for sources with long descriptions.

## Commands Used

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m compileall -q src
.venv/bin/python -m job_indexer list-sources --config config/sources.json
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q -m live -o addopts=""
.venv/bin/python scripts/live_check.py
```

## Remaining Work Before the Next Connector

- Review this slice and confirm the architecture and scope.
- Decide which platform from the matrix to add next.
- Add new connectors only after explicit approval.
- Add more tenant coverage for Greenhouse and Lever if needed.
- Consider Greenhouse application-URL extraction separately; no unverified endpoint was implemented.
- Keep closure detection, deduplication, scheduling, and frontend in later phases unless scope changes.
