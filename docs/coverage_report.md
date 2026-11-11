# Coverage Report

Date: 2026-11-11

Source of truth: `docs/platform_matrix.csv`

## Summary

| Metric | Value |
| --- | ---: |
| Total platforms | 78 |
| ATS platforms | 58 |
| Job-board platforms | 20 |
| Implemented and live-tested platforms | 15 |
| Implemented ATS platforms | 14 |
| Implemented job-board platforms | 1 |
| Platform coverage | 19.2% |
| ATS coverage | 24.1% |
| Job-board coverage | 5.0% |

Platform coverage is calculated as `15 / 78`. It is not weighted by employer count or job volume.

## Matrix status counts

| Status | Count |
| --- | ---: |
| `LIVE_TESTED_MULTI_TENANT` | 15 |
| `RESEARCHED` | 56 |
| `ACCESS_BLOCKED` | 6 |
| `NOT_RESEARCHED` | 1 |
| Total | 78 |

## Implemented platforms

| Platform | Category | Tenants | Live status | Notes |
| --- | --- | --- | --- | --- |
| Greenhouse | ATS | `stripe`, `airbnb` | SUCCESS | No separate application URL. |
| Lever | ATS | `palantir`, `spotify` | SUCCESS | Global API host. |
| Ashby | ATS | `ashby`, `openai` | SUCCESS | Large responses. |
| Workable | ATS | `huggingface`, `runware` | SUCCESS | Merges duplicate shortcodes. |
| SmartRecruiters | ATS | `Canva`, `innergy1` | SUCCESS | N+1 detail requests. |
| Recruitee | ATS | `bunq`, `jobs` | SUCCESS | Auth deadline 2027-02-10. |
| Pinpoint | ATS | `avaaz`, `workwithus` | SUCCESS | No posting dates in list. |
| Personio | ATS | `lanch`, `deskbird` | SUCCESS | XML feed; apply URL may be null. |
| Teamtailor | ATS | `bankgirotab`, `doconomy` | SUCCESS | RSS may cap around 100 items. |
| Rippling | ATS | `netatwork`, `realwork` | SUCCESS | N+1 detail requests. |
| Workday | ATS | `salesforce`, `adobe` | PARTIAL_SUCCESS | Live cap of 5 jobs per board. |
| Breezy HR | ATS | `breezy-hr`, `prep-academy-tutors` | SUCCESS / PARTIAL_SUCCESS | JSON list plus JSON-LD detail; large board capped at 20 jobs. |
| BambooHR | ATS | `flyio`, `acme` | SUCCESS | List plus per-job detail endpoint. |
| JazzHR | ATS | `snapsheet`, `loccitaneenprovence` | SUCCESS / PARTIAL_SUCCESS | HTML list plus JSON-LD detail; large board capped at 20 jobs. |
| Niceboard | Job Board | `afa`, `linkinbio` | SUCCESS | JSON API; requires full filter query parameters. |

## Live evidence

Evidence is stored under `artifacts/live_runs/`.

- Per-source evidence: `artifacts/live_runs/{source_instance}.json`
- Summary: `artifacts/live_runs/summary.json`
- Raw payloads: `artifacts/raw/{source_instance}/{run_id}.json`

Latest configured sources: 30. 26 sources returned `SUCCESS`. Four returned `PARTIAL_SUCCESS` because of intentional live-test caps:

- Both Workday sources (`max_jobs=5`).
- `breezy-prep-academy` (`max_jobs=20` of 323).
- `jazzhr-loccitane` (`max_jobs=20` of 181).

Partial fetches never drive lifecycle closure.

## Test coverage

Deterministic suite:

```text
141 passed, 30 deselected
```

The deterministic suite covers:

- Connector fetch and normalization.
- Missing optional fields.
- Invalid top-level shapes and required fields.
- Pagination and partial-fetch behavior.
- Empty responses.
- Lifecycle transitions and closure policy.
- Canonical deduplication.
- API routes and UI.
- Legacy database migration.
- Scheduler cycles and stop behavior.
- 78-platform coverage checklist generation.

Live suite:

```text
30 passed, 141 deselected
```

Command:

```bash
.venv/bin/python -m pytest -q -m live -o addopts=""
```

The live suite asserts the documented partial behavior for capped sources.

## Not implemented

The remaining 63 platforms are not implemented:

- 56 `RESEARCHED` platforms have a proposed extraction path but no connector.
- 6 `ACCESS_BLOCKED` platforms have no verified workaround.
- 1 `NOT_RESEARCHED` platform remains unidentified or unverified.

Job-board coverage is 1 of 20. Niceboard is live-tested; the other 19 job-board rows remain research candidates.

## Interpretation

The project does not claim broad coverage. It claims a tested, documented vertical slice for 15 platforms, with conservative lifecycle and deduplication behavior, a search API/UI, a built-in scheduler, and evidence for every configured source.

The generated checklist in `docs/coverage_checklist.md` lists all 78 platforms with status, configured sources, evidence paths, and missing requirements.

The next coverage step is to implement additional public structured feeds from the 56 `RESEARCHED` rows, starting with platforms that have verified tenants and simple schemas.
