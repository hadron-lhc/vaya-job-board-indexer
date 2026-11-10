# Fixtures

These fixtures were derived from live public API responses on 2026-11-10:

- `greenhouse_stripe.json`: first two jobs from `https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true`
- `lever_palantir.json`: first two jobs from `https://api.lever.co/v0/postings/palantir?mode=json&limit=2&skip=0`
- `ashby_ashby.json`: first two jobs from `https://api.ashbyhq.com/posting-api/job-board/ashby?includeCompensation=true`
- `workable_huggingface.json`: first two jobs from `https://apply.workable.com/api/v1/widget/accounts/huggingface?details=true`
- `smartrecruiters_canva.json`: a combined fixture with the first two postings from `https://api.smartrecruiters.com/v1/companies/Canva/postings?limit=2&offset=0` and their detail responses.

Long HTML description fields were truncated to keep the repository small. The SmartRecruiters fixture stores the list response under `list` and detail responses under `details` so the connector's list-plus-detail flow can be tested without live HTTP. Field names and the overall response shapes are unchanged. No employer identifiers, job IDs, titles, locations, or URLs were invented.
