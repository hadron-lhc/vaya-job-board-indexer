# Coverage Report

Date: 2026-11-10

Source of truth: `docs/platform_matrix.csv`

## Summary

| Metric | Value |
| --- | ---: |
| Total platforms | 78 |
| ATS platforms | 58 |
| Job-board platforms | 20 |
| Implemented and live-tested platforms | 11 |
| Implemented ATS platforms | 11 |
| Implemented job-board platforms | 0 |
| Platform coverage | 14.1% |
| ATS coverage | 19.0% |
| Job-board coverage | 0.0% |

Platform coverage is calculated as `11 / 78`. It is not weighted by employer count or job volume.

## Matrix status counts

| Status | Count |
| --- | ---: |
| `LIVE_TESTED_MULTI_TENANT` | 11 |
| `RESEARCHED` | 60 |
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

## Live evidence

Evidence is stored under `artifacts/live_runs/`.

- Per-source evidence: `artifacts/live_runs/{source_instance}.json`
- Summary: `artifacts/live_runs/summary.json`
- Raw payloads: `artifacts/raw/{source_instance}/{run_id}.json`

Latest configured sources: 22. All 20 non-Workday sources returned `SUCCESS`. Both Workday sources returned `PARTIAL_SUCCESS` because of the intentional `max_jobs=5` live-test cap.

## Test coverage

Deterministic suite:

```text
110 passed, 22 deselected
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

Live suite:

```text
22 passed, 110 deselected
```

Command:

```bash
.venv/bin/python -m pytest -q -m live -o addopts=""
```

Workday checks assert the documented partial behavior.

## Not implemented

The remaining 67 platforms are not implemented:

- 60 `RESEARCHED` platforms have a proposed extraction path but no connector.
- 6 `ACCESS_BLOCKED` platforms have no verified workaround.
- 1 `NOT_RESEARCHED` platform remains unidentified or unverified.

No job-board platform is implemented. The 20 job-board rows remain research candidates.

## Interpretation

The project does not claim broad coverage. It claims a tested, documented vertical slice for 11 ATS platforms, with conservative lifecycle and deduplication behavior, a search API/UI, and evidence for every configured source.

The next coverage step is to implement additional public structured feeds from the 60 `RESEARCHED` rows, starting with platforms that have verified tenants and simple schemas.
