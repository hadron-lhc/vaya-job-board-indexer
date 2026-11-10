# vaya-job-board-indexer

Minimal multi-tenant job board indexer. Phase 3 currently supports **Greenhouse**, **Lever**, **Ashby**, **Workable**, and **SmartRecruiters**.

## Requirements

- Python 3.12+
- Public network access to the configured job board APIs

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
```

## Commands

List configured employer sources:

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

Exit codes: `0` success, `2` partial fetch, `1` failed fetch or configuration error.

Run deterministic tests:

```bash
.venv/bin/python -m pytest -q
```

Run live tests explicitly:

```bash
.venv/bin/python -m pytest -q -m live -o addopts=""
```

Run all configured live checks and write evidence:

```bash
.venv/bin/python scripts/live_check.py
```

## Outputs

- `data/jobs.db`: SQLite database with `source_instances`, `job_listings`, and `fetch_runs`.
- `artifacts/raw/{source_instance}/{run_id}.json`: raw API payloads for each fetch.
- `artifacts/live_runs/{source_instance}.json`: per-source live evidence.
- `artifacts/live_runs/summary.json`: latest live-check summary.

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

For Lever, set `options.api_host` to `api.lever.co` and optionally set `options.page_size` between `1` and `100`.

For SmartRecruiters, optionally set `options.page_size` between `1` and `100`. The connector paginates the postings list and then fetches each posting detail to obtain the full description and apply URL.

## Current scope

- Greenhouse, Lever, Ashby, Workable, and SmartRecruiters connectors.
- Two verified real employer instances per platform.
- Normalized source-level listings.
- SQLite persistence with idempotent upserts.
- Fetch-run tracking with `success`, `partial`, and `failed` statuses.
- Raw payload preservation.
- Deterministic fixture tests and separate live tests.
- CLI for one source at a time.

Not implemented yet: cross-company deduplication, closure detection, scheduling, workers, frontend, and additional platforms.

## Known limitations

- Greenhouse does not expose a separate application URL in its jobs response; `application_url` is `null`.
- Lever EU host was not verified for real employers; configured sources use the global `api.lever.co` host.
- Ashby responses can be large because full descriptions and compensation data are included; `ashby-openai` is roughly 14 MB per fetch.
- Workable can return the same `shortcode` multiple times for multi-location postings. The connector merges those duplicate entries and their location lists before normalization, so `pagination.total` can exceed `pagination.returned`.
- SmartRecruiters requires one detail request per posting after list pagination. This is an N+1 request pattern and is documented rather than hidden.
- SmartRecruiters list-only postings fall back to `https://jobs.smartrecruiters.com/{company}/{id}` when the detail response is unavailable.
- Failed or partial fetches never mark jobs as closed. A later successful fetch does not remove jobs that disappeared from the source.
- Job counts change between live runs, so the database can contain rows that are no longer returned by the source.
- Descriptions are stored as source HTML where provided.

See `docs/phase3_report.md` for Phase 3 implementation details, evidence, and test results. See `docs/phase2_report.md` for the earlier Greenhouse/Lever slice.
