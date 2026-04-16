# Live Reader Economic Source Probe

- feature_key: `bd-2agbe.6`
- probe_version: `2026-04-14.live-reader-probe-v1`
- mode: `replay`
- generated_at: `2026-04-14T08:02:01.029771+00:00`

## Summary

- total_cases: 3
- reader_success_cases: 3
- substantive_text_cases: 1
- economics_topic_signal_cases: 3
- numeric_parameter_signal_cases: 0
- decision_grade_candidate_cases: 0

## Cases

| case_id | reader_success | substantive_text | economics_topic_signal | numeric_parameter_signal | likely_portal_or_navigation | decision_grade_candidate | blocking_gate |
|---|---:|---:|---:|---:|---:|---:|---|
| sanjose_legistar_cost_of_residential_development | true | true | true | false | false | false | parameterization_sufficiency |
| sanjose_records_contract_pdf_con667337_002 | true | false | true | false | true | false | reader_source_quality |
| sanjose_housing_council_memos_portal | true | false | true | false | true | false | reader_source_quality |

## Audit Notes

- Topic text without numeric parameters is qualitative-only and not decision-grade.
- Navigation/portal-like reader outputs are treated as reader/source-quality failures.

### sanjose_legistar_cost_of_residential_development

- url: https://sanjose.legistar.com/MeetingDetail.aspx?ID=1315729&GUID=3C17B03F-B014-43D5-B8DF-44024CDE065B&Options=info%7C&Search=
- blocking_gate: parameterization_sufficiency
- chars: 766
- portal_reasons: -
- economics_keywords: budget, contract, cost, development, economic, fee, fiscal, housing, rent, residential, revenue, subsidy, tax
- numeric_examples: -
- fetch_error: -

```text
Agenda item summary for cost of residential development policy update. The staff memo discusses housing affordability outcomes, fee and tax context, fiscal impact framing, budget tradeoffs, and contract delivery implications for development activity in San Jose. This notice includes Levine Act boilerplate that bars officials from participating if campaign contributions exceed $500 from a party to the proceeding. The discussion references economic development priorities, subsidy considerations, rent pressure, and expected revenue effects across implementation scenarios. The item explains that the analysis remains qualitative at this stage and does not publish numeric pass through rates, dolla
```

### sanjose_records_contract_pdf_con667337_002

- url: https://records.sanjoseca.gov/Contracts/CON667337-002.pdf
- blocking_gate: reader_source_quality
- chars: 376
- portal_reasons: navigation_phrases:8, records_pdf_navigation_render
- economics_keywords: housing
- numeric_examples: -
- fetch_error: -

```text
Search Records GILES City of San Jose. Skip to main content. City Clerk. Home menu accessibility search. Popular links include business license, payments, housing, police, fire, library, and city calendar. Department listing and council links are shown with navigation sections. Participate and watch public meetings. Official city records. Terms and privacy. Sign in account.
```

### sanjose_housing_council_memos_portal

- url: https://www.sanjoseca.gov/your-government/departments-offices/housing/policies-and-data/reports-and-memos/city-council-memos
- blocking_gate: reader_source_quality
- chars: 281
- portal_reasons: url_signal:your-government, url_signal:reports-and-memos, url_signal:city-council-memos
- economics_keywords: economic, housing
- numeric_examples: -
- fetch_error: -

```text
Housing reports and memos listing page for city council memos. This page is a portal index with links to memo titles, publish dates, and categories. It contains navigation and directory content and does not provide standalone analysis text for direct economic parameter extraction.
```
