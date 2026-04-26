# Round 1 Search Benchmark Report

- generated_at: `2026-04-26T14:02:27.630381+00:00`
- benchmark_state: `round1_reviewable`
- mode: `live`
- matrix_queries: `12`

## Lane Metrics

| lane | empty_result_rate | non_empty_result_rate | official_source_top5_rate | useful_url_yield | unique_useful_url_yield | artifact_vs_portal_rate | duplicate_url_rate | median_latency_ms | hard_failure_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.417 | 0.583 | 0.583 | 1.750 | 1.333 | 0.500 | 0.000 | 842 | 0.000 |
| searxng | 0.000 | 1.000 | 1.000 | 4.083 | 3.500 | 0.688 | 0.000 | 602 | 0.000 |

## Baseline Failure Modes

- none

## Baseline Representative Samples

- `san-jose-agenda`: San Jose CA city council agenda pdf
  - City Council Meeting Agendas and Minutes | City of San José :: https://www.sanjoseca.gov/your-government/agendas-minutes :: official=True useful=True
  - City Council Meeting Agendas and Minutes | City of San José :: https://www.sanjoseca.gov/your-government/appointees/city-clerk/council-agendas-minutes/council-agendas :: official=True useful=True
  - Participate & Watch Public Meetings | City of San José :: https://www.sanjoseca.gov/your-government/appointees/city-clerk/council-agendas-minutes/participate-watch-public-meetings :: official=True useful=True
- `san-jose-minutes`: San Jose CA city council minutes pdf
  - City Council Meeting Agendas and Minutes | City of San José :: https://www.sanjoseca.gov/your-government/agendas-minutes :: official=True useful=True
  - PDF City Council Meeting MINUTES - legistar.granicus.com :: https://legistar.granicus.com/sanjose/attachments/098e14c4-6a54-40b6-a9f1-2259441883ce.pdf :: official=False useful=False
  - City of San José - Meeting of City Council on 5/6/2025 at 1:30 PM :: https://sanjose.legistar.com/MeetingDetail.aspx?LEGID=7215&GID=317 :: official=True useful=False
- `san-jose-ordinance`: San Jose CA municipal code ordinance
  - Municode Library :: https://library.municode.com/ca/san_jose/codes/code_of_ordinances :: official=True useful=True
  - Ordinances & Proposed Updates | City of San José :: https://www.sanjoseca.gov/your-government/departments-offices/planning-building-code-enforcement/planning-division/ordinances-proposed-updates :: official=True useful=True
  - PDF San Jose, CA Code of Ordinances :: https://sj-admin.s3-us-west-2.amazonaws.com/0000_0000_CityOfSanJose_CodeOfOrdinance.pdf :: official=False useful=False
- `oakland-agenda`: Oakland CA city council agenda packet
  - Meetings & Agendas | City of Oakland, CA :: https://www.oaklandca.gov/Government/Meetings-Agendas :: official=True useful=True
  - Oakland City Council Agenda -- All Meetings Committee :: http://councilmatic.aws.openoakland.org/ :: official=False useful=False
  - Oakland City Council Agenda -- All Meetings Committee (2025) :: https://oaklandcouncil.net/2025/all-meetings.html :: official=False useful=False

## Searxng Failure Modes

- none

## Searxng Representative Samples

- `san-jose-agenda`: San Jose CA city council agenda pdf
  - City Council Meeting Agendas and Minutes | City of San José :: https://www.sanjoseca.gov/your-government/agendas-minutes :: official=True useful=True
  - City Council Meeting Agendas and Minutes | City of San José :: https://www.sanjoseca.gov/your-government/appointees/city-clerk/council-agendas-minutes/council-agendas :: official=True useful=True
  - Guide to Council Meetings | City of San José :: https://www.sanjoseca.gov/your-government/appointees/city-clerk/council-agendas-minutes/guide-to-council-meetings :: official=True useful=True
- `san-jose-minutes`: San Jose CA city council minutes pdf
  - City Council Meeting Agendas and Minutes | City of San José :: https://www.sanjoseca.gov/your-government/appointees/city-clerk/council-agendas-minutes/council-agendas :: official=True useful=True
  - City Council Meeting Agendas and Minutes | City of San José :: https://www.sanjoseca.gov/your-government/agendas-minutes :: official=True useful=True
  - City of San José - Calendar :: https://sanjose.legistar.com/ :: official=True useful=False
- `san-jose-ordinance`: San Jose CA municipal code ordinance
  - Code of Ordinances | San Jose, CA - Municode Library :: https://library.municode.com/ca/san_jose/codes/code_of_ordinances :: official=True useful=True
  - Ordinances & Proposed Updates | City of San José :: https://www.sanjoseca.gov/your-government/departments-offices/planning-building-code-enforcement/planning-division/ordinances-proposed-updates :: official=True useful=True
  - Code of Ordinances | San Jose, CA - Municode Library :: https://library.municode.com/ca/san_jose/ordinances/code_of_ordinances :: official=True useful=True
- `oakland-agenda`: Oakland CA city council agenda packet
  - Meetings & Agendas | City of Oakland, CA :: https://www.oaklandca.gov/Government/Meetings-Agendas :: official=True useful=True
  - Oakland City Council Meeting :: https://oakland.legistar.com/ :: official=True useful=True
  - City Council Meeting Information | City of Oakland, CA :: https://www.oaklandca.gov/Government/Meetings-Agendas/City-Council-Meeting-Information :: official=True useful=True
