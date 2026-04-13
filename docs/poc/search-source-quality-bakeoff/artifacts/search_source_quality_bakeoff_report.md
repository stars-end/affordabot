# Search Source Quality Bakeoff

- Generated at: `2026-04-13T23:30:04.540369+00:00`
- Feature key: `bd-9qjof.8`
- Providers: `searxng, tavily, exa`
- Top-k: `5`
- Timeout seconds: `30`

## Provider Summary

| Provider | Provider score | MVP eligible | Query success % | Reader-ready % | Official hit % | Median score | P90 latency (ms) | Failures |
|---|---:|---|---:|---:|---:|---:|---:|---|
| exa | 72.04 | False | 68.4 | 31.6 | 73.7 | 75.00 | 195 | - |
| searxng | 71.39 | False | 68.4 | 31.6 | 94.7 | 70.00 | 3112 | - |
| tavily | 73.61 | False | 68.4 | 36.8 | 84.2 | 75.00 | 463 | - |

## Recommendation

- Best candidate: `tavily`
- MVP ready: `False`
- Reason: `no_provider_meets_mvp_threshold_best_candidate_only`
- Action: `do_not_lock_provider_run_full_reader_gate_or_tune_corpus`

## Query Winners

| Query | Winner | Top score | URL |
|---|---|---:|---|
| San Jose CA city council meeting minutes housing | exa | 100.00 | https://sanjose.legistar.com/View.ashx?GUID=CF0F61B5-1467-4299-B504-21A4ADD6FCFF&ID=1345653&M=A |
| San Jose city council agenda affordable housing | exa | 90.00 | https://sanjose.legistar.com/View.ashx?GUID=CF0F61B5-1467-4299-B504-21A4ADD6FCFF&ID=1345653&M=A |
| San Jose planning commission minutes housing development | tavily | 85.00 | https://sanjose.legistar.com/MeetingDetail.aspx?LEGID=7853&GID=317&G=920296E4-80BE-4CA2-A78F-32C5EFCF78AF |
| San Jose rent stabilization committee meeting minutes | searxng | 70.00 | https://www.sanjoseca.gov/your-government/departments-offices/housing/resource-library/council-memos |
| San Jose city clerk council minutes PDF housing | exa | 95.00 | https://sanjose.legistar.com/gateway.aspx?ID=520bd440-134c-4445-a308-f7a2689cfba2.pdf&M=F |
| San Jose city council housing memorandum | exa | 80.00 | https://www.sanjoseca.gov/your-government/departments-offices/housing/resource-library/council-memos |
| Saratoga CA city council meeting minutes housing | searxng | 85.00 | https://www.saratoga.ca.us/AgendaCenter/City-Council-13 |
| Saratoga CA planning commission minutes ADU | searxng | 85.00 | https://www.saratoga.ca.us/357/Planning-Commission |
| Saratoga CA housing element update public hearing minutes | exa | 80.00 | https://saratoga.ca.us/499/Housing-Element-Update |
| Saratoga city council agenda affordable housing ordinance | exa | 80.00 | https://www.saratoga.ca.us/AgendaCenter/ViewFile/Agenda/_04022025-1317 |
| Santa Clara County Board of Supervisors meeting minutes housing | exa | 70.00 | https://bos.santaclaracounty.gov/board-supervisors/meetings-board-supervisors-and-board-policy-committees |
| Santa Clara County affordable housing committee minutes | searxng | 25.00 | https://osh.santaclaracounty.gov/solutions-homelessness/continuum-care/service-provider-partners-training-and-resources/continuum-care-meeting-minutes |
| Santa Clara County planning commission agenda housing development | tavily | 65.00 | https://plandev.santaclaracounty.gov/events/planning-commission-2026-0 |
| Santa Clara County housing element adoption meeting minutes | searxng | 65.00 | https://plandev.santaclaracounty.gov/services/planning-services/general-plan-updates/housing-element-update-2023-2031 |
| Santa Clara County board agenda homelessness housing item | searxng | 35.00 | https://plandev.santaclaracounty.gov/services/planning-services/general-plan-updates/housing-element-update-2023-2031/current-draft |
| Mountain View CA city council meeting minutes housing | exa | 95.00 | http://mountainview.legistar.com/MeetingDetail.aspx?GUID=5982FDD1-736C-47D3-9606-1B619C66C45C&ID=1352177 |
| Sunnyvale CA city council housing agenda item minutes | exa | 75.00 | https://sunnyvaleca.legistar.com/ViewReport.ashx?G=FA76FAAA-7A&GID=270&GUID=C2D46B9B-63D5-4ABF-82B5-CC5C21C3A5C4&ID=6307329&M=R&N=Text&Title=Agenda+Item-No+Attachments+%28PDF%29 |
| San Jose city jobs police permits parks events | exa | 40.00 | https://www.sanjoseca.gov/your-government/departments-offices/special-events |
| Santa Clara County tourism museums top attractions | tavily | 30.00 | https://parks.santaclaracounty.gov/learn/visit-historic-sites |
