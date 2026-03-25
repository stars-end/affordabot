"""
Legislation Analysis Pipeline (bd-tytc.4).

Orchestrates multi-step legislation analysis using the shared
LegislationResearchService for retrieval-backed research.

Workflow:
1. Research: Retrieval-backed + web research via LegislationResearchService
2. Generate: LLM analysis with structured output (LegislationAnalysisResponse)
3. Review: LLM critique
4. Refine: Regenerate if review failed
"""

from __future__ import annotations

from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient
from llm_common.core.models import LLMMessage, MessageRole
from typing import List, Dict, Any, Optional
import re
import json
from pydantic import BaseModel, ValidationError
from schemas.analysis import (
    LegislationAnalysisResponse,
    ImpactEvidence,
    LegislationImpact,
    ReviewCritique,
    ScenarioBounds,
    SufficiencyState,
    SufficiencyBreakdown,
)
from datetime import datetime
import logging

from services.legislation_research import (
    LegislationResearchService,
    LegislationResearchResult,
)
from services.llm.evidence_adapter import envelope_to_impact_evidence
from services.llm.evidence_gates import (
    assess_sufficiency,
    strip_quantification,
    supports_quantified_evidence,
)

logger = logging.getLogger(__name__)

CANONICAL_PIPELINE_STEPS: List[str] = [
    "ingestion_source",
    "chunk_index",
    "research_discovery",
    "impact_discovery",
    "mode_selection",
    "parameter_resolution",
    "sufficiency_gate",
    "generate",
    "parameter_validation",
    "review",
    "refine",
    "persistence",
    "notify_debug",
]
STEP_INDEX = {name: i + 1 for i, name in enumerate(CANONICAL_PIPELINE_STEPS)}


class PrefixFixtureError(RuntimeError):
    """Raised when replay/fixture payloads are missing or invalid."""

EVIDENCE_BOILERPLATE_PATTERNS = (
    r"secretary of (the )?senate shall transmit",
    r"chief clerk of the assembly",
    r"chaptered copies",
    r"resolved, that the secretary",
)

EVIDENCE_STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "this",
    "with",
    "from",
    "into",
    "under",
    "would",
    "shall",
    "should",
    "about",
    "their",
    "there",
    "have",
    "has",
    "been",
    "will",
    "are",
    "was",
    "were",
    "than",
    "then",
    "when",
    "what",
    "where",
    "which",
    "while",
    "because",
    "without",
    "through",
}

RESIDENT_BURDEN_CLAIM_INDICATORS = (
    "cost of living",
    "tax burden",
    "taxpayer",
    "taxpayers",
    "household",
    "households",
    "resident",
    "residents",
    "public services",
    "service reductions",
)

RESIDENT_BURDEN_EVIDENCE_TERMS = (
    "tax",
    "taxpayer",
    "taxpayers",
    "household",
    "households",
    "resident",
    "residents",
    "ratepayer",
    "ratepayers",
    "fee",
    "fees",
    "price",
    "prices",
    "bill increase",
    "monthly bill",
    "public services",
    "service reduction",
    "service cuts",
)

NEGATED_RESIDENT_BURDEN_PATTERNS = (
    "no direct impact on the cost of living",
    "no direct cost-of-living impact",
    "no cost-of-living impact",
    "no provisions for taxation",
    "no taxes",
    "no fees",
    "no appropriations",
    "no mandates",
    "does not impose taxes",
    "does not impose fees",
    "does not impose mandates",
    "contains no provisions for taxation",
    "contains no provisions for fees",
    "contains no provisions for appropriations",
    "contains no provisions for regulatory mandates",
)

FISCAL_MISSING_IMPACT_TERMS = (
    "cost",
    "cost-of-living",
    "fiscal",
    "price",
    "prices",
    "rent",
    "rents",
    "tax",
    "taxes",
    "taxpayer",
    "taxpayers",
    "fee",
    "fees",
    "utility",
    "utilities",
    "reimbursement",
    "mandate",
    "appropriation",
    "budget",
    "spending",
    "expenditure",
    "expenditures",
    "funding",
    "labor",
    "training",
    "compliance",
    "administrative",
    "salary",
    "wage",
    "wages",
    "insurance",
    "housing",
    "transportation",
    "childcare",
    "food",
    "energy",
)


class AnalysisPipeline:
    """
    Orchestrate multi-step legislation analysis.

    Uses LegislationResearchService for retrieval-backed research
    with structured EvidenceEnvelope provenance (bd-tytc.4).
    """

    def __init__(
        self,
        llm_client: LLMClient,
        search_client: WebSearchClient,
        db_client: Any,
        fallback_client: LLMClient | None = None,
        retrieval_backend: Any = None,
        embedding_fn: Any = None,
    ):
        """
        Initialize pipeline.

        Args:
            llm_client: Primary LLM client (e.g. Z.ai)
            search_client: Web search client
            db_client: Database client
            fallback_client: Optional fallback/embedding provider (e.g. OpenRouter)
            retrieval_backend: Vector retrieval backend for RAG
            embedding_fn: Async function to embed text queries
        """
        self.llm = llm_client
        self.search = search_client
        self.db = db_client
        self.fallback_llm = fallback_client
        self.retrieval_backend = retrieval_backend
        self.embedding_fn = embedding_fn

        self.research_service = LegislationResearchService(
            llm_client=llm_client,
            search_client=search_client,
            retrieval_backend=retrieval_backend,
            embedding_fn=embedding_fn,
            db_client=db_client,
        )

    async def run(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        models: Dict[str, str],
        trigger_source: str = "manual",
        start_at_step: int = 1,
        stop_after_step: Optional[int] = None,
        reuse_prior_step_outputs: Optional[str] = None,
        fixture_mode: Optional[str] = None,
        run_label: Optional[str] = None,
    ) -> LegislationAnalysisResponse:
        """
        Run full pipeline.

        Args:
            bill_id: Bill identifier (e.g., "SB-277")
            bill_text: Full bill text
            jurisdiction: Jurisdiction (e.g., "California")
            models: {"research": "...", "generate": "...", "review": "..."}
            trigger_source: "manual" or "windmill"

        Returns:
            Final analysis (validated LegislationAnalysisResponse)
        """
        from services.audit.logger import AuditLogger

        if start_at_step < 1 or start_at_step > len(CANONICAL_PIPELINE_STEPS):
            raise PrefixFixtureError(f"fixture_invalid: start_at_step={start_at_step}")
        if stop_after_step is not None and (
            stop_after_step < 1 or stop_after_step > len(CANONICAL_PIPELINE_STEPS)
        ):
            raise PrefixFixtureError(
                f"fixture_invalid: stop_after_step={stop_after_step}"
            )
        if stop_after_step is not None and stop_after_step < start_at_step:
            raise PrefixFixtureError(
                "fixture_invalid: stop_after_step must be >= start_at_step"
            )
        trigger_with_label = trigger_source
        if run_label:
            trigger_with_label = f"prefix:{run_label}"

        run_id = await self._create_pipeline_run(
            bill_id, jurisdiction, models, trigger_with_label
        )
        audit = AuditLogger(run_id, self.db)

        try:
            replay_outputs = await self._load_prefix_seed_outputs(
                reuse_prior_step_outputs=reuse_prior_step_outputs,
                fixture_mode=fixture_mode,
                start_at_step=start_at_step,
            )
            if start_at_step > 1 and not replay_outputs:
                raise PrefixFixtureError(
                    "fixture_invalid: start_at_step > 1 requires reuse_prior_step_outputs or fixture_mode"
                )

            def _seeded(step_name: str) -> Optional[Dict[str, Any]]:
                value = replay_outputs.get(step_name)
                if value is None:
                    return None
                if not isinstance(value, dict):
                    raise PrefixFixtureError(
                        f"fixture_invalid: payload for {step_name} must be object"
                    )
                return value

            async def _checkpoint(step_name: str, output_result: Dict[str, Any], status: str = "completed", input_context: Optional[Dict[str, Any]] = None, model_info: Optional[Dict[str, Any]] = None) -> bool:
                await audit.log_step(
                    step_number=STEP_INDEX[step_name],
                    step_name=step_name,
                    status=status,
                    input_context=input_context or {},
                    output_result=output_result,
                    model_info=model_info or {},
                    duration_ms=0,
                )
                if stop_after_step is not None and STEP_INDEX[step_name] >= stop_after_step:
                    await self._complete_pipeline_run(
                        run_id,
                        bill_id,
                        bill_text,
                        self._empty_analysis(
                            bill_id=bill_id,
                            jurisdiction=jurisdiction,
                            model_used=models.get("generate", "unknown"),
                        ),
                        ReviewCritique(
                            passed=False,
                            critique=f"Prefix run halted after step {step_name}",
                            missing_impacts=[],
                            factual_errors=[],
                        ),
                        jurisdiction,
                        run_status="prefix_halted",
                    )
                    await self._emit_slack_summary(
                        run_id,
                        bill_id,
                        jurisdiction,
                        "prefix_halted",
                        trigger_with_label,
                    )
                    return True
                return False

            source_data = await self.db.get_latest_scrape_for_bill(
                jurisdiction, bill_id
            )
            source_text_present = bool(bill_text and len(bill_text) > 100)
            ingestion_output = _seeded("ingestion_source")
            if STEP_INDEX["ingestion_source"] < start_at_step:
                if ingestion_output is None:
                    raise PrefixFixtureError("fixture_invalid: missing seeded ingestion_source")
                halted = await _checkpoint(
                    "ingestion_source",
                    ingestion_output,
                    status="replayed",
                    input_context={"mode": "replay"},
                    model_info={"model": "deterministic"},
                )
                if halted:
                    return self._empty_analysis(
                        bill_id=bill_id,
                        jurisdiction=jurisdiction,
                        model_used=models.get("generate", "unknown"),
                    )
            else:
                if source_data:
                    ingestion_output = {
                        "raw_scrape_id": str(source_data["id"]),
                        "source_url": source_data["url"],
                        "content_hash": source_data["content_hash"],
                        "metadata": source_data["metadata"],
                        "minio_blob_path": source_data.get("storage_uri", "N/A"),
                        "source_text_present": source_text_present,
                    }
                    halted = await _checkpoint(
                        "ingestion_source",
                        ingestion_output,
                        status="completed",
                        input_context={
                            "jurisdiction": jurisdiction,
                            "bill_id": bill_id,
                            "bill_text_preview": bill_text[:500] + "..."
                            if bill_text
                            else "N/A",
                        },
                        model_info={"model": "scraper", "provider": "firecrawl"},
                    )
                else:
                    ingestion_output = {
                        "error": "No raw scrape found for this bill.",
                        "source_text_present": source_text_present,
                    }
                    halted = await _checkpoint(
                        "ingestion_source",
                        ingestion_output,
                        status="skipped",
                        input_context={"jurisdiction": jurisdiction, "bill_id": bill_id},
                        model_info={"model": "scraper", "provider": "firecrawl"},
                    )
                if halted:
                    return self._empty_analysis(
                        bill_id=bill_id,
                        jurisdiction=jurisdiction,
                        model_used=models.get("generate", "unknown"),
                    )

            chunk_output = _seeded("chunk_index")
            if STEP_INDEX["chunk_index"] < start_at_step:
                if chunk_output is None:
                    raise PrefixFixtureError("fixture_invalid: missing seeded chunk_index")
                halted = await _checkpoint(
                    "chunk_index",
                    chunk_output,
                    status="replayed",
                    input_context={"mode": "replay"},
                    model_info={"model": "deterministic"},
                )
                if halted:
                    return self._empty_analysis(
                        bill_id=bill_id,
                        jurisdiction=jurisdiction,
                        model_used=models.get("generate", "unknown"),
                    )
            else:
                chunk_count = 0
                if source_data and hasattr(self.db, "get_vector_stats"):
                    vector_stats = await self.db.get_vector_stats(
                        source_data.get("document_id")
                    )
                    if vector_stats:
                        chunk_count = int(vector_stats.get("chunk_count", 0))
                chunk_output = {
                    "document_id": source_data.get("document_id") if source_data else None,
                    "chunk_count": chunk_count,
                    "provenance_compatible": bool(chunk_count >= 0),
                }
                halted = await _checkpoint(
                    "chunk_index",
                    chunk_output,
                    status="completed",
                    input_context={"bill_id": bill_id, "jurisdiction": jurisdiction},
                    model_info={"model": "deterministic", "provider": "postgres"},
                )
                if halted:
                    return self._empty_analysis(
                        bill_id=bill_id,
                        jurisdiction=jurisdiction,
                        model_used=models.get("generate", "unknown"),
                    )

            start_ts = datetime.now()
            research_result = await self._research_step(
                bill_id, bill_text, jurisdiction, models["research"]
            )
            duration = int((datetime.now() - start_ts).total_seconds() * 1000)
            wave2_prerequisites = self._serialize_wave2_prerequisites(
                getattr(research_result, "wave2_prerequisites", {}) or {}
            )
            research_output = {
                "rag_chunks": len(research_result.rag_chunks),
                "web_sources": len(research_result.web_sources),
                "evidence_envelopes": len(research_result.evidence_envelopes),
                "evidence_details": self._serialize_evidence_envelopes(
                    research_result
                ),
                "wave2_prerequisites": wave2_prerequisites,
                "sufficiency_breakdown": research_result.sufficiency_breakdown,
                "is_sufficient": research_result.is_sufficient,
                "insufficiency_reason": research_result.insufficiency_reason,
            }
            halted = await _checkpoint(
                "research_discovery",
                research_output,
                status="completed" if research_result.is_sufficient else "degraded",
                input_context={"bill_id": bill_id, "jurisdiction": jurisdiction},
                model_info={"model": models["research"], "duration_ms": duration},
            )
            if halted:
                return self._empty_analysis(
                    bill_id=bill_id,
                    jurisdiction=jurisdiction,
                    model_used=models.get("generate", "unknown"),
                )

            discovered_impacts = research_result.impact_candidates or []
            impact_discovery_output = {
                "impacts": discovered_impacts,
                "wave2_prerequisites": {
                    "impact_candidates": wave2_prerequisites.get("impact_candidates", []),
                    "parameter_candidates": wave2_prerequisites.get(
                        "parameter_candidates", {}
                    ),
                },
            }
            halted = await _checkpoint(
                "impact_discovery",
                impact_discovery_output,
                status="completed" if discovered_impacts else "failed",
                input_context={"bill_id": bill_id},
                model_info={"model": models.get("research", "unknown")},
            )
            if halted:
                return self._empty_analysis(
                    bill_id=bill_id,
                    jurisdiction=jurisdiction,
                    model_used=models.get("generate", "unknown"),
                )

            mode_decisions = [
                self._build_mode_selection_output(impact)
                for impact in discovered_impacts
            ]
            first_mode = (
                mode_decisions[0]
                if mode_decisions
                else self._build_mode_selection_output({})
            )
            mode_selection_output = {
                **first_mode,
                "impact_modes": mode_decisions,
            }
            self._validate_deterministic_step_payload("mode_selection", mode_selection_output)
            halted = await _checkpoint(
                "mode_selection",
                mode_selection_output,
                status="completed",
                input_context={"impact_count": len(discovered_impacts)},
                model_info={"model": "deterministic"},
            )
            if halted:
                return self._empty_analysis(
                    bill_id=bill_id,
                    jurisdiction=jurisdiction,
                    model_used=models.get("generate", "unknown"),
                )

            parameter_resolutions = [
                self._build_parameter_resolution_output(
                    impact_id=impact.get("impact_id", f"impact-{idx + 1}"),
                    selected_mode=decision["selected_mode"],
                    parameter_candidates=research_result.parameter_candidates.get(
                        impact.get("impact_id", f"impact-{idx + 1}"), {}
                    ),
                )
                for idx, (impact, decision) in enumerate(
                    zip(discovered_impacts, mode_decisions)
                )
            ]
            first_resolution = (
                parameter_resolutions[0]
                if parameter_resolutions
                else self._build_parameter_resolution_output(
                    impact_id="impact-1",
                    selected_mode="qualitative_only",
                    parameter_candidates={},
                )
            )
            parameter_resolution_output = {
                **first_resolution,
                "impact_parameters": parameter_resolutions,
                "wave2_parameter_candidates": wave2_prerequisites.get(
                    "parameter_candidates", {}
                ),
            }
            self._validate_deterministic_step_payload(
                "parameter_resolution", parameter_resolution_output
            )
            halted = await _checkpoint(
                "parameter_resolution",
                parameter_resolution_output,
                status="completed",
                input_context={"selected_mode": first_mode["selected_mode"]},
                model_info={"model": "deterministic"},
            )
            if halted:
                return self._empty_analysis(
                    bill_id=bill_id,
                    jurisdiction=jurisdiction,
                    model_used=models.get("generate", "unknown"),
                )

            evidence_items = []
            for envelope in research_result.evidence_envelopes:
                envelope_data = (
                    envelope.model_dump()
                    if hasattr(envelope, "model_dump")
                    else envelope
                )
                evidence_items.extend(envelope_to_impact_evidence(envelope_data))

            candidate_impacts = [
                {
                    "impact_id": impact.get("impact_id", f"impact-{idx + 1}"),
                    "selected_mode": decision["selected_mode"],
                    "parameter_resolution": resolution,
                    "parameter_validation": self._build_parameter_validation_output(
                        resolution,
                        eligible_for_quant=True,
                    ),
                }
                for idx, (impact, decision, resolution) in enumerate(
                    zip(discovered_impacts, mode_decisions, parameter_resolutions)
                )
            ]
            breakdown = assess_sufficiency(
                bill_text=bill_text,
                evidence_list=evidence_items,
                candidate_impacts=candidate_impacts,
                rag_chunks_retrieved=len(research_result.rag_chunks),
                web_research_count=len(research_result.web_sources),
            )
            impact_gate_summaries = [
                gate_summary.model_dump(mode="json")
                for gate_summary in breakdown.impact_gate_summaries
            ]
            sufficiency_output = {
                "overall_quantification_eligible": breakdown.overall_quantification_eligible,
                "overall_sufficiency_state": breakdown.overall_sufficiency_state.value,
                "impact_gate_summaries": impact_gate_summaries,
                "bill_level_failures": [
                    failure.value for failure in breakdown.bill_level_failures
                ],
            }
            halted = await _checkpoint(
                "sufficiency_gate",
                sufficiency_output,
                status="completed",
                input_context={"bill_id": bill_id},
                model_info={"model": "deterministic", "provider": "evidence_gates"},
            )
            if halted:
                return self._empty_analysis(
                    bill_id=bill_id,
                    jurisdiction=jurisdiction,
                    model_used=models.get("generate", "unknown"),
                )

            if breakdown.overall_sufficiency_state == SufficiencyState.RESEARCH_INCOMPLETE:
                analysis = LegislationAnalysisResponse(
                    bill_number=bill_id,
                    title="",
                    jurisdiction=jurisdiction,
                    status="",
                    sufficiency_state=breakdown.overall_sufficiency_state,
                    insufficiency_reason=self._breakdown_reason(breakdown),
                    quantification_eligible=False,
                    impacts=[],
                    aggregate_scenario_bounds=None,
                    analysis_timestamp=datetime.now().isoformat(),
                    model_used=models.get("generate", "unknown"),
                )
                await self._complete_pipeline_run(
                    run_id,
                    bill_id,
                    bill_text,
                    analysis,
                    ReviewCritique(
                        passed=False,
                        critique="Skipped: research incomplete",
                        missing_impacts=[],
                        factual_errors=[],
                    ),
                    jurisdiction,
                    breakdown=breakdown,
                    rag_chunks_retrieved=len(research_result.rag_chunks),
                    retriever_invoked=research_result.retriever_invoked,
                )
                return analysis

            if (
                not discovered_impacts
                and breakdown.overall_sufficiency_state == SufficiencyState.QUALITATIVE_ONLY
            ):
                analysis = LegislationAnalysisResponse(
                    bill_number=bill_id,
                    title="",
                    jurisdiction=jurisdiction,
                    status="",
                    sufficiency_state=breakdown.overall_sufficiency_state,
                    insufficiency_reason=self._breakdown_reason(breakdown),
                    quantification_eligible=False,
                    impacts=[],
                    aggregate_scenario_bounds=None,
                    analysis_timestamp=datetime.now().isoformat(),
                    model_used=models.get("generate", "unknown"),
                )

                skipped_reason = "no_impacts_discovered_fail_closed"
                for step_name in ("generate", "parameter_validation", "review", "refine"):
                    halted = await _checkpoint(
                        step_name,
                        {"skipped": True, "reason": skipped_reason},
                        status="skipped",
                        input_context={"bill_id": bill_id},
                        model_info={"model": "deterministic"},
                    )
                    if halted:
                        return analysis

                persistence = await self._complete_pipeline_run(
                    run_id,
                    bill_id,
                    bill_text,
                    analysis,
                    ReviewCritique(
                        passed=False,
                        critique="Skipped: no impacts discovered",
                        missing_impacts=[],
                        factual_errors=[],
                    ),
                    jurisdiction,
                    breakdown=breakdown,
                    rag_chunks_retrieved=len(research_result.rag_chunks),
                    retriever_invoked=research_result.retriever_invoked,
                )

                halted = await _checkpoint(
                    "persistence",
                    {
                        "legislation_id": persistence.get("legislation_id"),
                        "analysis_stored": persistence.get("analysis_stored", False),
                        "impacts_count": persistence.get("impacts_count", 0),
                        "sufficiency_state": analysis.sufficiency_state.value
                        if analysis.sufficiency_state
                        else None,
                        "quantification_eligible": analysis.quantification_eligible,
                        "aggregate_scenario_bounds": None,
                    },
                    status="completed" if persistence.get("analysis_stored") else "failed",
                    input_context={"bill_id": bill_id, "jurisdiction": jurisdiction},
                    model_info={"model": "deterministic", "provider": "postgres"},
                )
                if halted:
                    return analysis

                notify_output = {
                    "status": "emitted" if trigger_source == "manual" else "skipped",
                    "prefix_boundary": f"stopped_after_step_{stop_after_step}"
                    if stop_after_step is not None
                    else None,
                }
                halted = await _checkpoint(
                    "notify_debug",
                    notify_output,
                    status="completed",
                    input_context={"trigger_source": trigger_with_label},
                    model_info={"model": "deterministic"},
                )
                if halted:
                    return analysis

                await self._emit_slack_summary(
                    run_id,
                    bill_id,
                    jurisdiction,
                    "completed",
                    trigger_with_label,
                    analysis,
                )

                return analysis

            start_ts = datetime.now()
            analysis = await self._generate_step(
                bill_id,
                bill_text,
                jurisdiction,
                research_result,
                models["generate"],
                breakdown,
            )
            self._hydrate_analysis_evidence_from_research(analysis, research_result)
            duration = int((datetime.now() - start_ts).total_seconds() * 1000)
            analysis = self._apply_wave1_quantification(
                analysis=analysis,
                impact_candidates=discovered_impacts,
                mode_decisions=mode_decisions,
                parameter_resolutions=parameter_resolutions,
                breakdown=breakdown,
            )

            if not breakdown.overall_quantification_eligible:
                analysis.impacts = [
                    LegislationImpact(**strip_quantification([imp.model_dump()])[0])
                    for imp in analysis.impacts
                ]
                analysis.sufficiency_state = breakdown.overall_sufficiency_state
                analysis.insufficiency_reason = self._breakdown_reason(breakdown)
                analysis.quantification_eligible = False
                analysis.aggregate_scenario_bounds = None
            else:
                analysis.quantification_eligible = True

            analysis.bill_number = bill_id
            analysis.jurisdiction = jurisdiction
            analysis.model_used = models["generate"]
            analysis.analysis_timestamp = datetime.now().isoformat()

            halted = await _checkpoint(
                "generate",
                analysis.model_dump(),
                status="completed",
                input_context={
                    "evidence_envelope_count": len(research_result.evidence_envelopes),
                    "is_sufficient": research_result.is_sufficient,
                    "sufficiency_state": breakdown.overall_sufficiency_state.value,
                },
                model_info={"model": models["generate"], "duration_ms": duration},
            )
            if halted:
                return analysis

            impact_validations = [
                self._build_parameter_validation_output(
                    resolution,
                    eligible_for_quant=gate.quantification_eligible,
                )
                for resolution, gate in zip(
                    parameter_resolutions, breakdown.impact_gate_summaries
                )
            ]
            first_validation = (
                impact_validations[0]
                if impact_validations
                else self._build_parameter_validation_output(
                    self._build_parameter_resolution_output(
                        impact_id="impact-1",
                        selected_mode="qualitative_only",
                        parameter_candidates={},
                    ),
                    eligible_for_quant=False,
                )
            )
            parameter_validation_output = {
                **first_validation,
                "impact_validations": impact_validations,
            }
            self._validate_deterministic_step_payload(
                "parameter_validation", parameter_validation_output
            )
            halted = await _checkpoint(
                "parameter_validation",
                parameter_validation_output,
                status="completed",
                input_context={"bill_id": bill_id},
                model_info={"model": "deterministic"},
            )
            if halted:
                return analysis

            start_ts = datetime.now()
            review = await self._review_step(
                bill_id, analysis, research_result, models["review"]
            )
            review = self._normalize_review(review, analysis)
            duration = int((datetime.now() - start_ts).total_seconds() * 1000)

            halted = await _checkpoint(
                "review",
                review.model_dump(),
                status="completed",
                input_context={"analysis_summary": "See generate step"},
                model_info={"model": models["review"], "duration_ms": duration},
            )
            if halted:
                return analysis

            if not review.passed:
                start_ts = datetime.now()
                analysis = await self._refine_step(
                    bill_id,
                    analysis,
                    review,
                    bill_text,
                    models["generate"],
                    breakdown,
                )
                self._hydrate_analysis_evidence_from_research(analysis, research_result)
                duration = int((datetime.now() - start_ts).total_seconds() * 1000)
                analysis = self._apply_wave1_quantification(
                    analysis=analysis,
                    impact_candidates=discovered_impacts,
                    mode_decisions=mode_decisions,
                    parameter_resolutions=parameter_resolutions,
                    breakdown=breakdown,
                )

                if not breakdown.overall_quantification_eligible:
                    analysis.impacts = [
                        LegislationImpact(**strip_quantification([imp.model_dump()])[0])
                        for imp in analysis.impacts
                    ]
                    analysis.sufficiency_state = breakdown.overall_sufficiency_state
                    analysis.insufficiency_reason = self._breakdown_reason(breakdown)
                    analysis.quantification_eligible = False
                    analysis.aggregate_scenario_bounds = None
                else:
                    analysis.quantification_eligible = True

                analysis.bill_number = bill_id
                analysis.jurisdiction = jurisdiction
                analysis.model_used = models["generate"]
                analysis.analysis_timestamp = datetime.now().isoformat()

                review = await self._review_step(
                    bill_id, analysis, research_result, models["review"]
                )
                review = self._normalize_review(review, analysis)

                halted = await _checkpoint(
                    "refine",
                    analysis.model_dump(),
                    status="completed",
                    input_context={"critique": review.model_dump()},
                    model_info={"model": models["generate"], "duration_ms": duration},
                )
                if halted:
                    return analysis
            else:
                halted = await _checkpoint(
                    "refine",
                    {"skipped": True, "reason": "review_passed"},
                    status="skipped",
                    input_context={"bill_id": bill_id},
                    model_info={"model": "deterministic"},
                )
                if halted:
                    return analysis

            persistence = await self._complete_pipeline_run(
                run_id,
                bill_id,
                bill_text,
                analysis,
                review,
                jurisdiction,
                breakdown=breakdown,
                rag_chunks_retrieved=len(research_result.rag_chunks),
                retriever_invoked=research_result.retriever_invoked,
            )

            halted = await _checkpoint(
                "persistence",
                {
                    "legislation_id": persistence.get("legislation_id"),
                    "analysis_stored": persistence.get("analysis_stored", False),
                    "impacts_count": persistence.get("impacts_count", 0),
                    "sufficiency_state": analysis.sufficiency_state.value
                    if analysis.sufficiency_state
                    else None,
                    "quantification_eligible": analysis.quantification_eligible,
                    "aggregate_scenario_bounds": analysis.aggregate_scenario_bounds.model_dump()
                    if analysis.aggregate_scenario_bounds
                    else None,
                },
                status="completed" if persistence.get("analysis_stored") else "failed",
                input_context={"bill_id": bill_id, "jurisdiction": jurisdiction},
                model_info={"model": "deterministic", "provider": "postgres"},
            )
            if halted:
                return analysis

            notify_output = {
                "status": "emitted" if trigger_source == "manual" else "skipped",
                "prefix_boundary": f"stopped_after_step_{stop_after_step}"
                if stop_after_step is not None
                else None,
            }
            halted = await _checkpoint(
                "notify_debug",
                notify_output,
                status="completed",
                input_context={"trigger_source": trigger_with_label},
                model_info={"model": "deterministic"},
            )
            if halted:
                return analysis

            await self._emit_slack_summary(
                run_id,
                bill_id,
                jurisdiction,
                "completed",
                trigger_with_label,
                analysis,
            )

            return analysis

        except PrefixFixtureError as e:
            await self._fail_pipeline_run(run_id, str(e), status="fixture_invalid")
            await audit.log_step(
                step_number=STEP_INDEX["notify_debug"],
                step_name="notify_debug",
                status="failed",
                output_result={"error": str(e), "failure_code": "fixture_invalid"},
                model_info={"model": "deterministic"},
            )
            await self._emit_slack_summary(
                run_id,
                bill_id,
                jurisdiction,
                "fixture_invalid",
                trigger_with_label,
                error=str(e),
            )
            raise
        except Exception as e:
            await self._fail_pipeline_run(run_id, str(e), status="failed")
            await audit.log_step(
                step_number=STEP_INDEX["notify_debug"],
                step_name="notify_debug",
                status="failed",
                output_result={"error": str(e)},
                model_info={"models_attempted": models},
            )
            await self._emit_slack_summary(
                run_id,
                bill_id,
                jurisdiction,
                "failed",
                trigger_with_label,
                error=str(e),
            )
            raise

    async def _research_step(
        self, bill_id: str, bill_text: str, jurisdiction: str, model: str
    ) -> LegislationResearchResult:
        """
        Research step using LegislationResearchService (bd-tytc.4).

        Replaces generic ResearchAgent with retrieval-backed research
        that returns structured EvidenceEnvelope provenance.
        """
        result = await self.research_service.research(
            bill_id=bill_id,
            bill_text=bill_text,
            jurisdiction=jurisdiction,
            top_k=10,
            min_score=0.5,
        )

        if not result.is_sufficient:
            logger.warning(
                f"Research insufficient for {bill_id}: {result.insufficiency_reason}"
            )

        return result

    async def _chat(
        self, messages: List[Dict], model: str, response_model: type[BaseModel]
    ) -> BaseModel:
        """Helper to get structured output from LLMClient."""
        llm_messages = []
        for m in messages:
            role = MessageRole.USER if m["role"] == "user" else MessageRole.SYSTEM
            llm_messages.append(LLMMessage(role=role, content=m["content"]))

        schema = response_model.model_json_schema()
        json_instruction = (
            f"\n\nRespond with valid JSON matching this schema:\n{schema}"
        )
        if llm_messages:
            llm_messages[-1].content += json_instruction

        def _normalize_json_text(text: str) -> str:
            content = text.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content
                if content.endswith("```"):
                    content = content[:-3].strip()
                if content.startswith("json"):
                    content = content[4:].strip()
            return content

        def _extract_bill_number() -> str | None:
            combined = "\n".join(str(m.content) for m in llm_messages)
            match = re.search(r"(?m)^\\s*Bill:\\s*([^\\s\\(]+)", combined)
            return match.group(1) if match else None

        async def _call_llm(
            call_messages: list[LLMMessage], *, temperature: float
        ) -> str:
            try:
                response = await self.llm.chat_completion(
                    messages=call_messages,
                    model=model,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                )
                return _normalize_json_text(response.content)
            except Exception as e:
                if not self.fallback_llm:
                    raise
                print(f"Primary LLM failed: {e}. Retrying with Fallback LLM...")
                fallback_model = (
                    self.fallback_llm.config.default_model
                    or "google/gemini-2.0-flash-exp"
                )
                response = await self.fallback_llm.chat_completion(
                    messages=call_messages,
                    model=fallback_model,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                )
                return _normalize_json_text(response.content)

        content = await _call_llm(llm_messages, temperature=0.1)
        last_error = ""
        try:
            return response_model.model_validate_json(content)
        except Exception as e:
            last_error = str(e)

        for _attempt in range(2):
            repair_prompt = (
                "Your previous response did not validate against the required JSON schema.\n"
                "Return ONLY valid JSON that matches the schema exactly (all required fields present; correct types; no extra keys).\n\n"
                f"Schema:\n{schema}\n\n"
                f"Validation error:\n{last_error}\n\n"
                "Previous response:\n"
                f"{content}\n"
            )
            repair_messages = list(llm_messages)
            repair_messages.append(
                LLMMessage(role=MessageRole.ASSISTANT, content=content)
            )
            repair_messages.append(
                LLMMessage(role=MessageRole.USER, content=repair_prompt)
            )

            content = await _call_llm(repair_messages, temperature=0.0)
            try:
                return response_model.model_validate_json(content)
            except Exception as e:
                last_error = str(e)

        if response_model is LegislationAnalysisResponse:
            return LegislationAnalysisResponse(
                bill_number=_extract_bill_number() or "UNKNOWN",
                sufficiency_state=SufficiencyState.INSUFFICIENT_EVIDENCE,
                quantification_eligible=False,
                impacts=[],
                aggregate_scenario_bounds=None,
                analysis_timestamp=datetime.now().isoformat(),
                model_used=model,
            )
        if response_model is ReviewCritique:
            return ReviewCritique(
                passed=False,
                critique=f"LLM output did not match schema after retries: {last_error}",
                missing_impacts=[],
                factual_errors=[last_error[:500]],
            )
        raise ValidationError(
            f"LLM output did not match schema after retries: {last_error}",
            response_model,
        )  # type: ignore[arg-type]

    async def _generate_step(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        research_result: LegislationResearchResult,
        model: str,
        breakdown: Any = None,
    ) -> LegislationAnalysisResponse:
        """
        Generate analysis using LLM with structured evidence.
        """
        evidence_context = self._format_evidence_for_generation(research_result)

        sufficiency_note = ""
        if not research_result.is_sufficient:
            sufficiency_note = f"""
IMPORTANT: Research insufficiency detected: {research_result.insufficiency_reason}

Your analysis should acknowledge data gaps. If evidence is insufficient for 
quantification, provide qualitative analysis only.
"""
        if breakdown and not breakdown.overall_quantification_eligible:
            sufficiency_note += (
                "\nIMPORTANT: Quantification is NOT permitted for this bill. "
                "Do not emit scenario bounds or modeled quantitative fields. "
                f"Reason: {self._breakdown_reason(breakdown)}\n"
            )

        system_prompt = f"""
You are an expert policy analyst. Analyze legislation for cost-of-living impacts.

{sufficiency_note}

Use the provided research data to support your analysis.
Base your estimates only on the evidence provided.
Be conservative and evidence-based.
Cite sources when making claims. For each impact, include at least one evidence
excerpt that directly supports the impact_description and legal_interpretation.
Do not mention institutions, legal effects, appropriations, or program details
unless those details are directly visible in the cited excerpt(s).
"""

        user_message = f"""
Bill: {bill_id} ({jurisdiction})

Research Evidence:
{evidence_context}

Bill Text:
{bill_text[:5000]}
"""

        result = await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model=model,
            response_model=LegislationAnalysisResponse,
        )
        return result  # type: ignore[return-value]

    def _format_evidence_for_generation(
        self, research_result: LegislationResearchResult
    ) -> str:
        """Format research evidence for generation prompt."""
        parts = []

        parts.append(
            f"Research Sufficiency: {'Sufficient' if research_result.is_sufficient else 'Insufficient'}"
        )
        parts.append(f"RAG Chunks Retrieved: {len(research_result.rag_chunks)}")
        parts.append(f"Web Sources Found: {len(research_result.web_sources)}")
        parts.append("")

        if research_result.rag_chunks:
            parts.append("=== Internal Documents (RAG) ===")
            for i, chunk in enumerate(research_result.rag_chunks[:5], 1):
                source = (
                    chunk.metadata.get("source_url")
                    or chunk.metadata.get("source_id")
                    or "unknown"
                )
                parts.append(f"[{i}] (Source: {source}, Score: {chunk.score:.2f})")
                parts.append(chunk.content[:500])
                parts.append("")

        curated_evidence = []
        for envelope in research_result.evidence_envelopes:
            for evidence in getattr(envelope, "evidence", []) or []:
                excerpt = getattr(evidence, "excerpt", "") or ""
                if not excerpt:
                    continue
                curated_evidence.append(
                    {
                        "label": getattr(evidence, "label", "Evidence"),
                        "url": getattr(evidence, "url", "") or "",
                        "excerpt": excerpt,
                    }
                )
        if curated_evidence:
            parts.append("=== Curated Evidence Excerpts ===")
            for i, item in enumerate(curated_evidence[:15], 1):
                parts.append(f"[E{i}] {item['label']}")
                parts.append(f"URL: {item['url']}")
                parts.append(f"Excerpt: {item['excerpt'][:700]}")
                parts.append("")

        if research_result.web_sources:
            parts.append("=== Web Research ===")
            for i, source in enumerate(research_result.web_sources[:10], 1):
                title = source.get("title", "Untitled")
                url = source.get("url") or source.get("link", "")
                snippet = source.get("snippet", "")[:300]
                parts.append(f"[{i}] {title}")
                parts.append(f"URL: {url}")
                parts.append(f"Snippet: {snippet}")
                parts.append("")

        return "\n".join(parts)

    async def _review_step(
        self,
        bill_id: str,
        analysis: LegislationAnalysisResponse,
        research_result: LegislationResearchResult,
        model: str,
    ) -> ReviewCritique:
        """Review analysis using LLM."""
        system_prompt = "You are a senior policy reviewer. Critique the following analysis for accuracy, evidence, and conservatism."

        evidence_summary = f"RAG chunks: {len(research_result.rag_chunks)}, Web sources: {len(research_result.web_sources)}, Sufficient: {research_result.is_sufficient}"
        evidence_context = self._format_evidence_for_generation(research_result)

        user_message = f"""
Bill: {bill_id}
Analysis: {analysis.model_dump_json()}
Evidence Summary: {evidence_summary}
Evidence Excerpts:
{evidence_context}
"""

        result = await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model=model,
            response_model=ReviewCritique,
        )
        return result  # type: ignore[return-value]

    def _hydrate_analysis_evidence_from_research(
        self,
        analysis: LegislationAnalysisResponse,
        research_result: LegislationResearchResult,
    ) -> None:
        """Replace weak generated excerpts with stronger provenance excerpts."""
        evidence_by_url: Dict[str, Dict[str, str]] = {}
        evidence_candidates: List[Dict[str, str]] = []
        for envelope in research_result.evidence_envelopes:
            for evidence in getattr(envelope, "evidence", []) or []:
                url = (getattr(evidence, "url", "") or "").strip()
                excerpt = (getattr(evidence, "excerpt", "") or "").strip()
                evidence_id = (getattr(evidence, "id", "") or "").strip()
                evidence_kind = (getattr(evidence, "kind", "") or "").strip()
                source_name = (
                    getattr(evidence, "label", "")
                    or getattr(evidence, "source_name", "")
                    or ""
                ).strip()
                if not excerpt:
                    continue
                candidate = {
                    "url": url,
                    "excerpt": excerpt,
                    "id": evidence_id,
                    "kind": evidence_kind,
                    "source_name": source_name,
                }
                evidence_candidates.append(candidate)
                key = url.lower()
                if key:
                    existing = evidence_by_url.get(key)
                    if not existing or len(excerpt) > len(existing.get("excerpt", "")):
                        evidence_by_url[key] = candidate

        for impact in analysis.impacts:
            for ev in impact.evidence:
                candidate = self._match_research_evidence_candidate(
                    impact,
                    ev,
                    evidence_by_url,
                    evidence_candidates,
                )
                if not candidate:
                    continue
                if self._is_weak_excerpt(ev.excerpt):
                    ev.excerpt = candidate["excerpt"]
                if not ev.url and candidate.get("url"):
                    ev.url = candidate["url"]
                if (
                    not ev.source_name
                    or ev.source_name.strip().lower() == "curated evidence excerpts"
                ) and candidate.get("source_name"):
                    ev.source_name = candidate["source_name"]
                if not ev.persisted_evidence_id and candidate.get("id"):
                    ev.persisted_evidence_id = candidate["id"]
                if not ev.persisted_evidence_kind and candidate.get("kind"):
                    ev.persisted_evidence_kind = candidate["kind"]

    def _serialize_evidence_envelopes(
        self, research_result: LegislationResearchResult
    ) -> List[Dict[str, Any]]:
        """Persist compact evidence provenance for auditability."""
        serialized: List[Dict[str, Any]] = []
        for envelope in research_result.evidence_envelopes:
            items: List[Dict[str, Any]] = []
            for evidence in getattr(envelope, "evidence", []) or []:
                items.append(
                    {
                        "id": getattr(evidence, "id", "") or "",
                        "kind": getattr(evidence, "kind", "") or "",
                        "label": getattr(evidence, "label", "") or "",
                        "url": getattr(evidence, "url", "") or "",
                        "excerpt": getattr(evidence, "excerpt", "") or "",
                        "confidence": getattr(evidence, "confidence", None),
                    }
                )
            serialized.append(
                {
                    "id": getattr(envelope, "id", "") or "",
                    "source_tool": getattr(envelope, "source_tool", "") or "",
                    "source_query": getattr(envelope, "source_query", "") or "",
                    "evidence": items,
                }
            )
        return serialized

    def _serialize_wave2_prerequisites(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ensure wave2 prerequisite payload is JSON-safe for checkpoint persistence."""
        impact_candidates = payload.get("impact_candidates", [])
        if not isinstance(impact_candidates, list):
            impact_candidates = []
        parameter_candidates = payload.get("parameter_candidates", {})
        if not isinstance(parameter_candidates, dict):
            parameter_candidates = {}

        curated_evidence = []
        raw_envelopes = payload.get("curated_evidence_envelopes", [])
        if isinstance(raw_envelopes, list):
            for envelope in raw_envelopes:
                if hasattr(envelope, "model_dump"):
                    envelope_dict = envelope.model_dump(mode="json")
                elif isinstance(envelope, dict):
                    envelope_dict = dict(envelope)
                else:
                    continue
                items = []
                for evidence in envelope_dict.get("evidence", []) or []:
                    if hasattr(evidence, "model_dump"):
                        evidence_dict = evidence.model_dump(mode="json")
                    elif isinstance(evidence, dict):
                        evidence_dict = dict(evidence)
                    else:
                        continue
                    items.append(
                        {
                            "id": evidence_dict.get("id", ""),
                            "kind": evidence_dict.get("kind", ""),
                            "label": evidence_dict.get("label", ""),
                            "url": evidence_dict.get("url", ""),
                            "excerpt": evidence_dict.get("excerpt", ""),
                            "confidence": evidence_dict.get("confidence"),
                            "source_type": (
                                (evidence_dict.get("metadata") or {}).get("source_type")
                                if isinstance(evidence_dict.get("metadata"), dict)
                                else None
                            ),
                        }
                    )
                curated_evidence.append(
                    {
                        "id": envelope_dict.get("id", ""),
                        "source_tool": envelope_dict.get("source_tool", ""),
                        "source_query": envelope_dict.get("source_query", ""),
                        "evidence_count": len(items),
                        "evidence": items,
                    }
                )

        return {
            "impact_candidates": impact_candidates,
            "parameter_candidates": parameter_candidates,
            "curated_evidence": curated_evidence,
        }

    def _match_research_evidence_candidate(
        self,
        impact: LegislationImpact,
        evidence: ImpactEvidence,
        evidence_by_url: Dict[str, Dict[str, str]],
        evidence_candidates: List[Dict[str, str]],
    ) -> Optional[Dict[str, str]]:
        """Find the best research candidate for a generated evidence item."""
        url_key = (evidence.url or "").strip().lower()
        if url_key and url_key in evidence_by_url:
            return evidence_by_url[url_key]

        normalized_excerpt = re.sub(r"\s+", " ", (evidence.excerpt or "")).strip().lower()
        best_candidate: Optional[Dict[str, str]] = None
        best_score = 0
        impact_tokens = self._claim_tokens(impact)

        for candidate in evidence_candidates:
            score = 0
            candidate_excerpt = re.sub(
                r"\s+", " ", (candidate.get("excerpt", "") or "")
            ).strip()
            candidate_lower = candidate_excerpt.lower()
            candidate_name = (candidate.get("source_name", "") or "").strip().lower()

            if normalized_excerpt and candidate_lower:
                if normalized_excerpt == candidate_lower:
                    score += 100
                elif normalized_excerpt in candidate_lower or candidate_lower in normalized_excerpt:
                    score += 60

            if evidence.source_name and candidate_name:
                if evidence.source_name.strip().lower() == candidate_name:
                    score += 20

            overlap = len(impact_tokens.intersection(self._tokenize_text(candidate_excerpt)))
            score += min(overlap, 12)

            if score > best_score:
                best_score = score
                best_candidate = candidate

        return best_candidate if best_score >= 4 else None

    def _apply_fail_closed_review_gates(
        self,
        review: ReviewCritique,
        analysis: LegislationAnalysisResponse,
    ) -> ReviewCritique:
        """Force review failure when impact prose is unsupported by cited excerpts."""
        support_issues = self._collect_claim_support_issues(analysis)
        if not support_issues:
            return review

        review.passed = False
        review.factual_errors = list(dict.fromkeys(review.factual_errors + support_issues))
        gate_note = "Deterministic evidence gate: impact claims lack supporting excerpts."
        review.critique = (
            f"{review.critique} {gate_note}".strip() if review.critique else gate_note
        )
        return review

    def _normalize_review(
        self,
        review: ReviewCritique,
        analysis: LegislationAnalysisResponse,
    ) -> ReviewCritique:
        review = self._apply_fail_closed_review_gates(review, analysis)
        review.missing_impacts = self._filter_cost_of_living_missing_impacts(
            review.missing_impacts
        )
        if review.passed and (review.missing_impacts or review.factual_errors):
            review.passed = False
            if review.critique:
                review.critique += (
                    " Auto-corrected: review cannot pass while listing "
                    "missing impacts or factual errors."
                )
        return review

    def _filter_cost_of_living_missing_impacts(
        self, missing_impacts: List[str]
    ) -> List[str]:
        """Keep only review gaps that are actually relevant to fiscal / cost-of-living scope."""
        relevant: List[str] = []
        for item in missing_impacts:
            lowered = (item or "").lower()
            if "non-fiscal" in lowered or "non fiscal" in lowered:
                continue
            if any(term in lowered for term in FISCAL_MISSING_IMPACT_TERMS):
                relevant.append(item)
        return relevant

    def _collect_claim_support_issues(
        self, analysis: LegislationAnalysisResponse
    ) -> List[str]:
        """Return fail-closed issues for impacts without materially supporting excerpts."""
        issues: List[str] = []
        for impact in analysis.impacts:
            claim_tokens = self._claim_tokens(impact)
            if not claim_tokens:
                continue
            claim_text = " ".join(
                [
                    impact.legal_interpretation or "",
                    impact.impact_description or "",
                    impact.chain_of_causality or "",
                ]
            ).lower()
            requires_resident_burden_support = any(
                indicator in claim_text
                for indicator in RESIDENT_BURDEN_CLAIM_INDICATORS
            ) and not self._is_negative_resident_burden_claim(claim_text)

            if not impact.evidence:
                issues.append(
                    f"Impact {impact.impact_number} has no cited evidence supporting prose claims."
                )
                continue

            supported = False
            quantified_supported = not impact.is_quantified
            resident_burden_supported = not requires_resident_burden_support
            for ev in impact.evidence:
                excerpt = re.sub(r"\s+", " ", (ev.excerpt or "")).strip()
                if self._is_weak_excerpt(excerpt):
                    continue
                excerpt_tokens = self._tokenize_text(excerpt)
                overlap = len(claim_tokens.intersection(excerpt_tokens))
                if overlap >= 2:
                    supported = True
                    if impact.is_quantified and supports_quantified_evidence(
                        excerpt=excerpt,
                        source_name=ev.source_name or "",
                        numeric_basis=None,
                    ):
                        quantified_supported = True
                    if requires_resident_burden_support and any(
                        term in excerpt.lower()
                        for term in RESIDENT_BURDEN_EVIDENCE_TERMS
                    ):
                        resident_burden_supported = True
                    if not impact.is_quantified:
                        break

            if not supported:
                issues.append(
                    f"Impact {impact.impact_number} evidence excerpts do not materially support the stated legal/impact claims."
                )
                continue

            if impact.is_quantified and not quantified_supported:
                issues.append(
                    f"Impact {impact.impact_number} is quantified but cited evidence lacks numeric fiscal support."
                )

            if requires_resident_burden_support and not resident_burden_supported:
                issues.append(
                    f"Impact {impact.impact_number} extends to resident/tax/cost-of-living burdens without supporting evidence."
                )

        return issues

    def _is_negative_resident_burden_claim(self, claim_text: str) -> bool:
        return any(pattern in claim_text for pattern in NEGATED_RESIDENT_BURDEN_PATTERNS)

    def _claim_tokens(self, impact: LegislationImpact) -> set[str]:
        text = " ".join(
            [
                impact.legal_interpretation or "",
                impact.impact_description or "",
                impact.chain_of_causality or "",
            ]
        )
        return self._tokenize_text(text)

    def _tokenize_text(self, text: str) -> set[str]:
        tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(token) >= 4 and token not in EVIDENCE_STOPWORDS
        }
        return tokens

    def _is_weak_excerpt(self, excerpt: str) -> bool:
        normalized = re.sub(r"\s+", " ", excerpt or "").strip()
        if len(normalized) < 80:
            return True
        lower = normalized.lower()
        if any(re.search(pattern, lower) for pattern in EVIDENCE_BOILERPLATE_PATTERNS):
            return True
        return False

    async def _refine_step(
        self,
        bill_id: str,
        analysis: LegislationAnalysisResponse,
        review: ReviewCritique,
        bill_text: str,
        model: str,
        breakdown: Any = None,
    ) -> LegislationAnalysisResponse:
        """Refine analysis based on critique."""
        quantification_note = ""
        if breakdown and not breakdown.overall_quantification_eligible:
            quantification_note = (
                "\n\nIMPORTANT: Quantification is NOT permitted for this bill. "
                "Do not emit scenario bounds or modeled quantitative fields."
            )
        system_prompt = (
            "Refine the analysis based on the critique. Ensure all issues are addressed."
            f"{quantification_note}"
        )

        user_message = f"""
Original Analysis: {analysis.model_dump_json()}
Critique: {review.model_dump_json()}
Bill Text: {bill_text[:5000]}
"""

        result = await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model=model,
            response_model=LegislationAnalysisResponse,
        )
        return result  # type: ignore[return-value]

    async def _create_pipeline_run(
        self,
        bill_id: str,
        jurisdiction: str,
        models: Dict[str, str],
        trigger_source: str = "manual",
    ) -> str:
        """Create a new pipeline run record."""
        if hasattr(self.db, "create_pipeline_run"):
            run_id = await self.db.create_pipeline_run(
                bill_id, jurisdiction, models, trigger_source=trigger_source
            )
            if run_id:
                return run_id
        return "run_id_placeholder"

    def _empty_analysis(
        self, bill_id: str, jurisdiction: str, model_used: str
    ) -> LegislationAnalysisResponse:
        return LegislationAnalysisResponse(
            bill_number=bill_id,
            jurisdiction=jurisdiction,
            sufficiency_state=SufficiencyState.INSUFFICIENT_EVIDENCE,
            quantification_eligible=False,
            impacts=[],
            aggregate_scenario_bounds=None,
            analysis_timestamp=datetime.now().isoformat(),
            model_used=model_used,
        )

    def _breakdown_reason(self, breakdown: SufficiencyBreakdown | Any) -> str:
        failures = getattr(breakdown, "bill_level_failures", []) or []
        return "; ".join(
            failure.value if hasattr(failure, "value") else str(failure)
            for failure in failures
        )

    def _build_mode_selection_output(
        self, impact_candidate: Dict[str, Any]
    ) -> Dict[str, Any]:
        hints = impact_candidate.get("candidate_mode_hints", []) or []
        supported = [hint for hint in hints if hint in {"direct_fiscal", "compliance_cost"}]
        unsupported = [hint for hint in hints if hint not in {"direct_fiscal", "compliance_cost"}]
        if "direct_fiscal" in supported:
            selected = "direct_fiscal"
        elif "compliance_cost" in supported:
            selected = "compliance_cost"
        else:
            selected = "qualitative_only"
        ambiguity = "unsupported" if unsupported and not supported else "clear"
        return {
            "impact_id": impact_candidate.get("impact_id", "impact-1"),
            "candidate_modes": hints or ["qualitative_only"],
            "selected_mode": selected,
            "rejected_modes": [mode for mode in hints if mode != selected],
            "selection_rationale": "Wave 1 deterministic mode selection from research hints.",
            "ambiguity_status": ambiguity,
            "composition_candidate": False,
        }

    def _build_parameter_resolution_output(
        self,
        impact_id: str,
        selected_mode: str,
        parameter_candidates: Dict[str, Any],
    ) -> Dict[str, Any]:
        required_parameters = {
            "direct_fiscal": ["fiscal_amount"],
            "compliance_cost": ["population", "frequency", "time_burden", "wage_rate"],
        }.get(selected_mode, [])
        resolved_parameters = {
            name: {
                "name": name,
                "value": candidate["value"],
                "unit": candidate.get("unit"),
                "source_url": candidate.get("source_url", ""),
                "source_excerpt": candidate.get("source_excerpt", ""),
                "source_type": candidate.get("source_type"),
                "literature_confidence": candidate.get("literature_confidence"),
            }
            for name, candidate in parameter_candidates.items()
            if candidate.get("value") is not None
        }
        missing_parameters = [
            name for name in required_parameters if name not in resolved_parameters
        ]
        source_hierarchy_status = {
            name: candidate.get("source_hierarchy_status", "failed_closed")
            for name, candidate in parameter_candidates.items()
        }
        for name in required_parameters:
            source_hierarchy_status.setdefault(name, "failed_closed")
        excerpt_validation_status = {
            name: candidate.get("excerpt_validation_status", "not_applicable")
            for name, candidate in parameter_candidates.items()
        }
        literature_confidence = {
            name: float(candidate.get("literature_confidence"))
            for name, candidate in parameter_candidates.items()
            if candidate.get("literature_confidence") is not None
        }
        if (
            selected_mode == "compliance_cost"
            and "wage_rate" in resolved_parameters
            and "wage_rate" not in literature_confidence
        ):
            literature_confidence["wage_rate"] = 0.0
        dominant_uncertainty_parameters = (
            ["fiscal_amount"]
            if selected_mode == "direct_fiscal"
            else [name for name in ["time_burden", "population", "unit_cost"] if name in parameter_candidates]
        )
        return {
            "impact_id": impact_id,
            "required_parameters": required_parameters,
            "resolved_parameters": resolved_parameters,
            "missing_parameters": missing_parameters,
            "source_hierarchy_status": source_hierarchy_status,
            "excerpt_validation_status": excerpt_validation_status,
            "literature_confidence": literature_confidence,
            "dominant_uncertainty_parameters": dominant_uncertainty_parameters,
        }

    def _build_parameter_validation_output(
        self, resolution: Dict[str, Any], eligible_for_quant: bool
    ) -> Dict[str, Any]:
        missing = resolution.get("missing_parameters", []) or []
        failed_hierarchy = any(
            value == "failed_closed"
            for value in (resolution.get("source_hierarchy_status", {}) or {}).values()
        )
        is_valid = eligible_for_quant and not missing and not failed_hierarchy
        failures = []
        if missing:
            failures.append("parameter_missing")
        if failed_hierarchy:
            failures.append("source_hierarchy_failed")
        return {
            "schema_valid": True,
            "arithmetic_valid": is_valid,
            "bound_construction_valid": is_valid,
            "claim_support_valid": True,
            "validation_failures": failures,
        }

    def _apply_wave1_quantification(
        self,
        analysis: LegislationAnalysisResponse,
        impact_candidates: List[Dict[str, Any]],
        mode_decisions: List[Dict[str, Any]],
        parameter_resolutions: List[Dict[str, Any]],
        breakdown: SufficiencyBreakdown,
    ) -> LegislationAnalysisResponse:
        while len(analysis.impacts) < len(impact_candidates):
            candidate = impact_candidates[len(analysis.impacts)]
            analysis.impacts.append(
                LegislationImpact(
                    impact_number=len(analysis.impacts) + 1,
                    relevant_clause="; ".join(candidate.get("relevant_clauses", []) or []),
                    legal_interpretation="Deterministic Wave 1 impact synthesis.",
                    impact_description=candidate.get("impact_description", ""),
                    evidence=[],
                    chain_of_causality="Derived from research-backed parameter extraction.",
                )
            )

        aggregate_low = 0.0
        aggregate_central = 0.0
        aggregate_high = 0.0
        quantified_count = 0

        for idx, impact in enumerate(analysis.impacts):
            if idx >= len(mode_decisions):
                impact.impact_mode = "qualitative_only"
                continue
            mode = mode_decisions[idx]["selected_mode"]
            resolution = parameter_resolutions[idx]
            impact.impact_mode = mode
            impact.mode_selection = {
                key: value
                for key, value in mode_decisions[idx].items()
                if key != "impact_id"
            }
            impact.parameter_resolution = {
                key: value
                for key, value in resolution.items()
                if key != "impact_id"
            }
            gate = (
                breakdown.impact_gate_summaries[idx]
                if idx < len(breakdown.impact_gate_summaries)
                else None
            )
            impact.parameter_validation = self._build_parameter_validation_output(
                resolution, gate.quantification_eligible if gate else False
            )
            impact.failure_codes = [
                failure.value for failure in getattr(gate, "gate_failures", []) or []
            ]

            if not gate or not gate.quantification_eligible:
                cleaned = strip_quantification([impact.model_dump(mode="json")])[0]
                analysis.impacts[idx] = LegislationImpact(**cleaned)
                analysis.impacts[idx].mode_selection = impact.mode_selection
                analysis.impacts[idx].parameter_resolution = impact.parameter_resolution
                analysis.impacts[idx].parameter_validation = impact.parameter_validation
                analysis.impacts[idx].failure_codes = impact.failure_codes
                continue

            resolved = resolution.get("resolved_parameters", {}) or {}
            impact.modeled_parameters = resolved
            if mode == "direct_fiscal" and "fiscal_amount" in resolved:
                total = resolved["fiscal_amount"]["value"]
                impact.component_breakdown = [
                    {
                        "component_name": "direct_fiscal",
                        "base": total,
                        "low": total,
                        "high": total,
                        "unit": "usd_per_year",
                        "formula": "official fiscal amount",
                    }
                ]
                impact.scenario_bounds = ScenarioBounds(
                    conservative=total,
                    central=total,
                    aggressive=total,
                )
            elif mode == "compliance_cost":
                admin_total = 0.0
                substantive_total = 0.0
                components = []
                if all(
                    name in resolved
                    for name in ["population", "frequency", "time_burden", "wage_rate"]
                ):
                    admin_total = (
                        resolved["population"]["value"]
                        * resolved["frequency"]["value"]
                        * resolved["time_burden"]["value"]
                        * resolved["wage_rate"]["value"]
                    )
                    components.append(
                        {
                            "component_name": "administrative_labor_cost",
                            "base": admin_total,
                            "low": admin_total * 0.8,
                            "high": admin_total * 1.2,
                            "unit": "usd_per_year",
                            "formula": "population * frequency * time_burden * wage_rate",
                        }
                    )
                if "affected_units" in resolved and "unit_cost" in resolved:
                    substantive_total = (
                        resolved["affected_units"]["value"]
                        * resolved["unit_cost"]["value"]
                    )
                    components.append(
                        {
                            "component_name": "substantive_non_labor_cost",
                            "base": substantive_total,
                            "low": substantive_total * 0.8,
                            "high": substantive_total * 1.2,
                            "unit": "usd_per_year",
                            "formula": "affected_units * unit_cost",
                        }
                    )
                total = admin_total + substantive_total
                impact.component_breakdown = components
                impact.scenario_bounds = ScenarioBounds(
                    conservative=sum(item["low"] for item in components),
                    central=total,
                    aggressive=sum(item["high"] for item in components),
                )

            if impact.scenario_bounds is not None:
                quantified_count += 1
                aggregate_low += impact.scenario_bounds.conservative
                aggregate_central += impact.scenario_bounds.central
                aggregate_high += impact.scenario_bounds.aggressive

        analysis.sufficiency_state = breakdown.overall_sufficiency_state
        analysis.insufficiency_reason = self._breakdown_reason(breakdown) or None
        analysis.quantification_eligible = quantified_count > 0
        analysis.aggregate_scenario_bounds = (
            ScenarioBounds(
                conservative=aggregate_low,
                central=aggregate_central,
                aggressive=aggregate_high,
            )
            if quantified_count > 0
            else None
        )
        return analysis

    def _validate_deterministic_step_payload(
        self, step_name: str, payload: Dict[str, Any]
    ) -> None:
        required_keys_by_step = {
            "mode_selection": {
                "candidate_modes",
                "selected_mode",
                "rejected_modes",
                "selection_rationale",
                "ambiguity_status",
                "composition_candidate",
            },
            "parameter_resolution": {
                "required_parameters",
                "resolved_parameters",
                "missing_parameters",
                "source_hierarchy_status",
                "excerpt_validation_status",
                "literature_confidence",
                "dominant_uncertainty_parameters",
            },
            "parameter_validation": {
                "schema_valid",
                "arithmetic_valid",
                "bound_construction_valid",
                "claim_support_valid",
                "validation_failures",
            },
        }
        required_keys = required_keys_by_step.get(step_name)
        if not required_keys:
            return
        missing = [key for key in required_keys if key not in payload]
        if missing:
            raise PrefixFixtureError(
                f"fixture_invalid: {step_name} missing required keys {missing}"
            )

    async def _load_prefix_seed_outputs(
        self,
        reuse_prior_step_outputs: Optional[str],
        fixture_mode: Optional[str],
        start_at_step: int,
    ) -> Dict[str, Dict[str, Any]]:
        seed_outputs: Dict[str, Dict[str, Any]] = {}
        if reuse_prior_step_outputs:
            if not hasattr(self.db, "_fetch"):
                raise PrefixFixtureError(
                    "fixture_invalid: db client missing _fetch for replay"
                )
            rows = await self.db._fetch(
                """
                SELECT step_name, step_number, output_result
                FROM pipeline_steps
                WHERE run_id::text = $1
                ORDER BY step_number ASC
                """,
                reuse_prior_step_outputs,
            )
            if not rows:
                raise PrefixFixtureError(
                    "fixture_invalid: prior_run_id has no pipeline_steps"
                )
            for row in rows:
                step_name = row["step_name"]
                step_number = int(row["step_number"])
                if step_number >= start_at_step:
                    continue
                output = row["output_result"] or {}
                if isinstance(output, str):
                    try:
                        output = json.loads(output)
                    except Exception as e:
                        raise PrefixFixtureError(
                            f"fixture_invalid: invalid JSON output_result for {step_name}"
                        ) from e
                if not isinstance(output, dict):
                    raise PrefixFixtureError(
                        f"fixture_invalid: output_result for {step_name} must be object"
                    )
                self._validate_deterministic_step_payload(step_name, output)
                seed_outputs[step_name] = output

        if fixture_mode:
            try:
                with open(fixture_mode, "r", encoding="utf-8") as handle:
                    fixture_data = json.load(handle)
            except Exception as e:
                raise PrefixFixtureError(
                    f"fixture_invalid: unable to load fixture {fixture_mode}"
                ) from e

            fixture_steps = fixture_data
            if isinstance(fixture_data, dict) and "steps" in fixture_data:
                fixture_steps = fixture_data["steps"]

            if isinstance(fixture_steps, dict):
                for step_name, payload in fixture_steps.items():
                    if step_name not in STEP_INDEX:
                        raise PrefixFixtureError(
                            f"fixture_invalid: unknown step {step_name}"
                        )
                    if STEP_INDEX[step_name] >= start_at_step:
                        continue
                    if not isinstance(payload, dict):
                        raise PrefixFixtureError(
                            f"fixture_invalid: payload for {step_name} must be object"
                        )
                    self._validate_deterministic_step_payload(step_name, payload)
                    seed_outputs[step_name] = payload
            elif isinstance(fixture_steps, list):
                for item in fixture_steps:
                    if not isinstance(item, dict):
                        raise PrefixFixtureError(
                            "fixture_invalid: fixture step entries must be objects"
                        )
                    step_name = item.get("step_name")
                    payload = item.get("output_result")
                    if step_name not in STEP_INDEX:
                        raise PrefixFixtureError(
                            f"fixture_invalid: unknown step {step_name}"
                        )
                    if STEP_INDEX[step_name] >= start_at_step:
                        continue
                    if not isinstance(payload, dict):
                        raise PrefixFixtureError(
                            f"fixture_invalid: payload for {step_name} must be object"
                        )
                    self._validate_deterministic_step_payload(step_name, payload)
                    seed_outputs[step_name] = payload
            else:
                raise PrefixFixtureError(
                    "fixture_invalid: fixture content must be dict or list"
                )

        return seed_outputs

    async def _complete_pipeline_run(
        self,
        run_id: str,
        bill_id: str,
        bill_text: str,
        analysis: LegislationAnalysisResponse,
        review: ReviewCritique,
        jurisdiction: str,
        breakdown: Any = None,
        rag_chunks_retrieved: int = 0,
        retriever_invoked: bool = False,
        run_status: str = "completed",
    ) -> Dict[str, Any]:
        """Mark pipeline run as complete and store results with truthful metadata."""
        persistence: Dict[str, Any] = {
            "legislation_id": None,
            "analysis_stored": False,
            "impacts_count": 0,
        }
        result_data = {
            "analysis": analysis.model_dump(),
            "review": review.model_dump(),
            "sufficiency_breakdown": breakdown.model_dump() if breakdown else None,
            "source_text_present": bool(bill_text and len(bill_text) > 100),
            "retriever_invoked": retriever_invoked,
            "rag_chunks_retrieved": rag_chunks_retrieved,
            "validated_evidence_count": len(analysis.impacts)
            if analysis.impacts
            else 0,
            "quantification_eligible": analysis.quantification_eligible,
            "insufficiency_reason": analysis.insufficiency_reason,
            "model_used": analysis.model_used,
        }
        try:
            bill_data = {
                "bill_number": bill_id,
                "title": analysis.title
                if analysis.title and analysis.title != ""
                else None,
                "text": bill_text if bill_text else None,
                "status": "analyzed",
                "sufficiency_state": analysis.sufficiency_state.value
                if analysis.sufficiency_state
                else None,
                "insufficiency_reason": analysis.insufficiency_reason,
                "quantification_eligible": analysis.quantification_eligible,
                "aggregate_scenario_bounds": analysis.aggregate_scenario_bounds.model_dump()
                if analysis.aggregate_scenario_bounds
                else None,
            }

            if hasattr(self.db, "get_or_create_jurisdiction"):
                jurisdiction_id = await self.db.get_or_create_jurisdiction(
                    jurisdiction, "municipality"
                )
                if not jurisdiction_id:
                    logger.error(
                        f"Failed to resolve jurisdiction_id for {jurisdiction}"
                    )
                elif hasattr(self.db, "store_legislation"):
                    legislation_id = await self.db.store_legislation(
                        jurisdiction_id, bill_data
                    )

                    if legislation_id:
                        persistence["legislation_id"] = legislation_id
                        persistence["analysis_stored"] = True
                        impact_dicts = [i.model_dump() for i in analysis.impacts]
                        if hasattr(self.db, "store_impacts"):
                            stored_impacts = await self.db.store_impacts(
                                legislation_id, impact_dicts
                            )
                            if stored_impacts:
                                persistence["impacts_count"] = len(analysis.impacts)
                        logger.info(f"Stored analysis results for {bill_id}")
                    else:
                        logger.warning(
                            "store_legislation returned no id for %s (%s)",
                            bill_id,
                            jurisdiction,
                        )
        except Exception as e:
            logger.error(f"Failed to store results: {e}")
            import traceback

            traceback.print_exc()

        try:
            if run_status == "completed" and hasattr(self.db, "complete_pipeline_run"):
                await self.db.complete_pipeline_run(run_id, result_data)
            elif hasattr(self.db, "_execute"):
                await self.db._execute(
                    """
                    UPDATE pipeline_runs
                    SET status = $1, result = $2, completed_at = NOW()
                    WHERE id = $3
                    """,
                    run_status,
                    json.dumps(result_data),
                    run_id,
                )
        except Exception as e:
            logger.error(f"Failed to finalize pipeline run status: {e}")

        return persistence

    async def _fail_pipeline_run(self, run_id: str, error: str, status: str = "failed"):
        """Mark pipeline run as failed or fixture-invalid."""
        print(f"Pipeline Run {run_id} Failed: {error}")
        if status == "failed" and hasattr(self.db, "fail_pipeline_run"):
            await self.db.fail_pipeline_run(run_id, error)
            return
        if hasattr(self.db, "_execute"):
            await self.db._execute(
                """
                UPDATE pipeline_runs
                SET status = $1, error = $2, completed_at = NOW()
                WHERE id = $3
                """,
                status,
                error,
                run_id,
            )

    async def _emit_slack_summary(
        self,
        run_id: str,
        bill_id: str,
        jurisdiction: str,
        status: str,
        trigger_source: str,
        analysis=None,
        error: str = "",
    ):
        """Emit Slack summary for manual runs after pipeline completion."""
        if trigger_source != "manual":
            return

        import os

        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
        if not webhook_url:
            logger.debug("No SLACK_WEBHOOK_URL set, skipping Slack summary")
            return

        try:
            from services.slack_summary import load_and_emit

            await load_and_emit(self.db, webhook_url, run_id, trigger_source)
        except Exception as exc:
            logger.warning("Slack summary emit failed (non-blocking): %s", exc)
