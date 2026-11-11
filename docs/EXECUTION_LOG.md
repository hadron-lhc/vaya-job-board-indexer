# Execution Log

Project: Vaya Job Board Indexer
Repository: `vaya-job-board-indexer`
Last updated: 2026-11-10

This log records the phases executed, commands run, outcomes, and defects fixed. It is not a commit log. Changes remain uncommitted unless explicitly requested.

## Phase 1: Research and matrix

- Audited the challenge scope: 78 platforms, 58 ATS and 20 job boards.
- Built `docs/platform_matrix.csv` with exactly 78 rows and 16 columns.
- Verified public endpoints where possible with live HTTP requests.
- Recorded access blocks and unknown platforms instead of guessing.
- Initial status counts: 66 `RESEARCHED`, 5 `LIVE_TESTED_MULTI_TENANT`, 6 `ACCESS_BLOCKED`, 1 `NOT_RESEARCHED`.
- Wrote `docs/research_notes.md` with evidence, field observations, and caveats.

## Phase 2: Greenhouse and Lever vertical slice

- Implemented the connector protocol, HTTP client, normalized `JobListing` model, SQLite persistence, fetch-run tracking, CLI, and fixtures.
- Added Greenhouse and Lever connectors with two live tenants each.
- Added deterministic and live tests.
- Preserved raw payloads under `artifacts/raw/`.
- Documented the slice in `docs/phase2_report.md`.

## Phase 3: Ashby, Workable, SmartRecruiters

- Added Ashby, Workable, and SmartRecruiters connectors with two live tenants each.
- Added offset/limit pagination and per-posting detail fetching for SmartRecruiters.
- Added duplicate-shortcode and multi-location merging for Workable.
- Added partial-fetch handling for list and detail failures.
- Added fixtures, deterministic tests, live tests, and live evidence.
- Documented the batch in `docs/phase3_report.md`.
- Deterministic suite at the end of this phase: `51 passed, 10 deselected`.
- Live suite at the end of this phase: `10 passed, 51 deselected`.

## Phase 4: Lifecycle, deduplication, search, API, and UI

- Added lifecycle columns to `job_listings`: `content_hash`, `last_changed_at`, `last_seen_at`, `source_status`, `missing_scans`, `last_missing_at`, `closed_at`.
- Added `job_changes` for field-level change history.
- Added `canonical_jobs` and FTS5 `canonical_job_search`.
- Added `canonical_job_id`, `dedup_reason`, and `dedup_confidence` to listings.
- Implemented conservative missing/closure policy:
  - first complete successful scan with a missing job marks it `missing`;
  - second complete successful scan marks it `closed`;
  - failed or partial scans never change lifecycle state.
- Implemented conservative deduplication:
  - exact source or application URL match first;
  - normalized company + title + location with description similarity threshold `0.55`;
  - ambiguous matches remain separate.
- Extended `fetch_runs` with `jobs_changed`, `jobs_missing`, `jobs_closed`, and `error_class`.
- Added `coverage.py`, `api.py`, and CLI commands `fetch-all`, `coverage`, `rebuild-dedup`, and `serve`.
- Added tests for lifecycle, deduplication, and API.
- Fixed API `source_count` `KeyError`.
- Fixed API error handling so `NotFoundError` returns 404 and is not swallowed by a broad `LookupError` catch.
- Deterministic suite after lifecycle/dedup: `61 passed, 10 deselected`.
- API suite after fixes: `6 passed`.

## Phase 5: Recruitee, Pinpoint, Personio, Teamtailor, Rippling, Workday

- Probed live endpoints and selected two tenants per platform.
- Implemented six connectors:
  - Recruitee
  - Pinpoint
  - Personio
  - Teamtailor
  - Rippling
  - Workday
- Added `HttpClient.post` for Workday's POST list endpoint.
- Added XML parsing for Personio and RSS parsing for Teamtailor.
- Added nested `tt:location` parsing for Teamtailor.
- Added pagination and per-posting detail requests for Rippling.
- Added POST list pagination and per-posting detail requests for Workday.
- Added `max_jobs` truncation for Workday. Truncated fetches raise `PartialFetchError`, are recorded as `PARTIAL_SUCCESS`, and do not drive closure.
- Added sanitized fixtures and deterministic tests for all six connectors.
- Updated `config/sources.json` from 10 to 22 sources.
- Updated live tests for all 22 sources, including Workday partial behavior.
- Updated the platform matrix from 5 to 11 `LIVE_TESTED_MULTI_TENANT` platforms.
- Updated research notes and counts.

## Phase 6: Verification and handoff documentation

- Fixed a legacy-database migration defect: indexes on new columns were created before the columns were added.
- Split table creation and index creation so `init_db()` migrates old databases before creating indexes.
- Added a regression test for legacy schema migration.
- Fixed `scripts/live_check.py`:
  - statuses are uppercase;
  - partial success is reported separately from hard failure;
  - existing summary evidence is merged instead of overwritten.
- Ran live checks for all 22 configured sources and wrote evidence under `artifacts/live_runs/`.
- Added handoff documentation: connectors, deployment, operating costs, known limitations, coverage report, and final report.
- Updated `README.md`.

## Verification results

Deterministic tests:

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

Live evidence command:

```bash
.venv/bin/python scripts/live_check.py
```

Expected exit codes for `live_check.py`: `0` all success, `2` at least one partial success, `1` at least one hard failure.

## Current live evidence summary

| Source | Status | Discovered | Processed |
| --- | --- | ---: | ---: |
| `greenhouse-stripe` | SUCCESS | 778 | 778 |
| `greenhouse-airbnb` | SUCCESS | 202 | 202 |
| `lever-palantir` | SUCCESS | 304 | 304 |
| `lever-spotify` | SUCCESS | 86 | 86 |
| `ashby-ashby` | SUCCESS | 76 | 76 |
| `ashby-openai` | SUCCESS | 827 | 827 |
| `workable-huggingface` | SUCCESS | 6 | 6 |
| `workable-runware` | SUCCESS | 24 | 24 |
| `smartrecruiters-canva` | SUCCESS | 36 | 36 |
| `smartrecruiters-innergy` | SUCCESS | 7 | 7 |
| `recruitee-bunq` | SUCCESS | 26 | 26 |
| `recruitee-tellent` | SUCCESS | 13 | 13 |
| `pinpoint-avaaz` | SUCCESS | 2 | 2 |
| `pinpoint-workwithus` | SUCCESS | 4 | 4 |
| `personio-lanch` | SUCCESS | 9 | 9 |
| `personio-deskbird` | SUCCESS | 4 | 4 |
| `teamtailor-bankgirotab` | SUCCESS | 2 | 2 |
| `teamtailor-doconomy` | SUCCESS | 2 | 2 |
| `rippling-netatwork` | SUCCESS | 18 | 18 |
| `rippling-realwork` | SUCCESS | 4 | 4 |
| `workday-salesforce` | PARTIAL_SUCCESS | 5 | 5 |
| `workday-adobe` | PARTIAL_SUCCESS | 5 | 5 |

Workday rows are partial by configuration (`max_jobs=5`). They are useful as live schema evidence, not as complete board coverage.

## Defects fixed

1. API `source_count` `KeyError` when a source had no count.
2. API `LookupError` catch incorrectly converted missing jobs into 404 for unrelated failures.
3. Legacy database migration failed because indexes referenced columns before `ALTER TABLE`.
4. `scripts/live_check.py` compared uppercase statuses to lowercase `success`.
5. Teamtailor locations were initially read as text; the feed stores them under nested `tt:location` elements.
6. Workday detail URL initially omitted the `/wday/cxs/{tenant}/{site}` prefix.
7. Workday truncation initially returned `SUCCESS` with `complete=false`; it now raises `PartialFetchError` so status is `PARTIAL_SUCCESS`.

## Remaining work

- Implement additional platforms from the 60 `RESEARCHED` rows.
- Resolve or document the 6 `ACCESS_BLOCKED` platforms.
- Resolve the 1 `NOT_RESEARCHED` platform.
- Add scheduler/worker execution and monitoring.
- Add API authentication and TLS termination for non-local deployment.
- Increase Workday coverage beyond the live-test cap.
- Add rate limiting and detail-fetch concurrency controls for Rippling, Workday, and SmartRecruiters.
