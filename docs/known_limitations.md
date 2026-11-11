# Known Limitations

## Coverage

- 11 of 78 platforms are implemented and live-tested with two tenants each.
- 60 platforms remain `RESEARCHED`.
- 6 platforms are `ACCESS_BLOCKED`.
- 1 platform remains `NOT_RESEARCHED`.
- The matrix is the source of truth: `docs/platform_matrix.csv`.

## Connector limitations

- Greenhouse does not expose a separate application URL in its jobs response; `application_url` is `null`.
- Lever EU host was not verified for real employers; configured sources use `api.lever.co`.
- Ashby responses can be large; `ashby-openai` is roughly 14 MB per fetch.
- Workable can return duplicate `shortcode` values for multi-location postings. The connector merges them, so `pagination.total` can exceed `pagination.returned`.
- SmartRecruiters requires one detail request per posting after list pagination.
- Recruitee documents an auth-token requirement starting 2027-02-10. The connector will need review before that date.
- Pinpoint does not expose posting dates in the list response.
- Personio XML may omit direct apply URLs and descriptions for some positions.
- Teamtailor RSS may cap around 100 items and feed truncation is not detected.
- Rippling requires one detail request per posting. The `rippling` tenant has 410 jobs and is not configured to avoid an unbounded live fetch.
- Workday uses an undocumented CXS API. The live configuration caps each board at 5 jobs, so fetches are `PARTIAL_SUCCESS` and do not drive closure.

## Lifecycle and deduplication

- Closure requires two complete successful scans with the job missing. A single missing scan only marks the job `missing`.
- Failed, blocked, partial, rate-limited, timed-out, or schema-changed scans never close jobs.
- Deduplication is conservative. It prefers false negatives over merging distinct roles.
- Deduplication uses exact URL matches and normalized company + title + location with description similarity threshold `0.55`.
- Ambiguous matches remain separate and can appear as duplicate canonical jobs.
- Canonical job status is derived from source listings but is not a substitute for human review.

## API and UI

- The API uses Python's standard library HTTP server, not a production ASGI server.
- There is no authentication, authorization, or rate limiting in the application.
- There is no TLS termination in the application.
- The HTML UI is intentionally minimal.
- Pagination is capped at 100 items per request.
- The API is read-only.

## Operations

- There is no built-in scheduler. Use cron or systemd timers.
- There is no distributed lock. Do not run overlapping full refreshes against one SQLite database.
- SQLite is suitable for the current scale but not for high write concurrency across many workers.
- Raw payload retention is manual.
- There is no alerting integration.
- There is no retry queue beyond in-process HTTP retries.

## Data quality

- Job counts change between live runs.
- Descriptions are stored as source HTML where provided.
- Some sources provide salary, employment type, or posting date inconsistently.
- Remote status is inferred from explicit fields where available, otherwise from location text.
- Original posting timestamps are normalized to UTC when parseable; otherwise the source string is preserved or left `null`.

## Security and compliance

- No authentication bypass, CAPTCHA solving, or hidden credential use is implemented.
- No private tokens or customer data are stored in fixtures.
- Public endpoints may change without notice.
- Review each platform's terms before production use.
