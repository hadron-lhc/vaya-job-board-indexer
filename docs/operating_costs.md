# Operating Costs

These are planning estimates, not vendor quotes. Actual costs depend on request volume, retention, hosting, and how many platforms are enabled.

## Current footprint

- 22 configured source instances across 11 platforms.
- One Python process for fetching, one for the API/UI.
- One SQLite database.
- Raw payload retention under `artifacts/raw/`.
- No managed queue, cache, or search cluster.

## Compute

A small VM or container is sufficient for the current 22 sources:

- 1 vCPU, 1-2 GB RAM
- 10-20 GB disk for database and artifacts
- Outbound HTTPS

Estimated hosting cost: USD 5-20 per month on a small VPS, or near zero on existing infrastructure.

Workday and Rippling are the main CPU/network consumers because they fetch one detail response per job. Workday is capped at 5 jobs per source in the current live configuration. A full Workday board can require hundreds to thousands of detail requests.

## Network and request volume

Assumptions:

- 4 full refreshes per day.
- 22 sources.
- 1-3 requests per source for simple feeds.
- N+1 detail requests for SmartRecruiters, Rippling, and Workday.

Current approximate daily request count:

- Simple sources: roughly 40-80 requests per refresh.
- SmartRecruiters: 2 sources, about 43 detail requests plus list requests.
- Rippling: 2 configured sources, about 22 detail requests plus list requests.
- Workday: 2 configured sources, 10 detail requests plus list requests.
- Total: roughly 100-200 requests per refresh, or 400-800 per day at four refreshes.

At 78 sources with detail-heavy connectors enabled broadly, expect tens of thousands of requests per day. Budget for rate limiting, retries, and concurrency controls before scaling.

## Storage

SQLite storage is small for normalized rows and moderate for raw payloads.

- Normalized jobs: kilobytes per job.
- Raw JSON: can be megabytes per fetch for large boards.
- FTS index: proportional to canonical job text.
- Change history: grows with field changes, not every scan.

Current disk estimate:

- Database: under 100 MB for tens of thousands of listings.
- Raw artifacts: hundreds of MB to several GB depending on retention.

Recommended retention:

- Keep the last 7-30 days of raw payloads.
- Keep fetch-run metadata and change history longer.
- Back up the database daily.

## Monitoring

Minimum:

- Fetch-run status counts by source.
- Error-class counts.
- Jobs discovered/processed/inserted/updated/changed/closed.
- Disk usage for `data/` and `artifacts/`.
- API health and latency.

No paid observability stack is required. A cron job can query `fetch_runs` and emit a summary.

## Cost drivers

1. Detail-heavy connectors: SmartRecruiters, Rippling, Workday.
2. Large boards: Ashby OpenAI, Greenhouse Stripe, Workday Salesforce.
3. Raw payload retention.
4. Number of refreshes per day.
5. Reverse proxy, TLS, and access control if the API is public.

## Cost controls

- Keep `max_jobs` caps for Workday until rate limits and concurrency are in place.
- Add per-source request budgets.
- Use conditional requests or caching only where the source supports it.
- Prune raw payloads on a schedule.
- Run full refreshes less often than incremental or high-value sources.
- Do not enable every tenant for every platform; prioritize employers and job boards that matter.
