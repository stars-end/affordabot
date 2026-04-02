# Testing Story Catalog
**Epic**: `affordabot-bok6`
**Status**: Consolidating 🚀

This catalog defines the "Deep Validity" test suite for Affordabot V3. 
It combines **Persona-Based Functional Testing** with **Rigorous Data Integrity Testing**.

---

## 1. The "Deep Validity" Triad (Technical Rigor)
*Ensuring the system is intellectually honest and technically sound.*

| Story ID | Persona | Goal | Success Criteria |
|----------|---------|------|------------------|
| **`extraction_fidelity_check`** | Data Engineer | **Input Integrity**: Verify key figures survive ingestion. | Input "$500 fee" → Exists in Vector Chunk. |
| **`citation_validity_check`** | Data Auditor | **Trace Integrity**: Verify analysis citations exist in source. | Analysis Quote == Source Text (Anti-Hallucination). |
| **`economic_impact_validity`** | Economic Expert | **Output Integrity**: Verify Golden Inputs produce correct logic. | Tax Hike Input → "High Negative Impact" Output. |

---

## 2. Persona Workflows (User Experience)
*Ensuring the system delivers value to its key stakeholders.*

| Story ID | Persona | Goal | Success Criteria |
|----------|---------|------|------------------|
| **`voter_bill_impact_journey`** | Informed Voter | **Comprehension**: Can a layperson find & understand impact? | Search "Zoning" → Clear "Econ 101" Summary (Supply/Cost). |
| **`trend_integrity_check`** | Economic Analyst | **Consistency**: Do the dashboards match the data? | Dashboard Total == Sum of Bill List. |
| **`glass_box_provenance_trace`** | Admin Debugger | **Explanation**: Can we explain a "0 Impact" result? | Trace View shows: Raw Text → Prompt → "No Data" Reason. |
| **`alert_system_verification`** | Admin Operator | **Proactivity**: Does urgent news reach the user? | High Impact Bill → Active Alert in Dashboard. |

---

## 3. Operational Baselines (Health Checks)
*Ensuring the application is running.*

- `jurisdiction_detail_view` (Page Load)
- `discovery_search_flow` (Integration)
- `review_queue_workflow` (Action)

---

## Usage Guide
Run the full suite using:
```bash
make verify-stories
```
(Implementation pending Golden Seed Data `BILL-TEST-101`).

---

## 4. Plaid Sandbox Stories (Accounts Linking)
*Sandbox coverage for account-link UX and failure handling.*

| Story ID | Persona | Goal | Success Criteria |
|----------|---------|------|------------------|
| **`plaid_sandbox_happy_path`** | Admin Operator | **Happy Path**: Link a sandbox institution account from `/settings/accounts`. | Plaid Link closes successfully and a linked account row/card is visible. |
| **`plaid_sandbox_login_failure`** | Admin Operator | **Failure Path**: Invalid sandbox credentials fail safely. | Error state appears in Link, flow exits safely, and no linked account is created. |

### Engine Recommendation (Plaid Stories)
- **Playwright is the default execution engine** for Plaid sandbox stories.
- **uismoke is orchestration/proof only** and should run these stories only when deterministic end-to-end execution is viable in that environment.
