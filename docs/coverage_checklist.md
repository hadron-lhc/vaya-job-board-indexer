# Coverage Checklist

Generated: 2026-11-11T03:31:04.343550+00:00

Source of truth: `docs/platform_matrix.csv`.

## Summary

| Metric | Value |
| --- | ---: |
| Total platforms | 78 |
| ATS platforms | 58 |
| Job-board platforms | 20 |
| Configured sources | 30 |
| Indexed jobs | 2582 |

## Status counts

| Status | Count |
| --- | ---: |
| `ACCESS_BLOCKED` | 6 |
| `LIVE_TESTED_MULTI_TENANT` | 15 |
| `NOT_RESEARCHED` | 1 |
| `RESEARCHED` | 56 |

## Full checklist

| Platform | Category | Status | Sources | Evidenced | Jobs | Missing | Evidence |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| ADP | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://developers.adp.com/ |
| ApplicantPro | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.applicantpro.com/ |
| Ashby | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 909 | none | https://api.ashbyhq.com/posting-api/job-board/ashby?includeCompensation=true<br>`artifacts/live_runs/ashby-ashby.json` |
| Avature | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.avature.com/ |
| BambooHR | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 14 | none | https://flyio.bamboohr.com/careers/list<br>`artifacts/live_runs/bamboohr-acme.json` |
| BrassRing | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://brassring.com/ |
| Breezy HR | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 22 | none | https://breezy-hr.breezy.hr/json<br>`artifacts/live_runs/breezy-breezyhr.json` |
| CareerPlug | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.careerplug.com/ |
| Comeet | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.comeet.com/ |
| CSOD | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.cornerstoneondemand.com/ |
| Dayforce | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.dayforce.com/ |
| Deel | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.deel.com/ |
| Dover | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.dover.com/ |
| Eightfold AI | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://nvidia.eightfold.ai/careers |
| FirstStage | ATS | `NOT_RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, product_identity | https://firststage.com/ |
| Freshteam | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.freshteam.com/ |
| Gem.com | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.gem.com/ |
| GoHire | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.gohire.io/ |
| Greenhouse | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 982 | none | https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true<br>`artifacts/live_runs/greenhouse-airbnb.json` |
| HiBob | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.hibob.com/ |
| HireBridge | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.hirebridge.com/ |
| HireHive | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.hirehive.com/ |
| Hireology | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.hireology.com/ |
| HiringThing | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.hiringthing.com/ |
| iCIMS | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://developer-community.icims.com/ |
| iSolvedHire | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.isolvedhire.com/ |
| JazzHR | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 23 | none | https://snapsheet.applytojob.com/apply/jobs<br>`artifacts/live_runs/jazzhr-loccitane.json` |
| Jobvite | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://jobs.jobvite.com/logitech/search |
| JOIN.com | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://join.com/ |
| Kula.ai | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.kula.ai/ |
| Lever.co | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 391 | none | https://api.lever.co/v0/postings/leverdemo?mode=json<br>`artifacts/live_runs/lever-palantir.json` |
| Manatal | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.manatal.com/ |
| Oracle Recruiting | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.oracle.com/human-capital-management/recruiting/ |
| PageUp | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.pageuppeople.com/ |
| Paradox | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.paradox.ai/ |
| Paycom | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.paycom.com/ |
| Paycor | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.paycor.com/ |
| Paylocity | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.paylocity.com/ |
| Personio | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 13 | none | https://lanch.jobs.personio.de/xml?language=en<br>`artifacts/live_runs/personio-deskbird.json` |
| Phenom People | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.phenom.com/ |
| Pinpoint | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 6 | none | https://avaaz.pinpointhq.com/postings.json<br>`artifacts/live_runs/pinpoint-avaaz.json` |
| Polymer | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.polymer.co/ |
| Recooty | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://recooty.com/ |
| Recruitee | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 39 | none | https://bunq.recruitee.com/api/offers/<br>`artifacts/live_runs/recruitee-bunq.json` |
| Rippling | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 22 | none | https://ats.rippling.com/api/v2/board/netatwork/jobs?page=0<br>`artifacts/live_runs/rippling-netatwork.json` |
| Rival | ATS | `ACCESS_BLOCKED` | 0 | 0 | 0 | connector, second_tenant, access | https://rival.com/ |
| SAP SuccessFactors | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://help.sap.com/docs/SAP_SUCCESSFACTORS |
| SmartRecruiters | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 43 | none | https://api.smartrecruiters.com/v1/companies/linkedin3/postings?limit=1<br>`artifacts/live_runs/smartrecruiters-canva.json` |
| talentReef | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.talentreef.com/ |
| Taleo | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.oracle.com/human-capital-management/taleo/ |
| Teamtailor | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 4 | none | https://bankgirotab.teamtailor.com/jobs.rss<br>`artifacts/live_runs/teamtailor-bankgirotab.json` |
| Trakstar | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.trakstar.com/ |
| TriNet | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.trinet.com/ |
| UltiPro | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://developer.ukg.com/ |
| WeRecruit | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://werecruit.com/ |
| Workable | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 30 | none | https://apply.workable.com/api/v1/widget/accounts/huggingface?details=true<br>`artifacts/live_runs/workable-huggingface.json` |
| Workday | ATS | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 10 | none | https://salesforce.wd12.myworkdayjobs.com/wday/cxs/salesforce/External_Career_Site/jobs<br>`artifacts/live_runs/workday-adobe.json` |
| Zoho Recruit | ATS | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.zoho.com/recruit/ |
| Niceboard | Job Board | `LIVE_TESTED_MULTI_TENANT` | 2 | 2 | 74 | none | https://afa.niceboard.co/api/jobs<br>`artifacts/live_runs/niceboard-afa.json` |
| WP Job Manager | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://wpjobmanager.com/wp-json/wp/v2/job_listing?per_page=1 |
| JobKit | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://docs.jobkit.io/ |
| Jobboardly | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.jobboardly.com/ |
| Jobiqo | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.jobiqo.com/ |
| JBoard.io | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://jboard.io/ |
| JobBoardFire | Job Board | `ACCESS_BLOCKED` | 0 | 0 | 0 | connector, second_tenant, access | https://jobboardfire.com/ |
| SmartJobBoard | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://jobs.alanet.org/browse-jobs/ |
| JobBoard.io | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.hireheroesusa.org/ |
| Wiley Madgex | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.wiley.com/en-us/publishing/society-revenue-services/madgex |
| Talenetic | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.talenetic.com/ |
| JobMount | Job Board | `ACCESS_BLOCKED` | 0 | 0 | 0 | connector, second_tenant, access | https://www.jobboardmount.com/ |
| CareerSiteCloud | Job Board | `ACCESS_BLOCKED` | 0 | 0 | 0 | connector, second_tenant, access | https://www.careersitecloud.com/ |
| JobBoard.com | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.jobboard.com/ |
| Artha | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://arthajobboard.com/ |
| jobboardsoftware.com | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://jobboardsoftware.com/ |
| jobBoardHQ | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://www.estatejobs.com/ |
| Nodex | Job Board | `ACCESS_BLOCKED` | 0 | 0 | 0 | connector, second_tenant, access | https://nodex.co.uk/services/job-board-software |
| eJobBoard | Job Board | `ACCESS_BLOCKED` | 0 | 0 | 0 | connector, second_tenant, access | https://www.ejobboard.co.uk/ |
| ejobsitesoftware.com | Job Board | `RESEARCHED` | 0 | 0 | 0 | connector, second_tenant, live_endpoint_verification | https://ejobsitesoftware.com/demo/ |
