# Phase 3 Report: Ashby, Workable, and SmartRecruiters

## Status

Phase 3 is implemented and ready for review. Three connectors were added: **Ashby**, **Workable**, and **SmartRecruiters**. Each connector has two configured real employer instances, deterministic fixture tests, a live smoke test, normalization coverage, and saved live evidence.

No other platform was implemented. No closure detection, cross-source deduplication, scheduling, workers, frontend, or AI extraction was added. Changes are uncommitted pending review.

## Candidate Ranking

The six primary candidates were ranked by public accessibility, verified tenants, field completeness, implementation effort, and long-term operational risk.

| Rank | Platform | Evidence | Decision |
| ---: | --- | --- | --- |
| 1 | Ashby | Public JSON; `ashby` returned 75 jobs and `openai` returned 831 jobs; full descriptions, apply URLs, compensation, remote metadata; no pagination. | Selected. |
| 2 | Workable | Public JSON; `huggingface` returned 6 jobs and `runware` returned 55 postings / 24 unique shortcodes; full descriptions, apply URLs, locations, remote flags; no pagination. | Selected. |
| 3 | SmartRecruiters | Public JSON; `Canva` returned 36 jobs and `innergy1` returned 7; offset/limit pagination; full descriptions and apply URLs require one detail request per posting. | Selected. |
| 4 | Recruitee | Simple public JSON with full fields and multiple real tenants, but Recruitee documents an auth-token requirement starting 2027-02-10. | Not selected in this batch because of future access risk. |
| 5 | Pinpoint | Simple public JSON, full descriptions, no pagination, but only one tenant was verified during Phase 1 and no second real tenant was confirmed in this batch. | Not selected. |
| 6 | Personio | Public XML, full descriptions, no pagination, but requires an XML parser and the feed may not expose a direct application URL. | Not selected. |

Teamtailor was also probed, but its RSS feed is less complete for descriptions and was not selected.

## Scope Delivered

- Ashby connector for:
  - `ashby-ashby` / Ashby
  - `ashby-openai` / OpenAI
- Workable connector for:
  - `workable-huggingface` / Hugging Face
  - `workable-runware` / Runware
- SmartRecruiters connector for:
  - `smartrecruiters-canva` / Canva
  - `smartrecruiters-innergy` / INNERGY
- Registry support for all five platforms.
- Source configuration for six new employer instances.
- Normalized records with source/application URLs, HTML descriptions, locations, remote status, employment type, and original posting dates where available.
- SmartRecruiters offset/limit pagination with per-posting detail fetches.
- Partial-fetch handling for SmartRecruiters list and detail failures.
- Workable duplicate-shortcode merging for multi-location postings.
- Deterministic fixture tests and live tests.
- Live evidence under `artifacts/live_runs/`.
- Fixed the live-check raw artifact path so payloads are saved under `artifacts/raw/{source}/` rather than `artifacts/raw/raw/{source}/`.

## Connector Details

### Ashby

- Endpoint: `https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true`
- Pagination: none; all jobs are returned in one response.
- Required fields: `id`, `title`, `jobUrl`.
- Mapping:
  - `external_job_id` ← `id`
  - `title` ← `title`
  - `company` ← configured source company
  - `description` ← `descriptionHtml`, falling back to `descriptionPlain`
  - `location` ← `location`
  - `source_url` ← `jobUrl`
  - `application_url` ← `applyUrl`
  - `salary` ← `scrapeableCompensationSalarySummary`, falling back to `compensationTierSummary`
  - `employment_type` ← normalized `employmentType`
  - `remote_status` ← `workplaceType`, or `isRemote` when needed
  - `original_posted_at` ← `publishedAt`

### Workable

- Endpoint: `https://apply.workable.com/api/v1/widget/accounts/{subdomain}?details=true`
- Pagination: none; all jobs are returned in one response.
- Required fields: `shortcode`, `title`, `url` or `shortlink`.
- Mapping:
  - `external_job_id` ← `shortcode`
  - `title` ← `title`
  - `company` ← configured source company
  - `description` ← `description`
  - `location` ← formatted `locations`, falling back to `city`/`state`/`country`
  - `source_url` ← `url`, falling back to `shortlink`
  - `application_url` ← `application_url`
  - `employment_type` ← normalized `employment_type`
  - `remote_status` ← `telecommuting` plus location
  - `original_posted_at` ← `published_on`, falling back to `created_at`
- Duplicate `shortcode` entries are merged and their location lists are combined before normalization. This preserves multi-location postings without creating duplicate rows.

### SmartRecruiters

- List endpoint: `https://api.smartrecruiters.com/v1/companies/{company}/postings?limit={limit}&offset={offset}`
- Detail endpoint: `https://api.smartrecruiters.com/v1/companies/{company}/postings/{id}`
- Pagination: offset/limit, page size configurable from 1 to 100.
- Required fields: `id`, `name`.
- Mapping:
  - `external_job_id` ← `id`
  - `title` ← `name`
  - `company` ← `company.name`, falling back to configured source company
  - `description` ← combined `jobAd.sections.*.text` HTML
  - `location` ← `location.fullLocation`, falling back to city/region/country
  - `source_url` ← `postingUrl`, falling back to `https://jobs.smartrecruiters.com/{company}/{id}`
  - `application_url` ← `applyUrl`
  - `employment_type` ← normalized `typeOfEmployment.label`
  - `remote_status` ← `location.remote` / `location.hybrid`
  - `original_posted_at` ← `releasedDate`
- The connector fetches every posting detail after listing. This is an N+1 request pattern by design because the list response does not include full descriptions.
- If a detail request fails after listing succeeds, the fetch is recorded as `partial` and the already-listed jobs are preserved.
- If a list page fails after earlier pages succeed, the fetch is recorded as `partial` with the postings fetched so far.

## Live Verification

Latest live-check summary: `artifacts/live_runs/summary.json`.

| Source | Platform | Status | Discovered | Processed | Inserted | Updated |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `greenhouse-stripe` | Greenhouse | success | 775 | 775 | 0 | 775 |
| `greenhouse-airbnb` | Greenhouse | success | 203 | 203 | 0 | 203 |
| `lever-palantir` | Lever | success | 304 | 304 | 0 | 304 |
| `lever-spotify` | Lever | success | 86 | 86 | 0 | 86 |
| `ashby-ashby` | Ashby | success | 75 | 75 | 0 | 75 |
| `ashby-openai` | Ashby | success | 831 | 831 | 1 | 830 |
| `workable-huggingface` | Workable | success | 6 | 6 | 0 | 6 |
| `workable-runware` | Workable | success | 24 | 24 | 0 | 24 |
| `smartrecruiters-canva` | SmartRecruiters | success | 36 | 36 | 0 | 36 |
| `smartrecruiters-innergy` | SmartRecruiters | success | 7 | 7 | 0 | 7 |

`workable-runware` returned 55 raw postings but only 24 unique shortcodes. The connector merged the duplicate shortcodes and their locations, so 24 normalized jobs were processed.

Current database counts:

| Source | Rows |
| --- | ---: |
| `greenhouse-stripe` | 775 |
| `greenhouse-airbnb` | 204 |
| `lever-palantir` | 304 |
| `lever-spotify` | 86 |
| `ashby-ashby` | 75 |
| `ashby-openai` | 831 |
| `workable-huggingface` | 6 |
| `workable-runware` | 24 |
| `smartrecruiters-canva` | 36 |
| `smartrecruiters-innergy` | 7 |

`greenhouse-airbnb` has 204 rows while the latest live response returned 203 jobs. This remains expected because closure detection is not implemented.

Per-source Phase 3 evidence:

- `artifacts/live_runs/ashby-ashby.json`
- `artifacts/live_runs/ashby-openai.json`
- `artifacts/live_runs/workable-huggingface.json`
- `artifacts/live_runs/workable-runware.json`
- `artifacts/live_runs/smartrecruiters-canva.json`
- `artifacts/live_runs/smartrecruiters-innergy.json`

## Test Results

Deterministic tests:

```text
51 passed, 10 deselected
```

Command:

```bash
.venv/bin/python -m pytest -q
```

Live tests:

```text
10 passed, 51 deselected
```

Command:

```bash
.venv/bin/python -m pytest -q -m live -o addopts=""
```

Coverage added:

- Ashby fetch, normalization, missing optional fields, remote fallback, empty response, invalid top-level shape, and missing required fields.
- Workable fetch, normalization, missing optional fields, multi-location formatting, duplicate-shortcode merging, empty response, invalid top-level shape, and missing required fields.
- SmartRecruiters pagination, detail fetching, normalization, list-only URL fallback, missing optional fields, empty response, invalid top-level shape, missing posting ID, detail HTTP failure, detail invalid JSON, list failure after the first page, and invalid page size.
- Live fetch and normalization for all ten configured sources.

## Known Limitations

- Ashby has no documented pagination. Large boards can produce large responses; `ashby-openai` is roughly 14 MB per fetch.
- Workable may return duplicate `shortcode` entries for multi-location jobs. The connector merges them, but `pagination.total` can exceed `pagination.returned`.
- SmartRecruiters requires one detail request per posting. This is slower and more request-heavy than single-response connectors.
- SmartRecruiters list-only jobs fall back to `https://jobs.smartrecruiters.com/{company}/{id}` when no detail response is available.
- No closure detection. Jobs missing from a later successful fetch remain in the database.
- No cross-company or cross-platform deduplication.
- No scheduler, background worker, or retry queue.
- No frontend or dashboard.
- Descriptions are stored as source HTML where provided.
- Live tests depend on public API availability and can change in duration or result count.
- Recruitee was not selected because of its documented auth-token requirement starting 2027-02-10.

## Acceptance Criteria

- [x] Exactly three new connectors were implemented: Ashby, Workable, and SmartRecruiters.
- [x] Each selected platform has two real employer instances.
- [x] Each connector has a deterministic fixture test suite.
- [x] Each connector has a live smoke test.
- [x] Normalized records preserve required fields where the source provides them.
- [x] SmartRecruiters pagination is implemented and tested.
- [x] SmartRecruiters detail failures are recorded as partial, not failed zero-job successes.
- [x] Workable duplicate shortcodes are handled without losing locations.
- [x] Raw payloads are preserved under `artifacts/raw/`.
- [x] Live evidence is saved for all configured sources.
- [x] Matrix statuses were updated only for the implemented platforms and the Recruitee risk note.
- [x] No closure detection, cross-source deduplication, scheduler, worker, frontend, or AI extraction was added.

## Commands Used

```bash
.venv/bin/python -m compileall -q src tests
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q -m live -o addopts=""
.venv/bin/python scripts/live_check.py
```

## Remaining Work Before the Next Connector

- Review this batch and confirm the three-platform selection.
- Decide whether to add Recruitee before its 2027-02-10 auth deadline.
- Add more tenant coverage for Ashby, Workable, and SmartRecruiters if needed.
- Keep closure detection, cross-source deduplication, scheduling, and frontend in later phases unless scope changes.
