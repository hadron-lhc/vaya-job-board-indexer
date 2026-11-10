# Feasibility Report

Date: 2026-11-10
Challenge deadline: 2026-11-30
Status: Phase 1 research complete; no connectors implemented

## 1. Executive summary

The project is technically feasible as a modular Python monolith, but full 78-platform coverage with live-verified connectors by November 30 is not realistic for a solo developer starting from an empty repository.

What is realistic:

- A strong, reliable core indexer.
- 11 high-confidence public-feed connectors.
- Several HTML/JSON-LD connectors.
- A generic fallback framework for long-tail platforms.
- A coverage dashboard that is honest about verified, unverified, and blocked platforms.

What is not realistic by November 30:

- Implementing and live-testing all 58 ATS and 20 job-board platforms.
- Obtaining enterprise API access for platforms that require customer credentials.
- Verifying multiple tenants for every platform.
- Claiming full coverage where only a homepage or an unverified pattern exists.

Decision:

- **GO** for Phase 2 on the high-confidence public connectors and a generic extraction framework.
- **NO-GO** for claiming full 78-platform live-verified coverage by November 30 without additional engineering time or access to customer/enterprise credentials.

## 2. Evidence base

- `docs/platform_matrix.csv`: 78 rows, 58 ATS and 20 job boards.
- `docs/research_notes.md`: endpoint evidence, field mappings, live HTTP observations, and caveats.
- Research date: 2026-11-10.
- No connector code exists yet.
- 11 platform endpoint patterns returned live data during research.
- 71 rows have enough desk research to propose an extraction path.
- 6 rows are access-blocked.
- 1 row remains not researched.

Confidence distribution:

| Confidence | Count | Meaning |
| --- | ---: | --- |
| high | 11 | Live public endpoint returned data; schema observed. |
| medium | 19 | Public page, docs, or sample exists; endpoint/schema partially verified. |
| low | 48 | Homepage/docs only, unverified pattern, or access issue. |
| Total | 78 | |

## 3. Coverage feasibility

### 3.1 High-confidence public feeds

These are the best candidates for Phase 2. Each returned live data during research.

| Platform | Method | Key limitation |
| --- | --- | --- |
| Greenhouse | Public JSON API | Board token required. |
| Lever | Public JSON API | Company slug required. |
| Ashby | Public JSON API | Org slug required; no company name in item. |
| Workable | Public JSON API | Account subdomain required. |
| SmartRecruiters | Public JSON API | Valid company slug required; list may omit full description. |
| Recruitee | Public JSON API | Company subdomain required. |
| Personio | Public XML | XML may lack direct application URL. |
| Teamtailor | Public RSS | RSS may be truncated; JSON endpoint returned 404. |
| Pinpoint | Public JSON API | Company slug required. |
| Rippling | Public JSON API | List may omit full description. |
| Workday | Undocumented public JSON API | POST required; detail request needed for description. |

Estimated effort: 6-8 engineering days for these 11 connectors once the shared framework exists.

### 3.2 Medium-confidence HTML/JSON-LD and authenticated platforms

These are feasible but need more verification:

- JazzHR: public HTML board confirmed.
- Eightfold AI: public HTML confirmed; API returned 403.
- JobBoardHQ: multiple live sample boards; no public API confirmed.
- JobBoard.com: public HTML live; JSON-LD hypothesis.
- eJobSiteSoftware: public demo live.
- Artha: public HTML live.
- JobKit: Basic auth API; public feed unverified.
- Jobboardly: bearer-token API; plan-dependent.
- Jobiqo: API key required.
- JBoard.io: Enterprise API key.
- SmartJobBoard: Enterprise API key; sample board live.
- JobBoard.io: Enterprise API key; sample board live.
- Wiley Madgex: account-managed contract.
- Talenetic: custom XML feed.
- JobMount: posting/import API only.

Estimated effort: 8-14 engineering days, excluding time waiting for credentials or commercial approval.

### 3.3 Long-tail HTML platforms

43 matrix rows are HTML-first. Many may expose hidden JSON, but this is not verified. Examples:

- ADP, ApplicantPro, Avature, BrassRing, CareerPlug, Comeet, CSOD, Dayforce, Deel, Dover, Freshteam, Gem.com, GoHire, HiBob, HireBridge, HireHive, Hireology, HiringThing, iCIMS, iSolvedHire, Jobvite, JOIN.com, Kula.ai, Manatal, Oracle Recruiting, PageUp, Paradox, Paycom, Paycor, Paylocity, Phenom People, Polymer, Recooty, SAP SuccessFactors, talentReef, Taleo, Trakstar, TriNet, UltiPro, WeRecruit, Zoho Recruit.
- WP Job Manager and several job-board platforms also fall into HTML-first or unknown-feed territory.

Estimated effort: 15-25 engineering days for meaningful coverage, because each platform has different markup, pagination, and anti-bot behavior.

### 3.4 Access-blocked and unresolved

| Platform | Status | Issue |
| --- | --- | --- |
| Rival | `ACCESS_BLOCKED` | Domain did not resolve; product identity unclear. |
| eJobBoard | `ACCESS_BLOCKED` | Domain did not resolve; likely discontinued. |
| Nodex | `ACCESS_BLOCKED` | Official site returned 403; custom platform. |
| JobBoardFire | `ACCESS_BLOCKED` | Official site returned 403; no public API verified. |
| CareerSiteCloud | `ACCESS_BLOCKED` | Official site returned 403; no API verified. |
| JobMount | `ACCESS_BLOCKED` | Only posting API found; site returned 403. |
| FirstStage | `NOT_RESEARCHED` | Product identity and public job surface unverified. |

Additional unresolved issues:

- BambooHR public JSON endpoint is unverified.
- WP Job Manager vendor REST endpoint returned 404; a live customer board is needed.
- Niceboard public feed pattern is reported but no live tenant was verified.
- Jobvite test URLs redirected to a generic support page.
- Eightfold API returned 403.
- Some sample boards returned 403 intermittently.

## 4. Most feasible platforms

Ranked by evidence quality and implementation risk:

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
12. JazzHR
13. Eightfold AI
14. JobBoardHQ sample boards
15. JobBoard.com
16. eJobSiteSoftware
17. Artha

The first 11 should be the initial connector set. The next 6 are reasonable HTML/JSON-LD follow-ups.

## 5. Biggest blockers

### 5.1 Enterprise access

Several platforms require customer or enterprise credentials:

- SAP SuccessFactors
- Oracle Recruiting
- Zoho Recruit API
- iCIMS
- JobKit
- Jobboardly
- Jobiqo
- JBoard.io
- SmartJobBoard
- JobBoard.io
- Wiley Madgex
- Talenetic

Without credentials or a contract, these cannot be honestly marked as working.

### 5.2 Tenant discovery

A platform is not covered by one sample. Each connector must work across employers or boards. Several guessed slugs returned empty payloads or redirects. This is especially important for SmartRecruiters, Workday, Personio, Pinpoint, Rippling, and job-board platforms.

### 5.3 HTML variability

43 HTML-first platforms have different markup, pagination, and anti-bot behavior. A generic extractor helps, but cannot guarantee coverage without per-platform fixtures.

### 5.4 Closure detection

A failed fetch cannot be treated as closure. The system needs fetch-failure records, retry policy, and conservative closure rules. This is a design requirement, not a platform-specific blocker.

### 5.5 Time

The deadline is 21 days from the research date. A solo developer cannot build, test, and verify 78 connectors in that window with the current evidence.

## 6. Effort model

Rough solo effort estimate:

| Work package | Estimate |
| --- | ---: |
| Core framework, normalized model, storage, API, search UI | 5-7 days |
| 11 high-confidence public connectors | 6-8 days |
| 6 medium-confidence HTML/JSON-LD connectors | 4-6 days |
| 6 authenticated/contract platforms | 4-8 days plus external approval |
| 43 long-tail HTML platforms | 15-25 days |
| Access-blocked/unresolved platforms | 5-10 days |
| Hardening, deployment, docs, coverage dashboard | 4-6 days |
| Total | 43-70 days |

The estimate assumes one developer, no external credentials delays, and no major platform changes. Even with a generic extractor, the long tail dominates.

## 7. Realistic plan through November 30

### November 10-11: Phase 1 closeout

- Finalize the four Phase 1 documents.
- Validate 78 rows and 16 columns.
- Confirm no invented endpoints or secrets.
- Freeze the initial connector scope.

### November 12-17: Core and first six connectors

- Build the modular monolith skeleton.
- Add normalized job model, SQLite schema, fetch logs, and fixture tests.
- Implement Greenhouse, Lever, Ashby, Workable, SmartRecruiters, and Recruitee.
- Add a coverage report that distinguishes verified, unverified, and blocked.

### November 18-22: Next five public feeds and first HTML connectors

- Implement Personio, Teamtailor, Pinpoint, Rippling, and Workday.
- Add JazzHR and Eightfold AI HTML extraction if fixtures are stable.
- Add a generic JSON-LD extractor and a conservative HTML fallback.

### November 23-27: Search, deduplication, updates, and job-board samples

- Add search API and basic UI.
- Add deduplication keys and source-link preservation.
- Add fetch-failure tracking and conservative closure.
- Add JobBoardHQ, JobBoard.com, eJobSiteSoftware, and Artha sample extraction.
- Verify at least one tenant per implemented platform and multiple tenants where possible.

### November 28-29: Hardening and handoff

- Run live multi-tenant checks.
- Add deployment instructions, connector documentation, operating costs, and known limitations.
- Produce the coverage checklist with live examples.
- Freeze features.

### November 30: Submission

- Final validation and submission.
- No new platform work on submission day.

This plan produces a credible partial indexer, not full 78-platform coverage.

## 8. Recommended MVP scope

If the goal is a strong submission rather than an unrealistic full-coverage claim:

- Implement 11 high-confidence public connectors.
- Add 4-6 HTML/JSON-LD connectors with stable fixtures.
- Build a generic fallback that can be configured per platform.
- Provide a coverage dashboard with evidence and limitations.
- Document the remaining 50+ platforms honestly.

This is more defensible than claiming all 78 are working when many are not verified.

## 9. Operating cost

Expected cost: near zero for development and a small demo.

- Python runtime: free.
- SQLite: free.
- `httpx`, `Pydantic`, `SQLAlchemy`, `FastAPI`, `pytest`, `selectolax`: open source.
- No paid proxy service required for the high-confidence public feeds.
- No paid LLM parsing required.
- Optional small VPS or free-tier hosting for the demo.
- Browser automation only if an HTML platform cannot be fetched otherwise; it increases CPU and maintenance cost.

Hidden costs:

- Enterprise API access may require a customer relationship or paid plan.
- Some job-board APIs are gated behind Pro/Enterprise plans.
- Long-tail HTML maintenance is an ongoing engineering cost, not a hosting cost.

## 10. Go/no-go criteria

Proceed to Phase 2 only if all are true:

- The initial connector set is limited to platforms with verified public access.
- The system records fetch failures separately from closures.
- Every implemented connector has fixtures and at least one live test.
- The coverage dashboard does not overstate unverified platforms.
- The team accepts that full 78-platform coverage is a post-deadline goal unless access is obtained.

Do not proceed with a claim of full coverage if:

- A platform is only a homepage with no verified job extraction path.
- A connector has only been tested against a guessed tenant.
- An API requires credentials that are not available.
- A failed fetch is being used to close jobs.

## 11. Final recommendation

**Conditional GO.**

Build the core indexer and the 11 high-confidence public connectors first. Add HTML/JSON-LD connectors where evidence is strong. Treat the remaining platforms as a documented coverage roadmap, not as completed work.

**NO-GO for a truthful full 78-platform live-verified submission by November 30** under the current solo, zero-credential, empty-repository constraints. The research supports a credible partial product and a clear plan, but not an honest claim of complete coverage in 21 days.
