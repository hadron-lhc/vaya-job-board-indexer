# Research Notes

Research date: 2026-11-10

Scope: Phase 1 platform research for the Vaya Job Board Indexer challenge. This document records what was verified, how it was verified, and what remains unknown. It does not claim that any connector has been implemented.

## 1. Scope and sources

- Authoritative platform list: <https://vayahq.com/challenge/build-a-job-board-indexer-for-10000>
- Required coverage: 58 ATS platforms and 20 job-board platforms.
- Matrix: `docs/platform_matrix.csv` has exactly 78 rows and 16 columns.
- No credentials, API keys, private tokens, or customer data were used.
- No authentication, CAPTCHA, or access control was bypassed.
- No runtime LLM parsing is assumed.

Primary research inputs:

- Official platform documentation and homepages.
- Live HTTP requests to public endpoints and public career pages.
- Public open-source references:
  - <https://github.com/devilscrapes/ats-jobs-api>
  - <https://github.com/ctriolab/ats-jobs>
  - <https://github.com/ever-jobs/ever-jobs>
  - <https://github.com/strelov1/freehire>
  - <https://github.com/kalil0321/ats-scrapers>
  - <https://github.com/datascry/openroles>

## 2. Status definitions used in the matrix

- `RESEARCHED`: enough desk research and/or live evidence to propose an extraction path. This does not mean the endpoint, tenant, or schema is fully verified.
- `ACCESS_BLOCKED`: live access failed with 403, DNS failure, or another blocking condition, and no verified workaround exists.
- `NOT_RESEARCHED`: product identity or public job surface is still unverified.
- `IMPLEMENTED`, `FIXTURE_TESTED`, `LIVE_TESTED_ONE_TENANT`, `LIVE_TESTED_MULTI_TENANT`, `VERIFIED`: not used in Phase 1 because no connectors existed yet. The implemented batch uses `LIVE_TESTED_MULTI_TENANT` for Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, Pinpoint, Personio, Teamtailor, Rippling, and Workday.

Current matrix status counts:

| Status | Count |
| --- | ---: |
| `RESEARCHED` | 60 |
| `LIVE_TESTED_MULTI_TENANT` | 11 |
| `ACCESS_BLOCKED` | 6 |
| `NOT_RESEARCHED` | 1 |
| Total | 78 |

Confidence counts:

| Confidence | Count |
| --- | ---: |
| high | 11 |
| medium | 19 |
| low | 48 |
| Total | 78 |

The 11 high-confidence entries are public endpoint patterns that returned live data during this research: Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, Personio, Teamtailor, Pinpoint, Rippling, and Workday.

## 3. Extraction-method summary

| Extraction method | Count |
| --- | ---: |
| HTML | 43 |
| Public JSON API | 9 |
| Authenticated API / HTML fallback | 6 |
| Public JSON/XML/RSS variants | 4 |
| HTML/UNKNOWN | 3 |
| HTML + JSON-LD | 2 |
| HTML + JSON-LD / optional WP REST | 1 |
| HTML / OData API | 1 |
| HTML / API | 1 |
| Custom XML/API or posting-only | 4 |
| UNKNOWN | 4 |
| Total | 78 |

Interpretation:

- 13 platforms have a plausible public structured feed: 9 public JSON APIs, 1 unverified public JSON API, 1 undocumented public JSON API, 1 public XML feed, and 1 public RSS feed.
- 6 job-board platforms have authenticated APIs and may also expose public HTML.
- 3 platforms have HTML plus JSON-LD as the best initial path.
- 43 platforms are HTML-first in the current research. Many may expose hidden JSON, but that is not verified.
- 4 platforms remain completely unknown at the endpoint level.
- 6 platforms are currently access-blocked.

Authentication summary from the matrix:

| Authentication | Count |
| --- | ---: |
| None | 45 |
| UNKNOWN | 23 |
| API key / `X-Api-Key` | 4 |
| OAuth/API key or OAuth for API | 3 |
| Basic | 1 |
| Bearer token | 1 |
| Account-managed | 1 |
| Total | 78 |

## 4. Live-verified public endpoints

The following requests returned HTTP 200 during this research. Sizes are response bytes and are included only as evidence, not as stable expectations.

| Platform | Request | Status | Bytes | Evidence notes |
| --- | --- | ---: | ---: | --- |
| Greenhouse | `GET https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true` | 200 | 6,050,780 | Public board API; full descriptions included. |
| Lever | `GET https://api.lever.co/v0/postings/leverdemo?mode=json` | 200 | 83,523 | Public postings API. |
| Ashby | `GET https://api.ashbyhq.com/posting-api/job-board/ashby?includeCompensation=true` | 200 | 4,530,204 | Public posting API. |
| Workable | `GET https://apply.workable.com/api/v1/widget/accounts/huggingface?details=true` | 200 | 37,522 | Public widget API. |
| SmartRecruiters | `GET https://api.smartrecruiters.com/v1/companies/linkedin3/postings?limit=1` | 200 | 3,141 | Public postings API; offset/limit pagination. |
| Recruitee | `GET https://bunq.recruitee.com/api/offers/` | 200 | 742,123 | Public offers API. |
| Personio | `GET https://lanch.jobs.personio.de/xml?language=en` | 200 | 22,783 | Public XML feed. |
| Teamtailor | `GET https://bankgirotab.teamtailor.com/jobs.rss` | 200 | 15,845 | Public RSS feed. |
| Pinpoint | `GET https://avaaz.pinpointhq.com/postings.json` | 200 | 17,821 | Public postings JSON. |
| Rippling | `GET https://ats.rippling.com/api/v2/board/rippling/jobs?page=1` | 200 | 8,103 | Public board API with page/pageSize. |
| Workday | `POST https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs` | 200 | 16,049 | Undocumented CXS API; JSON body required. |

Workday request body:

```json
{"appliedFacets":{},"limit":2,"offset":0,"searchText":""}
```

Workday notes:

- The same URL with `GET` returned HTTP 400.
- The list response contains `total`, `jobPostings`, `facets`, and `userAuthenticated`.
- Each item contains `title`, `externalPath`, `locationsText`, `postedOn`, and `bulletFields`.
- A detail request is required to obtain full descriptions.

## 5. Field mappings observed

These are observed field names, not a final normalization contract.

### Greenhouse

- Top level: `jobs`, `meta`.
- Job fields include: `id`, `title`, `company_name`, `content`, `absolute_url`, `location.name`, `updated_at`, `first_published`, `departments`, `offices`.
- Company name is available directly.
- Application URL is available through `absolute_url`.

### Lever

- Response is a JSON array.
- Fields include: `id`, `text`, `description`, `descriptionPlain`, `hostedUrl`, `applyUrl`, `categories.location`, `categories.team`, `createdAt`, `salaryRange`, `country`, `workplaceType`.
- Company name is not a reliable posting field; use the configured company slug.

### Ashby

- Top level: `jobs`, `apiVersion`.
- Job fields include: `id`, `title`, `department`, `team`, `employmentType`, `location`, `publishedAt`, `isListed`, `isRemote`, `workplaceType`, `jobUrl`, `applyUrl`, `descriptionHtml`, `descriptionPlain`, `compensation`.
- Company name is not present in the job item; use the configured org slug.

### Workable

- Top level: `name` (company name), `description`, `jobs`.
- Job fields include: `title`, `shortcode`, `code`, `employment_type`, `telecommuting`, `department`, `url`, `shortlink`, `application_url`, `published_on`, `created_at`, `country`, `city`, `state`, `locations`, `description`.

### SmartRecruiters

- Top level: `offset`, `limit`, `totalFound`, `content`.
- Job fields include: `id`, `name`, `uuid`, `company.name`, `releasedDate`, `location`, `department`, `typeOfEmployment`, `ref`, `language`.
- Pagination uses `offset` and `limit`.
- The list may not include the full job description; a detail request may be required.

### Recruitee

- Top level: `offers`.
- Offer fields include: `id`, `title`, `company_name`, `description`, `careers_url`, `careers_apply_url`, `published_at`, `created_at`, `updated_at`, `location`, `remote`, `salary`, `employment_type_code`, `department`.
- Company name is available directly.
- Application URL is available through `careers_apply_url`.

### Personio

- XML root: `workzag-jobs`.
- Position fields include: `id`, `office`, `department`, `recruitingCategory`, `name`, `jobDescriptions`, `employmentType`, `seniority`, `schedule`, `keywords`, `occupation`, `createdAt`.
- The XML feed may not contain a direct application URL; the careers page may need to be used.

### Teamtailor

- RSS root: `rss`, then `channel`.
- Channel contains `title`, `description`, `link`, and `item` entries.
- Item fields include title, link, and description.
- `jobs.json` returned 404 for the tested tenant; RSS is the verified path.

### Pinpoint

- Top level: `data`.
- Job fields include: `id`, `title`, `description`, `url`, `location`, `employment_type`, `compensation`, `workplace_type`, `published_at`/deadline-related fields.
- Company name is not in the item; use the configured company slug.

### Rippling

- Top level: `items`, `page`, `pageSize`, `totalItems`, `totalPages`.
- Job fields include: `id`, `name`, `url`, `department`, `locations`, `language`.
- The list may omit full descriptions.

## 6. HTML, JSON-LD, and feed findings

- JazzHR: `https://jazzhr.applytojob.com/apply` returned HTTP 200 with 84,364 bytes of HTML. No documented unauthenticated JSON API was verified.
- Eightfold AI: `https://nvidia.eightfold.ai/careers` returned HTTP 200 with 191,631 bytes of HTML. The API endpoint `https://nvidia.eightfold.ai/api/apply/v2/jobs?...` returned HTTP 403 with a 39-byte response.
- WP Job Manager: `https://wpjobmanager.com/wp-json/wp/v2/job_listing?per_page=1` returned HTTP 404. The tested `/jobs/` URL redirected to documentation. A live WPJM board is still needed.
- Jobvite: tested `https://jobs.jobvite.com/logitech/search` redirected to a generic Jobvite support page, not a tenant job list.
- BambooHR: `https://bamboohr.bamboohr.com/careers/list` redirected to the BambooHR marketing site. The public JSON endpoint remains unverified.
- JobBoardHQ: sample boards returned HTTP 200:
  - `https://www.estatejobs.com/`
  - `https://www.greaterroccareers.com/`
  - `https://www.roaddogjobs.com/`
  - `https://jobs.macslist.org/`
  - `https://www.jobsindoorcounty.com/`
  - `https://www.njschooljobs.com/`
  - The pages advertise an Atom feed at `/atom.xml`, but the tested feed URL returned HTML, not valid Atom XML. Treat these as HTML/JSON-LD candidates, not feed sources.
- JobBoard.com: `https://www.jobboard.com/` returned HTTP 200 with 52,652 bytes. No public API was verified.
- Artha: `https://arthajobboard.com/` returned HTTP 200 with 229,252 bytes. No public API was verified.
- eJobSiteSoftware: `https://ejobsitesoftware.com/demo/` returned HTTP 200 with 206,353 bytes. No public API was verified.
- SmartJobBoard sample: `https://jobs.alanet.org/browse-jobs/` returned HTTP 200 in one check and HTTP 403 in another. Access is intermittent.
- JobBoard.io sample: `https://www.hireheroesusa.org/` returned HTTP 200 in one check. The official JobBoard.io site returned HTTP 403 in another check.
- JobBoardFire, CareerSiteCloud, JobMount, and Nodex returned HTTP 403 during checks.
- eJobBoard and Rival domains did not resolve.

## 7. Authenticated or contract-managed platforms

These platforms are not safe to treat as public-feed connectors without confirming account access and terms.

- JobKit: REST API with Basic auth. Public `jobs.json` was not verified.
- Jobboardly: API with bearer token, described as available on Pro/Ultra plans. Exact base path unverified.
- Jobiqo: Job Posting API, API key required. Reported paths include `/api/v1/job-list` and `/api/v1/job/{job_id}`.
- JBoard.io: API uses `X-Api-Key`; Enterprise plan. Showcase boards exist but were not verified.
- SmartJobBoard: API requires an Enterprise key. XML/JSON import exists. A public sample board is available, but the read API is not verified.
- JobBoard.io: API uses `X-Api-Key`; Enterprise plan. Case-study boards exist, but the API is not verified.
- Wiley Madgex: integration is account-managed; XML/API contract is per board.
- Talenetic: custom XML feed feature exists; schema and plan are unverified.
- JobMount: only a posting/import API was found; no public read API was verified.
- SAP SuccessFactors: OData APIs require enterprise credentials; public career sites vary.
- Oracle Recruiting: public HTML pages exist; Oracle HCM APIs require enterprise auth.
- Zoho Recruit: public career pages exist; API access requires OAuth setup.

## 8. Important caveats

- A `200` response does not guarantee the endpoint is supported, stable, or permitted for this use. Public visibility still needs terms review.
- Several platforms returned different results depending on request headers. For example, Ashby and Workable returned 403 to a default Python `urllib` user agent but 200 to `curl` or a browser-like user agent. Use a clear, honest user agent and retest; do not use header tricks to bypass access controls.
- Several guessed company slugs returned empty payloads. A valid tenant must be verified before a connector is considered working.
- The matrix uses `UNKNOWN` rather than invented endpoints, tenants, or field names.
- Some job-board products have ambiguous identities:
  - Artha is `arthajobboard.com`, not `artha.io`.
  - `jobboardsoftware.com` redirects to Exenzo.
  - eJobBoard appears unavailable.
  - Nodex is a custom job-board software provider, not a public job feed.
- No closure logic can be validated from a failed fetch. A failed fetch must be recorded as a fetch failure, never as proof that all jobs closed.

## 9. Recommended verification queue

Priority 1: implementable public connectors

1. Greenhouse
2. Lever
3. Ashby
4. Workable
5. SmartRecruiters
6. Recruitee
7. Personio
8. Teamtailor
9. Pinpoint
10. Rippling
11. Workday

Priority 2: high-value HTML/JSON-LD connectors

1. JazzHR
2. Eightfold AI
3. JobBoardHQ sample boards
4. JobBoard.com
5. eJobSiteSoftware demo
6. Artha

Priority 3: verify auth or contract before committing

1. JobKit
2. Jobboardly
3. Jobiqo
4. JBoard.io
5. SmartJobBoard
6. JobBoard.io
7. Wiley Madgex
8. Talenetic
9. JobMount

Priority 4: resolve identity or access

1. FirstStage
2. Rival
3. eJobBoard
4. Nodex
5. JobBoardFire
6. CareerSiteCloud
7. BambooHR public JSON
8. WP Job Manager live board
9. Niceboard live tenant
10. Jobvite live tenant

## 10. Implementation outcome

The implemented batch covers eleven platforms with two live-verified employer instances per platform:

- Greenhouse: `stripe`, `airbnb`
- Lever: `palantir`, `spotify`
- Ashby: `ashby`, `openai`
- Workable: `huggingface`, `runware`
- SmartRecruiters: `Canva`, `innergy1`
- Recruitee: `bunq`, `jobs` (Tellent)
- Pinpoint: `avaaz`, `workwithus`
- Personio: `lanch`, `deskbird`
- Teamtailor: `bankgirotab`, `doconomy`
- Rippling: `netatwork`, `realwork`
- Workday: `salesforce.wd12/External_Career_Site`, `adobe.wd5/external_experienced`

Recruitee is implemented despite its documented auth-token requirement starting 2027-02-10; the deadline is recorded in the matrix. Workday and Rippling require per-posting detail requests for descriptions. Workday live configuration intentionally caps each board at five jobs, so those fetches are `PARTIAL_SUCCESS` and never drive closure.

See `docs/phase3_report.md` for the first connector batch and `docs/EXECUTION_LOG.md` for the full execution history.

## 11. Source links

Official documentation and platform pages:

- <https://developers.greenhouse.io/job-board.html>
- <https://github.com/lever/postings-api>
- <https://developers.ashbyhq.com/>
- <https://workable.readme.io/>
- <https://developers.smartrecruiters.com/>
- <https://docs.recruitee.com/>
- <https://developer.personio.de/>
- <https://docs.teamtailor.com/>
- <https://developers.pinpointhq.com/docs/introduction>
- <https://developer.rippling.com/>
- <https://community.workday.com/>
- <https://developer.breezy.hr/reference/overview>
- <https://developer-community.icims.com/>
- <https://developer.ukg.com/>
- <https://developers.bamboohr.com/>
- <https://docs.jobkit.io/>
- <https://www.jobboardly.com/>
- <https://www.jobiqo.com/>
- <https://jboard.io/>
- <https://www.smartjobboard.com/>
- <https://www.jobboard.io/>
- <https://www.wiley.com/en-us/publishing/society-revenue-services/madgex>
- <https://www.talenetic.com/>
- <https://www.jobboardmount.com/>
- <https://www.careersitecloud.com/>
- <https://www.jobboard.com/>
- <https://arthajobboard.com/>
- <https://www.jobboardhq.com/>
- <https://nodex.co.uk/services/job-board-software>
- <https://ejobsitesoftware.com/>

Open-source references:

- <https://github.com/devilscrapes/ats-jobs-api>
- <https://github.com/ctriolab/ats-jobs>
- <https://github.com/ever-jobs/ever-jobs>
- <https://github.com/strelov1/freehire>
- <https://github.com/kalil0321/ats-scrapers>
- <https://github.com/datascry/openroles>
