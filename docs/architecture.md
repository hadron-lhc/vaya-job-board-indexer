# Architecture

Status: implemented 11-platform batch. This document reflects the current repository, not the original aspirational design.

## 1. Goals

- Collect jobs from multiple ATS platforms and tenants.
- Normalize listings into one consistent record.
- Preserve source and application links.
- Detect changes, missing jobs, and closures conservatively.
- Deduplicate the same opening across sources without unsafe merges.
- Expose search through a read-only API and minimal UI.
- Keep operations boring: one process, one SQLite database, raw evidence on disk.

## 2. Non-goals

- No microservices.
- No Kubernetes.
- No Redis, Celery, or external queue.
- No browser automation for the implemented platforms.
- No runtime LLM parsing.
- No authentication bypass, CAPTCHA solving, or hidden credential use.
- No claim of coverage without evidence.

## 3. Principles

1. Evidence over assumptions.
2. Fetch failure is not closure.
3. Conservative deduplication.
4. Source preservation.
5. Boring operations.
6. Idempotent ingestion.
7. Observable by default.
8. No secrets in logs or fixtures.

## 4. Runtime flow

```text
config/sources.json
        |
        v
  load_sources()
        |
        v
  build_connector(platform, HttpClient)
        |
        v
  connector.fetch(source)  ---> raw jobs, request URLs, raw payloads, pagination
        |
        v
  connector.normalize(raw_job, source, checked_at)
        |
        v
  upsert_jobs(conn, listings) ---> inserted, updated, changed
        |
        v
  apply_source_scan(conn, ...) ---> missing / closed lifecycle transitions
        |
        v
  canonical deduplication ---> canonical_jobs + canonical_job_search
        |
        v
  finish_fetch_run(conn, ...) ---> fetch_runs record
```

The runner owns HTTP retries, persistence, status classification, and evidence. Connectors own platform-specific parsing.

## 5. Repository layout

```text
.
├── README.md
├── pyproject.toml
├── config/
│   └── sources.json
├── docs/
│   ├── platform_matrix.csv
│   ├── research_notes.md
│   ├── architecture.md
│   ├── connectors.md
│   ├── deployment.md
│   ├── operating_costs.md
│   ├── known_limitations.md
│   ├── coverage_report.md
│   ├── EXECUTION_LOG.md
│   ├── final_report.md
│   └── phase2_report.md, phase3_report.md
├── scripts/
│   └── live_check.py
├── src/job_indexer/
│   ├── __main__.py
│   ├── api.py
│   ├── cli.py
│   ├── config.py
│   ├── coverage.py
│   ├── db.py
│   ├── errors.py
│   ├── http.py
│   ├── models.py
│   ├── runner.py
│   ├── utils.py
│   └── connectors/
│       ├── base.py
│       ├── registry.py
│       ├── greenhouse.py
│       ├── lever.py
│       ├── ashby.py
│       ├── workable.py
│       ├── smartrecruiters.py
│       ├── recruitee.py
│       ├── pinpoint.py
│       ├── personio.py
│       ├── teamtailor.py
│       ├── rippling.py
│       └── workday.py
├── tests/
│   ├── fixtures/
│   ├── live/
│   └── test_*.py
└── data/, artifacts/
```

## 6. Connector contract

```python
class Connector(Protocol):
    platform: str

    def fetch(self, source: SourceConfig) -> FetchBatch:
        ...

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        ...
```

`FetchBatch` contains:

- `raw_jobs`
- `request_urls`
- `source_url`
- `pagination`
- `complete`
- `raw_payloads`

Rules:

- `fetch` must return `complete=False` for truncated or partial scans.
- Partial fetches may raise `PartialFetchError` with a preserved batch.
- `normalize` must never invent missing values.
- Every connector has sanitized fixtures and deterministic tests.
- Every configured platform has live evidence.

## 7. Source registry

A source is a platform plus a tenant/board:

```json
{
  "name": "recruitee-bunq",
  "platform": "recruitee",
  "tenant": "bunq",
  "company": "bunq",
  "options": {}
}
```

`config/sources.json` is the runtime registry. `SourceConfig.from_dict()` validates required fields. `SUPPORTED_PLATFORMS` in `connectors/registry.py` controls which platforms can be built.

## 8. Normalized model

`JobListing` fields:

- `platform`
- `source_instance`
- `external_job_id`
- `title`
- `company`
- `description`
- `location`
- `source_url`
- `application_url`
- `salary`
- `employment_type`
- `remote_status` (`remote`, `hybrid`, `onsite`, `unknown`)
- `original_posted_at`
- `first_seen_at`
- `last_checked_at`

Optional fields remain `None` when the source does not provide them.

## 9. Persistence

SQLite tables:

### `source_instances`

Configured platform/tenant instances and options.

### `job_listings`

Source-level normalized jobs, keyed by `(platform, source_instance, external_job_id)`.

Lifecycle fields:

- `content_hash`
- `last_changed_at`
- `last_seen_at`
- `source_status` (`open`, `missing`, `closed`)
- `missing_scans`
- `last_missing_at`
- `closed_at`

Dedup fields:

- `canonical_job_id`
- `dedup_reason`
- `dedup_confidence`

### `canonical_jobs`

Cross-source deduplicated jobs with normalized title, company, location, description, status, and timestamps.

### `canonical_job_search`

FTS5 virtual table indexed by canonical job title, company, description, and location.

### `job_changes`

Field-level change history for listings.

### `fetch_runs`

Per-run status, counts, error details, error class, duration, raw payload path, and pagination JSON.

## 10. Lifecycle policy

- A complete successful scan that does not contain a previously seen job increments `missing_scans` and marks the listing `missing`.
- A second complete successful scan without the job marks it `closed`.
- A complete successful scan that sees the job again resets missing state.
- Failed, blocked, partial, rate-limited, timed-out, or schema-changed scans never change lifecycle state.
- Workday truncation is explicitly partial, so it cannot close jobs.

## 11. Deduplication policy

1. Exact source URL or application URL match.
2. Normalized company + title + location with description similarity at least `0.55`.
3. Ambiguous matches remain separate.

The policy prefers false negatives over unsafe merges. Canonical jobs preserve all source listings.

## 12. API and UI

`src/job_indexer/api.py` uses `ThreadingHTTPServer` from the Python standard library.

Routes:

- `GET /health`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{id}`
- `GET /api/v1/sources`
- `GET /api/v1/coverage`
- `GET /api/v1/fetch-runs`
- `GET /` HTML search UI
- `GET /coverage` HTML coverage page

The API is read-only. It has no application-level authentication or TLS. Deploy behind a reverse proxy for public access.

## 13. Evidence and observability

- Every fetch writes a `fetch_runs` row.
- Raw payloads are saved under `artifacts/raw/{source_instance}/{run_id}.json`.
- Live checks write `artifacts/live_runs/{source_instance}.json` and a merged `summary.json`.
- `coverage` reports matrix status counts and database job counts.

## 14. Failure handling

- HTTP retries are bounded and use exponential backoff with jitter.
- Retryable statuses: 429, 500, 502, 503, 504.
- `Retry-After` is honored up to 60 seconds.
- Errors are classified into fetch statuses and `error_class` values.
- Partial batches preserve fetched jobs and do not drive closure.
- Legacy database migration adds missing columns before creating indexes.

## 15. Scaling path

The current design is deliberately single-process and SQLite-backed. For larger scale:

- Add a scheduler/worker with per-source locks.
- Move to PostgreSQL for concurrent writes.
- Add rate limiting and bounded concurrency for N+1 detail fetches.
- Add a real ASGI API server and authentication.
- Add artifact retention and monitoring.
