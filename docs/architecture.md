# Architecture

Status: Phase 1 proposal. No application code exists yet.

## 1. Goals

Build a reliable, maintainable job indexer that:

- Collects jobs from 58 ATS platforms and 20 job-board platforms.
- Normalizes listings into one consistent record.
- Preserves source and application links.
- Detects changes, failures, and closures.
- Deduplicates the same opening across sources.
- Exposes search and a documented API.
- Can be handed off and operated by another team.

## 2. Non-goals

- No microservices.
- No Kubernetes.
- No Redis or Celery for the MVP.
- No browser automation unless a platform cannot be fetched otherwise.
- No runtime LLM parsing per listing.
- No authentication bypass, CAPTCHA solving, or hidden credential use.
- No claim of coverage without evidence.

## 3. Principles

1. **Evidence over assumptions.** Every connector has fixtures, a live check, and a documented limitation.
2. **Fetch failure is not closure.** Failed scans never close jobs.
3. **Conservative deduplication.** Prefer false negatives over merging genuinely distinct roles.
4. **Source preservation.** Keep every source URL and application URL.
5. **Boring operations.** One process, one database, one deployment.
6. **Idempotent ingestion.** Re-running a scan must not create duplicates.
7. **Observable by default.** Every scan produces a fetch run record and metrics.
8. **No secrets in logs or fixtures.**

## 4. High-level architecture

```text
                 +-------------------+
                 |  Source registry  |
                 |  (platform/tenant)|
                 +---------+---------+
                           |
                           v
+----------+      +--------+--------+      +------------------+
| Scheduler| ---> | Connector runner | ---> |  Raw payloads    |
| (cron /  |      |  (asyncio pool)  |      |  + fetch logs    |
|  worker) |      +--------+--------+      +--------+---------+
+----------+               |                        |
                           v                        v
                  +--------+--------+      +--------+---------+
                  | Platform adapter | ---> | Normalizer       |
                  | JSON/XML/RSS/HTML|      | + validator      |
                  +--------+--------+      +--------+---------+
                           |                        |
                           v                        v
                  +--------+--------+      +--------+---------+
                  | Dedup / merge    | ---> | SQLite / Postgres|
                  | + closure policy |      | jobs, sources,   |
                  +--------+--------+      | runs, configs    |
                           |               +--------+---------+
                           v                        |
                  +--------+--------+               v
                  | Search index    | ---> +--------+---------+
                  | SQLite FTS5     |      | FastAPI + UI     |
                  +-----------------+      +------------------+
```

## 5. Recommended repository layout

```text
.
├── README.md
├── pyproject.toml
├── docs/
│   ├── platform_matrix.csv
│   ├── research_notes.md
│   ├── feasibility_report.md
│   └── architecture.md
├── src/job_indexer/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── schemas.py
│   ├── http.py
│   ├── scheduler.py
│   ├── worker.py
│   ├── normalization.py
│   ├── dedup.py
│   ├── closure.py
│   ├── coverage.py
│   ├── api/
│   │   ├── app.py
│   │   ├── routes_jobs.py
│   │   ├── routes_sources.py
│   │   └── routes_coverage.py
│   ├── connectors/
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── greenhouse.py
│   │   ├── lever.py
│   │   ├── ashby.py
│   │   ├── workable.py
│   │   ├── smartrecruiters.py
│   │   ├── recruitee.py
│   │   ├── personio.py
│   │   ├── teamtailor.py
│   │   ├── pinpoint.py
│   │   ├── rippling.py
│   │   ├── workday.py
│   │   └── ...
│   └── extractors/
│       ├── jsonld.py
│       ├── html.py
│       └── xml.py
├── tests/
│   ├── fixtures/
│   ├── test_connectors/
│   ├── test_normalization.py
│   ├── test_dedup.py
│   └── test_api.py
└── scripts/
    ├── scan.py
    └── verify_coverage.py
```

## 6. Connector contract

Each platform adapter implements a small, testable interface. The runner owns HTTP, retries, persistence, and logging; the adapter owns platform-specific parsing.

```python
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass(frozen=True)
class SourceConfig:
    id: str
    platform: str
    tenant: str
    base_url: str
    enabled: bool = True
    options: dict[str, Any] | None = None

@dataclass
class FetchBatch:
    raw_jobs: list[dict[str, Any]]
    next_cursor: str | None
    complete: bool
    source_url: str
    notes: list[str]

class Connector(Protocol):
    platform: str

    async def fetch(
        self,
        source: SourceConfig,
        cursor: str | None = None,
    ) -> FetchBatch:
        ...

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
    ) -> dict[str, Any]:
        ...
```

Rules:

- `fetch` must return `complete=False` for partial scans.
- `normalize` must never invent missing values.
- Connector-specific fields go in `raw` or `extra`, not into ad hoc database columns.
- Every connector has a fixture file and at least one live smoke test.
- Every connector declares its auth mode and rate limit.

## 7. Source registry

A source is a platform plus a tenant/board:

```text
greenhouse:stripe
lever:leverdemo
ashby:ashby
workable:huggingface
smartrecruiters:linkedin3
recruitee:bunq
personio:lanch
teamtailor:bankgirotab
pinpoint:avaaz
rippling:rippling
workday:nvidia/NVIDIAExternalCareerSite
```

The registry stores:

- Platform name.
- Tenant/board identifier.
- Base URL.
- Connector version.
- Enabled flag.
- Scan interval.
- Last successful scan.
- Consecutive failure count.
- Coverage status and evidence link.

## 8. Normalized job model

Core fields:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID/string | Internal stable ID. |
| `platform` | string | Canonical platform name. |
| `source_id` | string | Source registry ID. |
| `source_job_id` | string | Platform job ID when available. |
| `title` | string | Required. |
| `company_name` | string | Required; use source metadata or tenant. |
| `description_html` | text/null | Original HTML when available. |
| `description_text` | text/null | Plain text for search. |
| `location_text` | string/null | Human-readable location. |
| `city` | string/null | Optional normalized city. |
| `region` | string/null | Optional normalized region. |
| `country` | string/null | Optional ISO country. |
| `remote_status` | enum | `remote`, `hybrid`, `onsite`, `unknown`. |
| `employment_type` | string/null | Full-time, contract, etc. |
| `salary_min` | decimal/null | Optional. |
| `salary_max` | decimal/null | Optional. |
| `salary_currency` | string/null | ISO currency. |
| `salary_period` | string/null | year/month/hour. |
| `posted_at` | datetime/null | Original posting date when provided. |
| `first_seen_at` | datetime | Set on first ingest. |
| `last_seen_at` | datetime | Set on successful scan. |
| `last_checked_at` | datetime | Set on every attempt. |
| `status` | enum | `open`, `stale`, `closed`, `unknown`. |
| `source_url` | string | Original listing URL. |
| `application_url` | string/null | Direct apply URL when available. |
| `content_hash` | string | Hash of normalized content for change detection. |
| `dedup_key` | string | Conservative dedup key. |
| `raw_ref` | string/null | Pointer to stored raw payload. |
| `created_at` | datetime | Record creation. |
| `updated_at` | datetime | Record update. |

Related tables:

- `job_sources`: one row per source link for a canonical job. Supports deduplication across sources.
- `job_changes`: field-level change history.
- `fetch_runs`: one row per scan attempt.
- `fetch_failures`: one row per failed request with error class and retry count.
- `source_configs`: registry.
- `coverage_snapshots`: periodic coverage counts by platform/status.

## 9. Extraction pipeline

1. Load enabled sources that are due.
2. Apply per-host rate limits.
3. Fetch with `httpx.AsyncClient`, timeout, retries, and exponential backoff.
4. Record a `fetch_run` before parsing.
5. Parse based on adapter type:
   - JSON: adapter-specific parser.
   - XML/RSS: safe parser with entity handling.
   - HTML: `selectolax` plus JSON-LD extraction.
6. Validate each raw job against a Pydantic schema.
7. Normalize fields.
8. Compute `content_hash`.
9. Upsert source-level record.
10. Run deduplication and merge.
11. Update closure state only if the scan was complete and successful.
12. Update coverage snapshot.
13. Emit structured logs and metrics.

## 10. Deduplication

Deduplication is deliberately conservative.

### Stage 1: source-level identity

Use the platform's job ID when available:

- Greenhouse `id`
- Lever `id`
- Ashby `id`
- Workable `shortcode`
- SmartRecruiters `id`
- Recruitee `id`
- Personio `id`
- Pinpoint `id`
- Rippling `id`
- Workday `externalPath`

If no source ID exists, use a hash of `source_url`.

### Stage 2: cross-source candidate

Create a candidate key from:

- Normalized company name.
- Normalized title.
- Normalized location.
- Optional requisition ID.

Then apply guardrails:

- Do not merge if locations are clearly incompatible.
- Do not merge if employment types conflict.
- Do not merge if salary ranges conflict materially.
- Require description similarity above a threshold for ambiguous cases.
- Preserve every source link in `job_sources`.
- Keep distinct roles separate when the title/location/requisition signals differ.

### Stage 3: human-review queue

Ambiguous candidates go to a review table rather than being auto-merged. This is safer than aggressive deduplication.

## 11. Update and closure semantics

Job states:

- `open`: seen in the latest successful complete scan.
- `stale`: not seen recently, but closure conditions are not met.
- `closed`: missing from multiple successful complete scans after a grace period.
- `unknown`: source has never completed a successful scan.

Closure policy:

1. A fetch failure increments `fetch_failures` and never changes job status.
2. A partial scan never closes jobs.
3. A job missing from a complete successful scan gets `last_missing_at`.
4. After two consecutive complete successful scans and a 7-day grace period, mark `closed`.
5. Never delete records; keep history and source links.
6. Allow manual override for false closures.

This directly satisfies the challenge requirement that a failed request is not proof that every job has closed.

## 12. Scheduling

MVP scheduler:

- A single worker process.
- SQLite-backed `scan_queue` table.
- `asyncio` task pool with per-host concurrency limits.
- System cron or a small in-process loop.
- No Redis, Celery, or Kubernetes.

Scan cadence:

- High-value sources: every 6-12 hours.
- Long-tail sources: every 24 hours.
- Failed sources: exponential backoff with a cap.
- Manual full refresh available through a CLI.

Rate limiting:

- Per-host semaphore.
- Minimum delay between requests.
- Respect `Retry-After`.
- Exponential backoff with jitter.
- Clear user agent with contact information.

## 13. Storage

MVP: SQLite.

- Simple deployment.
- FTS5 for keyword search.
- WAL mode for concurrent reads.
- Daily backup of the database file.

Upgrade path: PostgreSQL if concurrency or data volume grows. The repository layer should hide the database choice.

Schema highlights:

```sql
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_job_id TEXT,
  title TEXT NOT NULL,
  company_name TEXT NOT NULL,
  description_html TEXT,
  description_text TEXT,
  location_text TEXT,
  remote_status TEXT NOT NULL DEFAULT 'unknown',
  employment_type TEXT,
  salary_min NUMERIC,
  salary_max NUMERIC,
  salary_currency TEXT,
  salary_period TEXT,
  posted_at TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT,
  last_checked_at TEXT,
  status TEXT NOT NULL DEFAULT 'unknown',
  source_url TEXT NOT NULL,
  application_url TEXT,
  content_hash TEXT NOT NULL,
  dedup_key TEXT,
  raw_ref TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE job_sources (
  job_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_job_id TEXT,
  source_url TEXT NOT NULL,
  application_url TEXT,
  last_seen_at TEXT,
  PRIMARY KEY (job_id, source_id, source_url)
);

CREATE TABLE fetch_runs (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  http_status INTEGER,
  jobs_seen INTEGER NOT NULL DEFAULT 0,
  jobs_new INTEGER NOT NULL DEFAULT 0,
  jobs_updated INTEGER NOT NULL DEFAULT 0,
  complete INTEGER NOT NULL DEFAULT 0,
  error_class TEXT,
  error_message TEXT
);
```

## 14. API

FastAPI endpoints:

- `GET /health` — process and database health.
- `GET /api/v1/jobs` — paginated search.
- `GET /api/v1/jobs/{id}` — job detail with source links.
- `GET /api/v1/companies` — company facets.
- `GET /api/v1/sources` — source registry and last scan status.
- `GET /api/v1/coverage` — platform coverage summary.
- `GET /api/v1/fetch-runs` — recent scan history.

`GET /api/v1/jobs` filters:

- `q` keyword.
- `company`.
- `location`.
- `platform`.
- `remote`.
- `employment_type`.
- `posted_after`.
- `status`.
- `limit` and `cursor`.

Response includes:

- Normalized job fields.
- All source links.
- First seen and last checked timestamps.
- Coverage confidence for the source.

## 15. Search

MVP: SQLite FTS5 over `title`, `company_name`, `description_text`, and `location_text`.

Ranking signals:

- Keyword relevance.
- Recency.
- Source freshness.
- Company match.
- Location match.

The UI is a thin server-rendered or static frontend over the API. No separate frontend framework is required for the MVP.

## 16. Observability

- Structured JSON logs with source ID, run ID, platform, status, duration, and error class.
- `fetch_runs` and `fetch_failures` tables for auditability.
- Coverage dashboard counts:
  - Platforms with at least one successful live scan.
  - Platforms with only fixture tests.
  - Platforms blocked or unverified.
  - Sources with consecutive failures.
- Metrics:
  - Jobs seen/new/updated per run.
  - Fetch success rate.
  - Median latency per platform.
  - Closure counts.
  - Dedup merge counts.
- Alerts:
  - Source failing repeatedly.
  - Zero jobs from a source that previously returned jobs.
  - Database backup failure.

## 17. Security and compliance

- Store secrets in environment variables or a local secret file excluded from git.
- Never log tokens, cookies, or authorization headers.
- Review each platform's terms and robots policy before enabling a connector.
- Do not bypass authentication, CAPTCHA, or rate limits.
- Use a clear user agent with contact information.
- Sanitize HTML from job descriptions before rendering.
- Validate all external URLs before redirecting users.
- Keep raw payloads only as long as needed; redact personal data.

## 18. Testing

Test layers:

1. **Unit tests**: normalization, hashing, dedup keys, closure policy.
2. **Fixture tests**: one sanitized fixture per connector, checked into `tests/fixtures`.
3. **Contract tests**: every connector returns the required normalized fields.
4. **Live smoke tests**: opt-in, one tenant per platform, marked `live`.
5. **Multi-tenant tests**: at least two tenants for high-confidence platforms.
6. **API tests**: pagination, filters, and response schema.
7. **Failure tests**: timeouts, 403, 429, malformed JSON, empty payloads, and partial scans.

Rules:

- Live tests are not part of the default unit test run.
- Fixtures must not contain secrets or personal data.
- A connector cannot be marked `LIVE_TESTED_ONE_TENANT` without a recorded run.
- A connector cannot be marked `VERIFIED` without multi-tenant evidence.

## 19. Deployment and operations

MVP deployment:

- One FastAPI process.
- One worker process.
- One SQLite database file.
- Systemd services or a simple Docker Compose file.
- Daily database backup.
- No Kubernetes.

Operating cost:

- Near zero for development.
- Small VPS or free-tier host for the demo.
- No paid proxy or LLM service required for the initial connector set.
- Optional paid plans only for job-board APIs that require them.

Runbook:

1. Start API and worker.
2. Check `/health`.
3. Run `scripts/verify_coverage.py`.
4. Inspect `/api/v1/coverage`.
5. Review failed sources.
6. Restore from backup if needed.

## 20. Coverage dashboard

The dashboard must show the truth, not a marketing count.

Columns:

- Platform.
- Category.
- Extraction method.
- Auth mode.
- Evidence URL.
- Last successful scan.
- Tenants tested.
- Jobs seen.
- Status: `RESEARCHED`, `ACCESS_BLOCKED`, `IMPLEMENTED`, `FIXTURE_TESTED`, `LIVE_TESTED_ONE_TENANT`, `LIVE_TESTED_MULTI_TENANT`, `VERIFIED`.
- Known limitation.

This dashboard is the handoff artifact that prevents overclaiming.

## 21. Phase plan

### Phase 1 (complete)

- Audit repository.
- Research 78 platforms.
- Create matrix, notes, feasibility report, and architecture.

### Phase 2 (next)

- Core framework.
- SQLite schema.
- Fetch runner.
- First 6 connectors: Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee.
- Fixture tests and live smoke tests.

### Phase 3

- Personio, Teamtailor, Pinpoint, Rippling, Workday.
- HTML/JSON-LD extractors.
- Search API and UI.

### Phase 4

- Deduplication and closure.
- Scheduler and observability.
- Coverage dashboard.
- Deployment and handoff docs.

### Phase 5

- Remaining public HTML connectors.
- Authenticated/contract platforms when access is available.
- Multi-tenant verification.

## 22. Key tradeoffs

- **SQLite vs PostgreSQL**: SQLite is simpler and sufficient for the MVP; PostgreSQL is a later scaling option.
- **One worker vs queue**: a SQLite-backed worker avoids Redis/Celery complexity; it limits throughput but is appropriate for the deadline.
- **Conservative dedup vs high recall**: conservative dedup reduces false merges but may leave duplicates; this is the safer choice for a job index.
- **HTML fallback vs browser automation**: HTML is cheaper and faster; browser automation is a last resort because of operational cost.
- **Partial coverage vs overclaiming**: the architecture prioritizes truthful coverage reporting over a superficial 78/78 claim.
