# Policy Evidence Quality Spine Cycle Learning Report

- feature_key: `bd-3wefe.13`
- scope: San Jose scraped/local policy evidence + secondary economic literature evidence
- purpose: verify whether the data moat can feed direct and indirect economic analysis without fabricating quantitative conclusions
- current verdict: `partial` - storage and mechanics are proven for the latest live cycle; decision-grade economic output is not yet proven

## Cross-Cycle Findings

- Windmill/backend mechanics work for live cycles: each executed `search_materialize -> freshness_gate -> read_fetch -> index -> analyze -> summarize_run`.
- Storage is now proven on the latest live cycle: Postgres package row linked to backend run, MinIO reader/package artifacts read back, and pgvector chunks/embeddings are present.
- The direct economic lane can extract concrete fee parameters when the selected artifact contains them, as cycle 5 did for San Jose Commercial Linkage Fee rates.
- The indirect economic lane is correctly fail-closed: cycles 4-7 recognize pass-through/incidence mechanisms but refuse San Jose quantitative household-cost claims without transferable incidence evidence.
- The biggest remaining data-moat gap is not storage. It is source targeting/ranking and package composition: the pipeline needs a unified package that joins local legislative artifacts, structured source metadata, and secondary economic literature with assumption governance.

## Latest Storage Proof

- status: `pass`
- details: `all_storage_gates_passed`
- package_id: `pkg-10adcd7b63e6262425240b5b`
- backend_run_id: `e1826ad9-cda9-4737-9c1d-316852460029`
- windmill_job_id: `019d94fb-dfaa-7681-7d6b-c1fb39f6ab49`
- idempotency_key: `bd-3wefe.13-live-cycle-07-20260416`
- pgvector_truth_role: `derived_index`
- postgres_package_row: `pass` - package_row_linked_to_backend_run_id
- minio_object_readback: `pass` - all_artifact_refs_read_back
- pgvector_derivation: `pass` - document_chunks_and_embeddings_present_with_derived_index_truth_role
- atomicity_or_replay: `pass` - pipeline_run_is_terminal_without_failed_steps
- storage/read-back: `pass` - all_storage_gates_passed

## Cycle Details

### Cycle 1

- hypothesis: Baseline San Jose meeting-minutes run can traverse Windmill -> backend -> search/read/index/analyze.
- windmill_job_id: `019d94d2-81ef-1117-0353-4c40719876ed`
- backend_run_id: `6695fe26-eaaf-47d1-9100-7eb861a7aa2f`
- selected_url: https://sanjose.legistar.com/View.ashx?M=A&ID=1345653&GUID=CF0F61B5-1467-4299-B504-21A4ADD6FCFF
- observed learning: Mechanics worked, but selected a procedural agenda that did not contain useful housing cost evidence.
- direct economic signal: None useful.
- indirect economic signal: None useful.
- LLM summary: The provided text consists of procedural instructions and logistical details for a San Jose City Council meeting, covering public participation rules and technical requirements for viewing the session. It contains no data related to housing or development costs.
- key extracted points:
  - The text outlines protocols for public speakers and filling out speaker cards.
  - It includes technical specifications for viewing the meeting online (browser versions).
  - It references agenda items like 'Labor Negotiations Update' but offers no financial data.
  - No signals regarding housing costs or development costs were identified.
- sufficiency: `Insufficient evidence for quantitative cost-of-living analysis.`
- next tweak: Retarget search toward housing impact fee artifacts rather than generic meeting minutes.

### Cycle 2

- hypothesis: Targeting San Jose affordable housing impact fee terms should retrieve a policy mechanism artifact.
- windmill_job_id: `019d94d7-1f8a-2755-6d12-4b8c20565081`
- backend_run_id: `2a6944e1-4c18-4265-b22e-4faa16d7c08b`
- selected_url: https://sanjose.legistar.com/View.ashx?GUID=DEBFA654-8B86-447A-997C-5ED36892BE3C&ID=7810086&M=F
- observed learning: Retrieved official Legistar AHIF memo and identified developer-fee mechanism, but lacked fee-rate parameters.
- direct economic signal: Developer fee mechanism found, no rate.
- indirect economic signal: Pass-through theory identified but no incidence evidence.
- LLM summary: The provided text details the City of San Jose's Affordable Housing Impact Fee (AHIF) program, adopted in 2014, which levies fees on new market-rate rental developments to fund affordable housing. It references a Nexus Study connecting market-rate development to the demand for low-income housing driven by service sector job creation. The document also outlines the administration of a $100 million Notice of Funding Availability (NOFA) and compliance requirements for fund expenditure.
- key extracted points:
  - The Housing Impact Fee Resolution requires developers of new rental housing (specifically 3 to 19 apartments initially) to pay a fee per net rentable square foot to fund affordable housing.
  - Revenue is dedicated to increasing the supply of housing for extremely low-, very low-, low-, and moderate-income households through acquisition, financing, and construction.
  - A Nexus Study by Keyser Marston Associates established that new market-rate development creates low-wage service jobs, thereby generating a demand for affordable housing.
  - The Housing Department issued a $100 million Notice of Funding Availability (NOFA) in August 2018 to distribute AHIF funds.
  - State law requires that collected funds be spent within five years; as of October 2019, no expenditures had been made from the AHIF Fund.
- sufficiency: `Quantitative economic analysis is not supported by the provided evidence. While the text references the existence of a Nexus Study and describes the fee mechanism (fee per net rentable square foot), it lacks the specific quantitative data necessary for analysis, such as the actual fee rate, specific construction costs, or detailed income thresholds.`
- next tweak: Search for fee schedule/rate sources.

### Cycle 3

- hypothesis: Targeting fiscal-year fee schedule wording should find missing numeric AHIF parameters.
- windmill_job_id: `019d94da-1547-48ec-9185-11b91651f5be`
- backend_run_id: `498aff1e-3af9-4a28-9895-5058ffc92e21`
- selected_url: https://sanjose.legistar.com/View.ashx?M=F&ID=7810086&GUID=DEBFA654-8B86-447A-997C-5ED36892BE3C
- observed learning: Retrieved same 2019 AHIF memo; no new rate evidence. Search recall repeated the mechanism artifact rather than the parameter artifact.
- direct economic signal: Still no reliable rate.
- indirect economic signal: Still no incidence evidence.
- LLM summary: The provided text outlines the establishment of San Jose's Affordable Housing Impact Fee (AHIF) via a resolution adopted on November 18, 2014. It specifies that the fee applies to new market-rate rental housing developments, specifically those with 3 to 19 apartments. However, the text cuts off before revealing the specific numeric fee rates.
- key extracted points:
  - City Council adopted the Housing Impact Fee Resolution on November 18, 2014.
  - The fee applies to developers of new market-rate rental residential developments.
  - Applicability is specifically for rental housing developments of three (3) to nineteen (19) apartments.
  - The evidence references an Affordable Housing Impact Fee Annual Report for FY2018-2019.
  - The specific numeric fee rate is not present in the provided text.
- sufficiency: `Insufficient. Secondary evidence required: The specific fee schedule or the full text of the Housing Impact Fee Resolution containing the numeric fee rates (e.g., dollars per square foot or per unit).`
- next tweak: Implement package persistence and make missing parameter gates explicit before more live cycles.

### Cycle 4

- hypothesis: After persistence patches, same AHIF query should prove stored package rows/artifacts and direct-vs-indirect classification.
- windmill_job_id: `019d94ec-e80e-0daf-3bb2-fdee2c6dce6a`
- backend_run_id: `f208078b-64af-4ef6-89b5-caaf5b0b8322`
- package_id: `pkg-ba380f24f5478f2590380e46`
- package_artifact: `minio://affordabot-artifacts/policy-evidence/packages/pkg-ba380f24f5478f2590380e46.json`
- selected_url: https://sanjose.legistar.com/View.ashx?GUID=DEBFA654-8B86-447A-997C-5ED36892BE3C&ID=7810086&M=F
- reader_artifact: `minio://affordabot-artifacts/artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/92e7e2d4aa29bfe9d552a09849d7d836cf167b0377a5f409c90519b299e7e76f.md`
- mechanism_family_hint: `fee_or_tax_pass_through`
- impact_mode_hint: `pass_through_incidence`
- secondary_research_needed: `True`
- storage_result: stored=`True`, artifact_write=`succeeded`, artifact_readback=`proven`, pgvector_truth_role=`derived_index`
- observed learning: Persisted package row and package artifact appeared; mechanism correctly classified as fee/tax pass-through and failed closed for missing incidence.
- direct economic signal: Applicability and governance facts extracted, but specific AHIF rate still missing.
- indirect economic signal: Pass-through mechanism recognized; incidence missing.
- LLM summary: The Affordable Housing Impact Fee (AHIF) program, established November 18, 2014, imposes a fee on developers of new rental housing developments (specifically 3 to 19 units) calculated per net rentable square foot. Revenues are segregated into a special fund to finance the acquisition, construction, and administration of affordable housing for extremely low- to moderate-income households. The mechanism is legally grounded in a Nexus Study linking new market-rate development to the creation of low-wage service jobs and the subsequent demand for affordable housing.
- key extracted points:
  - Direct Fiscal/Developer Fee Effects: Developers constructing new rental developments with 3 to 19 units are liable for a fee assessed per net rentable square foot. Following AB 1505 and Council action, rental developments with 20 or more units fall under the Inclusionary Housing Ordinance rather than this specific fee. Funds are held in a special revenue reserve (Multi-Source Housing Fund) and must be expended within five years of collection.
  - Indirect Household Cost-of-Living Pass-Through Effects: The policy rationale relies on a Nexus Study indicating that new market-rate residents increase demand for goods and services, generating service and retail jobs with wages too low to afford market rents. The AHIF revenue is used to subsidize the housing supply for these workers, theoretically stabilizing the cost of living for essential employees, though the specific pass-through rate to renters is not quantified in the text.
  - Numeric Parameters Identified: Applicability threshold is 3–19 apartment units; expenditure deadline is 5 years; reporting frequency is every 6 months; 2018 Notice of Funding Availability (NOFA) total is $100 million.
  - Secondary Evidence Required: The specific fee rate (dollar amount per net rentable square foot) is absent. Additionally, the complete Keyser Marston Associates (KMA) Nexus Study and the specific project details from Attachment A are required to perform a quantitative cost-benefit analysis or determine precise fiscal impacts.
- sufficiency: `Insufficient for quantitative conclusion. The evidence details the structure and legal framework but omits the specific fee rate ($/sq ft) and the detailed data from the Nexus Study necessary to calculate the magnitude of fiscal or economic impacts.`
- next tweak: Target commercial linkage fee resolution text with explicit dollar-per-square-foot query.

### Cycle 5

- hypothesis: A query containing Resolution 79705 and $/sq ft terms should extract direct fee parameters.
- windmill_job_id: `019d94f5-27d3-0de0-4f82-4d554d74234e`
- backend_run_id: `d611af15-4464-4eae-9e86-04b5dd438d27`
- package_id: `pkg-d90d67f6703d5e3d18593814`
- package_artifact: `minio://affordabot-artifacts/policy-evidence/packages/pkg-d90d67f6703d5e3d18593814.json`
- selected_url: https://sanjose.legistar.com/View.ashx?M=F&ID=8758120&GUID=6C299331-91E9-48ED-B7A5-43601D63FBF6
- reader_artifact: `minio://affordabot-artifacts/artifacts/2026-04-13.windmill-domain.v1/San Jose CA/meeting_minutes/reader_output/71524d4b161bbf71c6145f0549351b0c4a9603630c5e8e7794fb77c552468dd3.md`
- mechanism_family_hint: `fee_or_tax_pass_through`
- impact_mode_hint: `pass_through_incidence`
- secondary_research_needed: `True`
- storage_result: stored=`True`, artifact_write=`succeeded`, artifact_readback=`proven`, pgvector_truth_role=`derived_index`
- observed learning: Retrieved official San Jose resolution and extracted direct commercial linkage fee rates by use category; still correctly blocked indirect household pass-through.
- direct economic signal: Direct fee parameters found: e.g. office/retail/industrial/warehouse/hotel/residential-care rates and credits, with one OCR anomaly flagged.
- indirect economic signal: No pass-through incidence evidence in local legislative artifact.
- LLM summary: San José City Council resolution establishing Commercial Linkage Fee amounts for non-residential developments, with specific rates varying by land use category and square footage thresholds, and allowing credits for demolished existing non-residential space.
- key extracted points:
  - Source/Action: Adopted by City Council of San José (Resolution, Agenda Item 8.2(c)(2), September 1, 2020).
  - Affected Development: Non-Residential Projects and non-residential portions of mixed projects (Office, Retail, Hotel, Industrial/Research and Development, Warehouse, Residential Care).
  - Fee Rate - Office (<100,000 sq. ft.): $3.00 per sq. ft.
  - Fee Rate - Retail (≥100,000 sq. ft.): $3.00 per sq. ft.
  - Fee Rate - Retail (<100,000 sq. ft.): No fee ($0).
  - Fee Rate - Hotel: $5.00 per sq. ft.
  - Fee Rate - Industrial/Research and Development (≥100,000 sq. ft.): $3.00 per sq. ft.
  - Fee Rate - Industrial/Research and Development (<100,000 sq. ft.): No fee ($0).
- sufficiency: `Insufficient. Direct developer fee parameters (rates and types) are extracted, but the evidence is missing regarding indirect pass-through-to-households assumptions; failing closed on the incidence requirement.`
- next tweak: Run secondary economic literature search for incidence/pass-through evidence.

### Cycle 6

- hypothesis: Broad economic literature search should find incidence theory or empirical estimates.
- windmill_job_id: `019d94f9-c6fa-9aab-f6e7-eca32b5b951f`
- backend_run_id: `f917d334-9dbc-4628-a6de-13a298c46692`
- package_id: `pkg-6f4ae5c23acc5ad4a09b686c`
- package_artifact: `minio://affordabot-artifacts/policy-evidence/packages/pkg-6f4ae5c23acc5ad4a09b686c.json`
- selected_url: https://www.huduser.gov/periodicals/cityscpe/vol8num1/ch4.pdf
- reader_artifact: `minio://affordabot-artifacts/artifacts/2026-04-13.windmill-domain.v1/San Jose CA/economic_literature/reader_output/4dbf81f3a67ad8e4c8782b5ba6c2291992c16c2e0e480d1a78adaa441db8bd80.md`
- mechanism_family_hint: `fee_or_tax_pass_through`
- impact_mode_hint: `pass_through_incidence`
- secondary_research_needed: `True`
- storage_result: stored=`True`, artifact_write=`succeeded`, artifact_readback=`proven`, pgvector_truth_role=`derived_index`
- observed learning: Retrieved HUD literature review and extracted useful theory, but no decision-grade numeric incidence estimates; search result set contained more targeted papers not selected.
- direct economic signal: Not applicable; secondary research lane.
- indirect economic signal: Qualitative incidence theory found; numeric evidence insufficient.
- LLM summary: The provided text reviews theoretical frameworks and empirical literature regarding the impact and incidence of impact fees and linkage fees. Theoretically, in scenarios with fungible jurisdictions and widespread exaction, consumers are predicted to bear 'all or most' of the fee burden. The text summarizes empirical studies (e.g., Somerville and Mayer, Singell and Lillydahl) but describes their findings qualitatively (e.g., 'small effect,' 'large differential,' 'difficult to understand') rather than providing specific quantitative incidence estimates, pass-through rates, or numerical coefficients. Consequently, the text does not contain the quantitative empirical evidence required for a precise extraction of fee incidence.
- key extracted points:
  - Theoretical prediction: In a 'fungible jurisdiction, widespread exaction' scenario where the housing market is competitive and demand is elastic, the consumer pays 'all or most' of the impact fee because substitutes are unavailable.
  - Theoretical prediction: If consumers can reduce demand (e.g., doubling up), part of the fee may be passed back to landowners.
  - Somerville and Mayer (2002): Found that the presence of impact fees increased the probability that an affordable rental unit 'filters up' to become unaffordable, but the text only notes the effect is 'small' without providing specific magnitude or statistical values.
  - Singell and Lillydahl: Found a 'large differential' between price effects on new and existing housing, but the text states the magnitude is 'difficult to understand' and offers no quantitative pass-through estimates.
  - Delaney and Smith (1989a, 1989b): Noted for finding that the market took 6 years to adjust to price differentials, though specific incidence percentages are not provided.
  - General gap: The text indicates that whether fees have the same price effects on different housing types (e.g., multifamily vs. single-family) is 'not clear' and cites Mathur et al. (2004) as only beginning to address the issue.
- sufficiency: `No quantitative incidence estimates; secondary research still required.`
- next tweak: Target Ihlanfeldt/Shaughnessy or similar quantitative studies directly.

### Cycle 7

- hypothesis: Targeted Ihlanfeldt/Shaughnessy query should retrieve quantitative pass-through estimates.
- windmill_job_id: `019d94fb-dfaa-7681-7d6b-c1fb39f6ab49`
- backend_run_id: `e1826ad9-cda9-4737-9c1d-316852460029`
- package_id: `pkg-10adcd7b63e6262425240b5b`
- package_artifact: `minio://affordabot-artifacts/policy-evidence/packages/pkg-10adcd7b63e6262425240b5b.json`
- selected_url: https://www.huduser.gov/periodicals/cityscpe/vol8num1/ch4.pdf
- reader_artifact: `minio://affordabot-artifacts/artifacts/2026-04-13.windmill-domain.v1/San Jose CA/economic_literature/reader_output/4dbf81f3a67ad8e4c8782b5ba6c2291992c16c2e0e480d1a78adaa441db8bd80.md`
- mechanism_family_hint: `fee_or_tax_pass_through`
- impact_mode_hint: `pass_through_incidence`
- secondary_research_needed: `True`
- storage_result: stored=`True`, artifact_write=`succeeded`, artifact_readback=`proven`, pgvector_truth_role=`derived_index`
- observed learning: Still selected HUD review, but extracted embedded quantitative examples: 100% qualitative pass-through claim, Dunedin $1,150 fee -> $2,600 new-home price and $1,643 existing-home effect. LLM correctly refused San Jose decision-grade transfer.
- direct economic signal: Not applicable; secondary research lane.
- indirect economic signal: Quantitative examples found, but not transferable enough to San Jose without local elasticities/context.
- LLM summary: The evidence reviews theoretical and empirical studies on impact fee incidence. Ihlanfeldt and Shaughnessy (2004) provide qualitative estimates suggesting developers are fully compensated for fees through higher new home prices, and that new and existing home prices rise equally due to perceived property tax savings, a finding the text critiques as unrealistic. A separate study in Dunedin, Florida, provides quantitative data showing a $1,150 fee led to a $2,600 increase in new housing prices and a $1,643 increase in existing housing prices, though these effects were temporary, dissipating over six years.
- key extracted points:
  - Ihlanfeldt and Shaughnessy (2004) qualitative estimate: Developers fully compensated for fees via price increases (100% pass-through to new housing prices).
  - Ihlanfeldt and Shaughnessy (2004) qualitative estimate: Impact fees increase prices of new and existing homes by equal amounts.
  - Ihlanfeldt and Shaughnessy (2004) assumptions: No change in infrastructure quality for new homes; consumers value fee-financing as tax/risk reduction; willingness to pay based on future tax savings.
  - Dunedin, FL study (similar study) quantitative estimate: Fee amount of $1,150.
  - Dunedin, FL study quantitative estimate: New housing price increase of $2,600 (approx. 226% of fee).
  - Dunedin, FL study quantitative estimate: Existing housing price increase of $1,643 relative to control.
  - Dunedin, FL study geography: Dunedin and Clearwater, Florida.
  - Dunedin, FL study uncertainty/temporality: Price differentials lasted 6 years before market adjustments eliminated them.
- sufficiency: `Insufficient. The estimates cannot support a robust indirect pass-through cost-of-living analysis for San Jose. Ihlanfeldt and Shaughnessy lack specific quantitative fee amounts and rely on theoretical assumptions about property tax savings and risk reduction that the text identifies as unrealistic and potentially inapplicable to San Jose's market structure. The quantitative data from the Dunedin study is dated (1970s), specific to a Florida housing market with noted imperfections, and showed temporary effects. Neither study provides the local supply and demand elasticities or specific linkage fee contexts necessary for San Jose.`
- next tweak: Need structured/source-aware secondary research package and source ranking that can select primary empirical papers, then model assumption governance before decision-grade economic output.

## Architecture Implications

- Keep direct and indirect economic paths separate in the package contract. Direct fee/tax parameters can become quantitative earlier; indirect pass-through requires a secondary research package plus explicit assumption governance.
- Do not make the frontend or Windmill infer economics. Backend must own mechanism classification, parameter provenance, unsupported-claim rejection, and decision-grade readiness.
- Windmill should continue to orchestrate retries/fanout and persist run ids, while backend owns domain commands and package semantics.
- Next implementation should focus on unified package composition across scraped local artifacts, structured sources, and secondary literature, then feed the existing economic schemas/services instead of duplicating them.
