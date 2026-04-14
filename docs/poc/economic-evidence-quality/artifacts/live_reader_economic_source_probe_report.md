# Live Reader Economic Source Probe

- feature_key: `bd-2agbe.6`
- probe_version: `2026-04-14.live-reader-probe-v1`
- mode: `live`
- generated_at: `2026-04-14T07:59:46.681713+00:00`

## Summary

- total_cases: 3
- reader_success_cases: 2
- substantive_text_cases: 1
- economics_topic_signal_cases: 2
- numeric_parameter_signal_cases: 0
- decision_grade_candidate_cases: 0

## Cases

| case_id | reader_success | substantive_text | economics_topic_signal | numeric_parameter_signal | likely_portal_or_navigation | decision_grade_candidate | blocking_gate |
|---|---:|---:|---:|---:|---:|---:|---|
| sanjose_legistar_cost_of_residential_development | true | true | true | false | false | false | parameterization_sufficiency |
| sanjose_records_contract_pdf_con667337_002 | true | false | true | false | true | false | reader_source_quality |
| sanjose_housing_council_memos_portal | false | false | false | false | true | false | reader_source_quality |

## Audit Notes

- Topic text without numeric parameters is qualitative-only and not decision-grade.
- Navigation/portal-like reader outputs are treated as reader/source-quality failures.

### sanjose_legistar_cost_of_residential_development

- url: https://sanjose.legistar.com/MeetingDetail.aspx?ID=1315729&GUID=3C17B03F-B014-43D5-B8DF-44024CDE065B&Options=info%7C&Search=
- blocking_gate: parameterization_sufficiency
- chars: 6411
- portal_reasons: -
- economics_keywords: contract, cost, development, economics, housing, residential
- numeric_examples: -
- fetch_error: -

```text
| File# | Ver. | Agenda# | Agenda Note | Type | Title | Action | Result | Action Details | Video |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | Please scroll to the end for information about the City Council Agenda and for the Rules of Conduct of the meeting. | | | Not available | Not available |
| | | | | | Public Comment in Person Only | | | Not available | Not available |
| | | | | | For live translations in over 50 languages, please go to https://attend.wordly.ai/join/FAYU-7105 | | | Not available | Not available |
| | | | | | American Disability Act | | | Not available | Not available |
| | | | | | To request an alternative format agenda under the Americans
```

### sanjose_records_contract_pdf_con667337_002

- url: https://records.sanjoseca.gov/Contracts/CON667337-002.pdf
- blocking_gate: reader_source_quality
- chars: 4523
- portal_reasons: navigation_phrases:5, records_pdf_navigation_render
- economics_keywords: budget, development, economic, housing, tax
- numeric_examples: -
- fetch_error: -

```text
# Search Records (GILES) | City of San JoséSkip to Main Content# City of San JoséHome MenuAccessibilityActivate Search## Popular Searches* Browse City Jobs* Business License* Make a PaymentPowered by TranslateSmaller Default Larger68℉# City Clerk* Home* Residents* Homelessness Hub* Payments* Parks & Recreation* Building Permits* City Maps* Recycling & Garbage* Housing* Animals* Report Issues* Emergency Preparedness* Police* Fire* Volunteering* Library* Free Public Wi-Fi* Businesses* Check Zoning* Find Land Use Info* Apply for Sign Permit* Apply for Building Permit* Register Business or Rental* Pay Business Tax* Help for Small Business* Why Locate Here* Move Business to San Jose* Become a Pre
```

### sanjose_housing_council_memos_portal

- url: https://www.sanjoseca.gov/your-government/departments-offices/housing/policies-and-data/reports-and-memos/city-council-memos
- blocking_gate: reader_source_quality
- chars: 0
- portal_reasons: url_signal:your-government, url_signal:reports-and-memos, url_signal:city-council-memos
- economics_keywords: -
- numeric_examples: -
- fetch_error: http_error:400:{"error":{"code":"1214","message":"The requested resource was not found"}}

```text

```
