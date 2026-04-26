# Round 1 Search Benchmark Report

- generated_at: `2026-04-25T15:28:24.477432+00:00`
- benchmark_state: `round1_reviewable`
- mode: `fixture`
- matrix_queries: `12`

## Lane Metrics

| lane | empty_result_rate | non_empty_result_rate | official_source_top5_rate | useful_url_yield | unique_useful_url_yield | artifact_vs_portal_rate | duplicate_url_rate | median_latency_ms | hard_failure_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.833 | 0.000 | 0 | 0.000 |
| searxng | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0 | 0.000 |

## Baseline Failure Modes

- none

## Baseline Representative Samples

- `san-jose-agenda`: San Jose CA city council agenda pdf
  - City Council Agenda :: https://sanjoseca.gov/agendas/city-council-agenda.pdf :: official=True useful=True
- `san-jose-minutes`: San Jose CA city council minutes pdf
  - City Council Minutes :: https://sanjoseca.gov/minutes/city-council-minutes.pdf :: official=True useful=True
- `san-jose-ordinance`: San Jose CA municipal code ordinance
  - San Jose Municipal Code :: https://library.municode.com/ca/san_jose/codes/code_of_ordinances :: official=True useful=True
- `oakland-agenda`: Oakland CA city council agenda packet
  - Oakland Meeting Detail :: https://oakland.legistar.com/MeetingDetail.aspx?ID=100 :: official=True useful=True

## Searxng Failure Modes

- none

## Searxng Representative Samples

- `san-jose-agenda`: San Jose CA city council agenda pdf
  - SJ Agenda :: https://sanjoseca.gov/agendas/city-council-agenda.pdf :: official=True useful=True
- `san-jose-minutes`: San Jose CA city council minutes pdf
  - SJ Minutes :: https://sanjoseca.gov/minutes/city-council-minutes.pdf :: official=True useful=True
- `san-jose-ordinance`: San Jose CA municipal code ordinance
  - SJ Code :: https://library.municode.com/ca/san_jose/codes/code_of_ordinances :: official=True useful=True
- `oakland-agenda`: Oakland CA city council agenda packet
  - Oakland Agenda Packet :: https://oaklandca.gov/documents/agenda-packet.pdf :: official=True useful=True
