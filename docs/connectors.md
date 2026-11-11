# Connector Reference

Implemented platforms: 11. Each platform has two live-verified source instances unless noted.

## Shared behavior

- All connectors implement `fetch(source) -> FetchBatch` and `normalize(raw_job, source, checked_at) -> JobListing`.
- `fetch` records request URLs, raw payloads, pagination metadata, and a `complete` flag.
- `normalize` never invents missing values. Optional fields are `None` when absent.
- Partial fetches preserve already-fetched jobs and are recorded as `PARTIAL_SUCCESS`.
- Failed or partial fetches never mark jobs missing or closed.
- Raw payloads are saved under `artifacts/raw/{source_instance}/{run_id}.json`.

## Greenhouse

- Endpoint: `https://boards-api.greenhouse.io/v1/boards/{tenant}/jobs?content=true`
- Pagination: none.
- Required fields: `id`, `title`, `absolute_url`.
- Company: `company_name`, falling back to configured company.
- Application URL: not separately exposed; `application_url` is `null`.
- Description: `content` HTML.
- Remote status: derived from location text.
- Tenants: `stripe`, `airbnb`.

## Lever

- Endpoint: `https://api.lever.co/v0/postings/{tenant}?mode=json`
- Pagination: none; `page_size` option is accepted by the connector configuration.
- Required fields: `id`, `text`, `hostedUrl`.
- Application URL: `applyUrl`.
- Description: `description` HTML.
- Remote status: `workplaceType`, falling back to location.
- Tenants: `palantir`, `spotify`.

## Ashby

- Endpoint: `https://api.ashbyhq.com/posting-api/job-board/{tenant}?includeCompensation=true`
- Pagination: none.
- Required fields: `id`, `title`, `jobUrl`.
- Application URL: `applyUrl`.
- Description: `descriptionHtml`, falling back to `descriptionPlain`.
- Compensation: `scrapeableCompensationSalarySummary`, falling back to `compensationTierSummary`.
- Tenants: `ashby`, `openai`.
- Limitation: large boards produce large responses; `ashby-openai` is roughly 14 MB.

## Workable

- Endpoint: `https://apply.workable.com/api/v1/widget/accounts/{tenant}?details=true`
- Pagination: none.
- Required fields: `shortcode`, `title`, `url` or `shortlink`.
- Application URL: `application_url`.
- Description: `description` HTML.
- Duplicate `shortcode` entries for multi-location postings are merged and their locations combined.
- Tenants: `huggingface`, `runware`.

## SmartRecruiters

- List endpoint: `https://api.smartrecruiters.com/v1/companies/{tenant}/postings?limit={limit}&offset={offset}`
- Detail endpoint: `https://api.smartrecruiters.com/v1/companies/{tenant}/postings/{id}`
- Pagination: offset/limit, configurable `page_size` from 1 to 100.
- Required fields: `id`, `name`.
- Application URL: `applyUrl`.
- Description: combined `jobAd.sections.*.text` HTML from the detail response.
- Behavior: N+1 detail requests. Detail failure after listing returns a partial batch with list-only jobs.
- Tenants: `Canva`, `innergy1`.

## Recruitee

- Endpoint: `https://{tenant}.recruitee.com/api/offers/`
- Pagination: none.
- Required fields: `id`, `title`.
- Application URL: `careers_apply_url`.
- Description: `description` plus `requirements`.
- Location: formatted `locations`, falling back to `location`.
- Remote status: explicit `remote`, `hybrid`, or `on_site` booleans.
- Salary: formatted from `salary.min`, `salary.max`, `salary.currency`, `salary.period`.
- Tenants: `bunq`, `jobs` (Tellent).
- Limitation: Recruitee documents an auth-token requirement starting 2027-02-10.

## Pinpoint

- Endpoint: `https://{tenant}.pinpointhq.com/postings.json`
- Pagination: none.
- Required fields: `title`, `url`.
- External ID: UUID extracted from `url`.
- Application URL: `url`.
- Description: combined `description`, `key_responsibilities`, `skills_knowledge_expertise`, and `benefits` sections.
- Salary: `compensation` when `compensation_visible` is true.
- Tenants: `avaaz`, `workwithus`.
- Limitation: posting dates are not exposed in the list response.

## Personio

- Endpoint: `https://{tenant}.jobs.personio.de/xml?language=en`
- Format: XML rooted at `workzag-jobs`.
- Pagination: none.
- Required fields: `id`, `name`.
- Application URL: not reliably exposed; `application_url` is `null`.
- Description: combined `jobDescriptions/jobDescription` entries.
- Employment type: `schedule`, falling back to `employmentType`.
- Tenants: `lanch`, `deskbird`.
- Limitation: some positions have no description blocks; the feed may omit direct apply URLs.

## Teamtailor

- Endpoint: `https://{tenant}.teamtailor.com/jobs.rss`
- Format: RSS.
- Pagination: none; RSS may cap around 100 items.
- Required fields: `title`, `link`.
- External ID: `guid`, falling back to `link`.
- Application URL: `link`.
- Location: nested `tt:locations/tt:location/tt:name`, falling back to city/country.
- Remote status: `remoteStatus` (`fully`, `temporary`, `hybrid`, `none`).
- Tenants: `bankgirotab`, `doconomy`.
- Limitation: feed truncation is not detected; large boards may be incomplete.

## Rippling

- List endpoint: `https://ats.rippling.com/api/v2/board/{tenant}/jobs?page={page}&pageSize={pageSize}&groupJobsByLocation=true`
- Detail endpoint: `https://ats.rippling.com/api/v2/board/{tenant}/jobs/{id}`
- Pagination: page/pageSize, configurable `page_size` from 1 to 1000, `max_pages` guard.
- Required fields: `id`, `name`, `url`.
- Application URL: `url`.
- Description: `detail.description.company` plus `detail.description.role`.
- Salary: first `detail.payRangeDetails` entry.
- Employment type: `detail.employmentType.id`.
- Tenants: `netatwork`, `realwork`.
- Limitation: N+1 detail requests. The `rippling` tenant has 410 jobs, so it is not configured to avoid an unbounded live fetch.

## Workday

- List endpoint: `POST https://{host}/wday/cxs/{tenant}/{site}/jobs`
- Detail endpoint: `GET https://{host}/wday/cxs/{tenant}/{site}{externalPath}`
- Request body: `{"appliedFacets":{},"limit":20,"offset":0,"searchText":""}`
- Pagination: offset/limit; `max_jobs` caps the fetch.
- Required fields: `externalPath`, plus `title` from the list or detail.
- External ID: `jobReqId`, falling back to `jobPostingId` or `externalPath`.
- Application URL: `jobPostingInfo.externalUrl`.
- Description: `jobPostingInfo.jobDescription`.
- Employment type: `jobPostingInfo.timeType`.
- Remote status: `jobPostingInfo.remoteType`, falling back to location.
- Tenants: `salesforce.wd12/External_Career_Site`, `adobe.wd5/external_experienced`.
- Limitation: undocumented CXS API; N+1 detail requests; live configuration caps each board at 5 jobs, producing `PARTIAL_SUCCESS`.

## Registry

`src/job_indexer/connectors/registry.py` maps platform names to connector classes and defines `SUPPORTED_PLATFORMS`. Adding a connector requires:

1. A connector module with `fetch` and `normalize`.
2. Registration in `SUPPORTED_PLATFORMS` and `build_connector`.
3. At least one sanitized fixture.
4. Deterministic tests.
5. Live test and config entries for two real tenants.
6. Matrix and documentation updates.
