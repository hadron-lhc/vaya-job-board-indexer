# Vaya Requirements Compliance Audit

Source: <https://vayahq.com/challenge/build-a-job-board-indexer-for-10000>
Audit date: 2026-11-11
Deadline: 2026-11-30

This document maps the published Vaya completion criteria to the current repository. It distinguishes implemented behavior from remaining gaps. It does not claim coverage that has not been verified.

## Overall status

| Criterion | Status | Evidence | Remaining gap |
| --- | --- | --- | --- |
| Working coverage across all 78 platforms | Partial | 15 platforms (14 ATS + 1 job board), 30 sources, live evidence | 63 platforms lack connectors: 56 researched, 6 access-blocked, 1 not researched |
| Coverage checklist with live examples and runs | Implemented | Generated `docs/coverage_checklist.md` and `artifacts/coverage/checklist.json` for all 78 platforms | Research-only rows have no live evidence by definition |
| Connectors work across different employers/boards | Partial | Two tenants for each of 15 platforms, including Niceboard as a job board | 44 ATS and 19 job-board platforms have no connector |
| Consistent job records | Implemented | `JobListing`, `job_listings`, normalization tests | Some sources cannot provide application URL or posting date |
| Title, company, description, location | Implemented | Normalized model and tests | Optional source gaps documented |
| Source URL and application URL | Implemented | Preserved per listing | Greenhouse and Personio may have `application_url=null` |
| Salary, employment type, remote status, posting date when provided | Implemented | Normalizers and fixtures | Source-dependent; missing values stay `null` |
| Track first seen and last checked | Implemented | `first_seen_at`, `last_checked_at` | None |
| Automatic updates | Implemented | CLI `fetch-all`, built-in `schedule` command, cron/systemd examples | Scheduler monitoring/alerting is minimal |
| Detect changes | Implemented | `content_hash`, `job_changes` | None |
| Remove or mark closed listings | Implemented | Conservative `missing`/`closed` lifecycle | Requires two complete successful scans |
| Failed request recorded as fetch failure, not closure | Implemented | `fetch_runs`, `PARTIAL_SUCCESS`, lifecycle guards | None |
| Deduplication across sources | Implemented | `canonical_jobs`, URL and fuzzy matching | Conservative; ambiguous duplicates can remain |
| Preserve source links | Implemented | `canonical_jobs` API returns all sources | None |
| Keep distinct roles separate | Implemented | Conservative threshold and tests | None |
| Working search interface | Implemented | `GET /`, HTML search UI | Minimal UI |
| Documented API with pagination and filters | Implemented | `GET /api/v1/jobs`, README, architecture | No OpenAPI document |
| Filters for keyword, company, location | Implemented | `q`, `company`, `location` | None |
| Source code | Implemented | Repository | Uncommitted changes |
| Deployment instructions | Implemented | `docs/deployment.md` | No container image or CI pipeline |
| Connector documentation | Implemented | `docs/connectors.md` | None |
| Operating costs | Implemented | `docs/operating_costs.md` | Estimates only |
| External service/data dependencies | Implemented | README, deployment, known limitations | No formal dependency inventory |

## Critical gap: platform coverage

The challenge requires all 58 ATS platforms and all 20 job-board platforms. Current coverage is 14 ATS platforms and 1 job board.

| Category | Required | Implemented | Coverage |
| --- | ---: | ---: | ---: |
| ATS | 58 | 14 | 24.1% |
| Job boards | 20 | 1 | 5.0% |
| Total | 78 | 15 | 19.2% |

The 15 implemented platforms are Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, Pinpoint, Personio, Teamtailor, Rippling, Workday, Breezy HR, BambooHR, JazzHR, and Niceboard.

## What is required next for full compliance

1. Implement the remaining 44 ATS platforms with live-verified tenants.
2. Implement the remaining 19 job-board platforms, including HTML/JSON-LD fallbacks where no public API exists.
3. Resolve or document the 6 access-blocked platforms and the 1 not-researched platform.
4. Add CI, linting, and type checking.
5. Add OpenAPI or equivalent API documentation.
6. Add a demo deployment and submission artifacts.

## Compliance risks

- Full 78-platform coverage is not achievable with the current connector count before 2026-11-30.
- 15 of 78 platforms are live-verified; the remaining 63 are documented but not implemented.
- Several platforms require enterprise credentials or contracts.
- HTML-first platforms need per-platform fixtures and breakage monitoring.
- Job-board platforms have heterogeneous or unverified feeds.
- The API is unauthenticated and intended for local/reverse-proxy deployment.
- Workday live evidence is partial by configuration (`max_jobs=5`).

## Rule

No platform is marked `LIVE_TESTED_MULTI_TENANT` without live evidence and a successful normalized run. Research-only rows remain `RESEARCHED`.
