#!/usr/bin/env python3
"""Run golden-fixture with-web vs without-web comparison diagnostics (bd-bkco.5)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.verification.fixtures.research_fixtures import (
    FixtureStore,
    ReplayableResearchFixture,
)

if TYPE_CHECKING:
    from schemas.analysis import LegislationAnalysisResponse
    from services.legislation_research import LegislationResearchResult

PIPELINE_RUNTIME_AVAILABLE = True
PIPELINE_RUNTIME_ERROR: Optional[str] = None
try:
    from llm_common.core import LLMClient
    from llm_common.web_search import WebSearchClient
    from schemas.analysis import LegislationAnalysisResponse
    from schemas.analysis import ReviewCritique
    from services.legislation_research import LegislationResearchResult
    from services.llm.orchestrator import AnalysisPipeline
except ModuleNotFoundError as exc:
    PIPELINE_RUNTIME_AVAILABLE = False
    PIPELINE_RUNTIME_ERROR = str(exc)


DEFAULT_MODELS = {
    "research": "fixture-research",
    "generate": "fixture-generate",
    "review": "fixture-review",
}


@dataclass
class VariantRunResult:
    bill_id: str
    variant: str
    run_id: str
    final_conclusion: Dict[str, Any]
    parameter_resolution: Dict[str, Any]
    sufficiency_gate: Dict[str, Any]
    research_counts: Dict[str, Any]


@dataclass
class LLMTextResponse:
    """Simple chat_completion response shim with plain text content."""

    content: str


@dataclass
class FixtureRetrievedChunk:
    """Minimal retrieved-chunk shape required by pipeline/runtime helpers."""

    content: str
    score: float
    metadata: Dict[str, Any]
    chunk_id: str = ""


class InMemoryPipelineDB:
    """Lightweight async DB shim for deterministic comparison runs."""

    def __init__(self, fixture_map: Dict[str, ReplayableResearchFixture]) -> None:
        self.fixture_map = fixture_map
        self.current_bill_id: Optional[str] = None
        self.current_chunk_count: int = 0
        self.runs: Dict[str, Dict[str, Any]] = {}
        self.pipeline_steps: Dict[str, List[Dict[str, Any]]] = {}

    async def create_pipeline_run(
        self,
        bill_id: str,
        jurisdiction: str,
        models: Dict[str, str],
        trigger_source: str = "manual",
    ) -> str:
        run_id = str(uuid4())
        self.runs[run_id] = {
            "bill_id": bill_id,
            "jurisdiction": jurisdiction,
            "models": models,
            "trigger_source": trigger_source,
            "status": "running",
        }
        self.pipeline_steps[run_id] = []
        return run_id

    async def get_latest_scrape_for_bill(
        self, jurisdiction: str, bill_id: str
    ) -> Optional[Dict[str, Any]]:
        fixture = self.fixture_map.get(bill_id)
        if not fixture:
            return None
        return {
            "id": f"scrape-{bill_id}",
            "document_id": f"doc-{bill_id}",
            "url": fixture.scraped_bill_text.source_url or "https://example.test",
            "content_hash": f"hash-{bill_id}",
            "metadata": {"bill_number": fixture.scraped_bill_text.bill_number},
            "storage_uri": f"s3://fixtures/{bill_id}.html",
        }

    async def get_vector_stats(self, document_id: Optional[str]) -> Dict[str, Any]:
        return {"chunk_count": self.current_chunk_count if document_id else 0}

    async def get_or_create_jurisdiction(self, jurisdiction: str, _kind: str) -> str:
        return f"jurisdiction:{jurisdiction.lower()}"

    async def store_legislation(
        self, jurisdiction_id: str, bill_data: Dict[str, Any]
    ) -> str:
        bill_number = bill_data.get("bill_number", "unknown")
        return f"legislation:{jurisdiction_id}:{bill_number}"

    async def store_impacts(
        self, legislation_id: str, impact_dicts: List[Dict[str, Any]]
    ) -> bool:
        _ = legislation_id
        _ = impact_dicts
        return True

    async def complete_pipeline_run(self, run_id: str, result_data: Dict[str, Any]) -> None:
        run = self.runs.setdefault(run_id, {})
        run["status"] = "completed"
        run["result"] = result_data

    async def fail_pipeline_run(self, run_id: str, error: str) -> None:
        run = self.runs.setdefault(run_id, {})
        run["status"] = "failed"
        run["error"] = error

    async def _execute(self, query: str, *args: Any) -> None:
        if "INSERT INTO pipeline_steps" in query and len(args) >= 8:
            run_id = str(args[0])
            output_raw = args[5]
            output_obj = output_raw
            if isinstance(output_raw, str):
                output_obj = json.loads(output_raw)
            self.pipeline_steps.setdefault(run_id, []).append(
                {
                    "step_number": int(args[1]),
                    "step_name": str(args[2]),
                    "status": str(args[3]),
                    "output_result": output_obj if isinstance(output_obj, dict) else {},
                }
            )
            return
        if "UPDATE pipeline_runs" in query and len(args) >= 3:
            status = str(args[0])
            result_raw = args[1]
            run_id = str(args[2])
            result_obj = result_raw
            if isinstance(result_raw, str):
                result_obj = json.loads(result_raw)
            run = self.runs.setdefault(run_id, {})
            run["status"] = status
            run["result"] = result_obj if isinstance(result_obj, dict) else {}


def _manifest_by_bill(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    manifest_path = (
        repo_root
        / "backend"
        / "scripts"
        / "verification"
        / "fixtures"
        / "golden_bill_corpus_manifest.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    bills = payload.get("bills", [])
    return {item["bill_id"]: item for item in bills if isinstance(item, dict)}


def _build_research_result(
    fixture: ReplayableResearchFixture,
    include_web: bool,
) -> "LegislationResearchResult":
    rag_chunks = _coerce_fixture_rag_chunks(fixture.get_rag_chunks())
    web_sources = fixture.get_web_sources() if include_web else []
    source_text_present = bool(fixture.get_bill_text().strip())
    rag_count = len(rag_chunks)
    web_count = len(web_sources)

    if not source_text_present:
        is_sufficient = False
        insufficiency_reason = "missing_source_text"
    elif rag_count >= 3:
        is_sufficient = True
        insufficiency_reason = None
    elif rag_count >= 1 and web_count >= 2:
        is_sufficient = True
        insufficiency_reason = None
    elif web_count >= 5:
        is_sufficient = True
        insufficiency_reason = None
    else:
        is_sufficient = False
        insufficiency_reason = "insufficient_research_sources"

    return LegislationResearchResult(
        bill_id=fixture.bill_id,
        jurisdiction=fixture.bill_id.split("-", 1)[0],
        evidence_envelopes=[],
        rag_chunks=rag_chunks,
        web_sources=web_sources,
        impact_candidates=[],
        parameter_candidates={},
        wave2_prerequisites={},
        sufficiency_breakdown={
            "source_text_present": source_text_present,
            "rag_chunks_retrieved": rag_count,
            "web_research_sources_found": web_count,
            "fiscal_notes_detected": False,
            "bill_text_chunks": rag_count,
        },
        is_sufficient=is_sufficient,
        insufficiency_reason=insufficiency_reason,
        retriever_invoked=True,
    )


def _coerce_fixture_rag_chunks(raw_chunks: List[Dict[str, Any]]) -> List[FixtureRetrievedChunk]:
    """Convert fixture chunk dictionaries to runtime-compatible chunk objects."""
    converted: List[FixtureRetrievedChunk] = []
    for item in raw_chunks:
        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        converted.append(
            FixtureRetrievedChunk(
                chunk_id=str(item.get("chunk_id", "")),
                content=str(item.get("content", "")),
                score=float(item.get("score", 0.0)),
                metadata=metadata,
            )
        )
    return converted


def _conclusion_payload(analysis: LegislationAnalysisResponse) -> Dict[str, Any]:
    return {
        "sufficiency_state": analysis.sufficiency_state.value
        if analysis.sufficiency_state
        else None,
        "quantification_eligible": bool(analysis.quantification_eligible),
        "insufficiency_reason": analysis.insufficiency_reason,
        "impacts_count": len(analysis.impacts),
        "aggregate_scenario_bounds_present": analysis.aggregate_scenario_bounds is not None,
        "total_impact_p50": analysis.total_impact_p50,
    }


def _parameter_stats(payload: Dict[str, Any]) -> Dict[str, int]:
    impact_rows: List[Dict[str, Any]] = []
    if isinstance(payload.get("impact_parameters"), list):
        impact_rows = [
            row for row in payload["impact_parameters"] if isinstance(row, dict)
        ]
    elif payload:
        impact_rows = [payload]
    resolved = sum(
        len((row.get("resolved_parameters") or {}))
        for row in impact_rows
        if isinstance(row.get("resolved_parameters") or {}, dict)
    )
    missing = sum(
        len((row.get("missing_parameters") or []))
        for row in impact_rows
        if isinstance(row.get("missing_parameters") or [], list)
    )
    return {"resolved_count": resolved, "missing_count": missing}


def verdict_from_final_conclusion(
    with_web: Dict[str, Any], without_web: Dict[str, Any]
) -> str:
    if with_web == without_web:
        return "no_effect"
    if (
        with_web.get("quantification_eligible") is True
        and without_web.get("quantification_eligible") is False
    ):
        return "improves"
    if (
        with_web.get("quantification_eligible") is False
        and without_web.get("quantification_eligible") is True
    ):
        return "harms"
    return "changed"


def verdict_from_parameter_resolution(
    with_web: Dict[str, Any], without_web: Dict[str, Any]
) -> str:
    if with_web == without_web:
        return "no_effect"
    with_stats = _parameter_stats(with_web)
    without_stats = _parameter_stats(without_web)
    if (
        with_stats["missing_count"] < without_stats["missing_count"]
        and with_stats["resolved_count"] >= without_stats["resolved_count"]
    ):
        return "improves"
    if (
        with_stats["missing_count"] > without_stats["missing_count"]
        and with_stats["resolved_count"] <= without_stats["resolved_count"]
    ):
        return "harms"
    return "changed"


def verdict_from_gate_behavior(with_web: Dict[str, Any], without_web: Dict[str, Any]) -> str:
    if with_web == without_web:
        return "no_effect"
    with_eligible = bool(with_web.get("overall_quantification_eligible"))
    without_eligible = bool(without_web.get("overall_quantification_eligible"))
    if with_eligible and not without_eligible:
        return "improves"
    if without_eligible and not with_eligible:
        return "harms"
    with_failures = len(with_web.get("bill_level_failures") or [])
    without_failures = len(without_web.get("bill_level_failures") or [])
    if with_failures < without_failures:
        return "improves"
    if with_failures > without_failures:
        return "harms"
    return "changed"


def overall_verdict_from_dimensions(verdicts: Dict[str, str]) -> str:
    values = set(verdicts.values())
    if "harms" in values:
        return "harms"
    if "improves" in values:
        return "improves"
    if values == {"no_effect"}:
        return "no_effect"
    return "changed"


async def _run_variant(
    db: InMemoryPipelineDB,
    fixture: ReplayableResearchFixture,
    variant: str,
    models: Dict[str, str],
) -> VariantRunResult:
    if not PIPELINE_RUNTIME_AVAILABLE:
        return _run_variant_fixture_only(fixture=fixture, variant=variant)

    include_web = variant == "with_web"
    db.current_bill_id = fixture.bill_id
    db.current_chunk_count = len(fixture.rag_chunks)
    bill_text = fixture.get_bill_text()
    jurisdiction = fixture.bill_id.split("-", 1)[0]

    analysis_payload = LegislationAnalysisResponse(
        bill_number=fixture.bill_id,
        title=fixture.get_bill_title() or fixture.bill_id,
        jurisdiction=jurisdiction,
        status="fixture_replay",
        sufficiency_state="qualitative_only",
        quantification_eligible=False,
        insufficiency_reason="impact_discovery_failed",
        impacts=[],
        aggregate_scenario_bounds=None,
        analysis_timestamp=datetime.now(timezone.utc).isoformat(),
        model_used=models.get("generate", "fixture-generate"),
    ).model_dump_json()
    review_payload = ReviewCritique(
        passed=True,
        critique="Fixture replay review pass",
        missing_impacts=[],
        factual_errors=[],
    ).model_dump_json()
    llm_client = MagicMock(spec=LLMClient)
    llm_client.chat_completion = AsyncMock(
        return_value=LLMTextResponse(content=analysis_payload)
    )
    # First call (generate) -> analysis JSON, second call (review) -> review JSON.
    llm_client.chat_completion.side_effect = [
        LLMTextResponse(content=analysis_payload),
        LLMTextResponse(content=review_payload),
    ]

    pipeline = AnalysisPipeline(
        llm_client,
        MagicMock(spec=WebSearchClient),
        db,
    )
    research_result = _build_research_result(fixture, include_web=include_web)

    with patch.object(
        pipeline.research_service,
        "research",
        new_callable=AsyncMock,
        return_value=research_result,
    ):
        analysis = await pipeline.run(
            fixture.bill_id,
            bill_text,
            jurisdiction,
            models,
            trigger_source=f"fixture:web_compare:{variant}",
        )

    run_id = max(db.runs.keys(), key=lambda rid: rid)
    step_map = {
        step["step_name"]: step["output_result"]
        for step in db.pipeline_steps.get(run_id, [])
    }
    return VariantRunResult(
        bill_id=fixture.bill_id,
        variant=variant,
        run_id=run_id,
        final_conclusion=_conclusion_payload(analysis),
        parameter_resolution=step_map.get("parameter_resolution", {}),
        sufficiency_gate=step_map.get("sufficiency_gate", {}),
        research_counts={
            "rag_chunks": len(research_result.rag_chunks),
            "web_sources": len(research_result.web_sources),
            "is_sufficient": bool(research_result.is_sufficient),
        },
    )


def _run_variant_fixture_only(
    fixture: ReplayableResearchFixture,
    variant: str,
) -> VariantRunResult:
    include_web = variant == "with_web"
    rag_count = len(fixture.rag_chunks)
    web_count = len(fixture.web_sources) if include_web else 0
    source_text_present = bool(fixture.get_bill_text().strip())

    if not source_text_present:
        sufficiency_state = "research_incomplete"
        insufficiency_reason = "missing_source_text"
        failures = ["missing_source_text"]
    else:
        sufficiency_state = "qualitative_only"
        insufficiency_reason = "impact_discovery_failed"
        failures = ["impact_discovery_failed"]

    parameter_resolution = {
        "impact_id": "impact-1",
        "required_parameters": [],
        "resolved_parameters": {},
        "missing_parameters": [],
        "source_hierarchy_status": {},
        "excerpt_validation_status": {},
        "literature_confidence": {},
        "dominant_uncertainty_parameters": [],
        "impact_parameters": [],
    }
    sufficiency_gate = {
        "overall_quantification_eligible": False,
        "overall_sufficiency_state": sufficiency_state,
        "impact_gate_summaries": [],
        "bill_level_failures": failures,
    }
    final_conclusion = {
        "sufficiency_state": sufficiency_state,
        "quantification_eligible": False,
        "insufficiency_reason": insufficiency_reason,
        "impacts_count": 0,
        "aggregate_scenario_bounds_present": False,
        "total_impact_p50": None,
    }
    is_sufficient = bool(
        source_text_present
        and (
            rag_count >= 3
            or (rag_count >= 1 and web_count >= 2)
            or web_count >= 5
        )
    )

    return VariantRunResult(
        bill_id=fixture.bill_id,
        variant=variant,
        run_id=f"fixture-only:{variant}:{fixture.bill_id}",
        final_conclusion=final_conclusion,
        parameter_resolution=parameter_resolution,
        sufficiency_gate=sufficiency_gate,
        research_counts={
            "rag_chunks": rag_count,
            "web_sources": web_count,
            "is_sufficient": is_sufficient,
        },
    )


async def generate_comparison_report(
    repo_root: Path,
    bill_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    manifest_by_bill = _manifest_by_bill(repo_root)
    fixture_store = FixtureStore.load_corpus()
    candidate_bill_ids = bill_ids or fixture_store.all_bill_ids()
    fixture_map = {
        bill_id: fixture_store.get(bill_id)
        for bill_id in candidate_bill_ids
        if fixture_store.get(bill_id) is not None
    }

    db = InMemoryPipelineDB(fixture_map=fixture_map)  # type: ignore[arg-type]
    comparisons: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []

    for bill_id in candidate_bill_ids:
        fixture = fixture_map.get(bill_id)
        if fixture is None:
            skipped.append({"bill_id": bill_id, "reason": "fixture_missing"})
            continue
        with_web = await _run_variant(db, fixture, "with_web", DEFAULT_MODELS)
        without_web = await _run_variant(db, fixture, "without_web", DEFAULT_MODELS)

        dimension_verdicts = {
            "final_conclusion": verdict_from_final_conclusion(
                with_web.final_conclusion, without_web.final_conclusion
            ),
            "parameter_resolution": verdict_from_parameter_resolution(
                with_web.parameter_resolution, without_web.parameter_resolution
            ),
            "gate_behavior": verdict_from_gate_behavior(
                with_web.sufficiency_gate, without_web.sufficiency_gate
            ),
        }
        overall = overall_verdict_from_dimensions(dimension_verdicts)
        manifest = manifest_by_bill.get(bill_id, {})
        comparisons.append(
            {
                "bill_id": bill_id,
                "jurisdiction": manifest.get("jurisdiction"),
                "mode_bucket": manifest.get("mode_bucket"),
                "expected_quantifiable": manifest.get("expected_quantifiable"),
                "control_type": manifest.get("control_type"),
                "variants": {
                    "with_web": {
                        "run_id": with_web.run_id,
                        "final_conclusion": with_web.final_conclusion,
                        "parameter_resolution": with_web.parameter_resolution,
                        "sufficiency_gate": with_web.sufficiency_gate,
                        "research_counts": with_web.research_counts,
                    },
                    "without_web": {
                        "run_id": without_web.run_id,
                        "final_conclusion": without_web.final_conclusion,
                        "parameter_resolution": without_web.parameter_resolution,
                        "sufficiency_gate": without_web.sufficiency_gate,
                        "research_counts": without_web.research_counts,
                    },
                },
                "dimension_verdicts": dimension_verdicts,
                "overall_verdict": overall,
            }
        )

    overall_counts: Dict[str, int] = {"improves": 0, "harms": 0, "no_effect": 0, "changed": 0}
    dimension_counts: Dict[str, Dict[str, int]] = {
        "final_conclusion": {"improves": 0, "harms": 0, "no_effect": 0, "changed": 0},
        "parameter_resolution": {"improves": 0, "harms": 0, "no_effect": 0, "changed": 0},
        "gate_behavior": {"improves": 0, "harms": 0, "no_effect": 0, "changed": 0},
    }
    for item in comparisons:
        overall_counts[item["overall_verdict"]] += 1
        for dim, verdict in item["dimension_verdicts"].items():
            dimension_counts[dim][verdict] += 1

    return {
        "schema_version": "1.0",
        "feature_key": "bd-bkco.5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_engine": (
            "analysis_pipeline" if PIPELINE_RUNTIME_AVAILABLE else "fixture_only_fallback"
        ),
        "runtime_engine_note": (
            None
            if PIPELINE_RUNTIME_AVAILABLE
            else (
                "AnalysisPipeline runtime unavailable in this environment; "
                f"falling back to fixture-only deterministic comparison ({PIPELINE_RUNTIME_ERROR})."
            )
        ),
        "comparison_scope": {
            "bill_ids_requested": candidate_bill_ids,
            "bills_compared": [item["bill_id"] for item in comparisons],
            "bills_skipped": skipped,
            "fixture_source": "backend/scripts/verification/fixtures/research_fixtures",
        },
        "dimensions": ["final_conclusion", "parameter_resolution", "gate_behavior"],
        "comparisons": comparisons,
        "summary": {
            "overall_counts": overall_counts,
            "dimension_counts": dimension_counts,
        },
    }


def _default_output_path(repo_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        repo_root
        / "backend"
        / "scripts"
        / "verification"
        / "artifacts"
        / f"web_mode_comparison_{stamp}.json"
    )


async def _async_main() -> int:
    parser = argparse.ArgumentParser(
        description="Run with-web vs without-web comparisons for golden fixtures."
    )
    parser.add_argument(
        "--bill-id",
        action="append",
        default=[],
        help="Bill id to include; may be passed multiple times.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output JSON path. Defaults to a timestamped artifacts path.",
    )
    args = parser.parse_args()

    repo_root = BACKEND_ROOT.parent
    requested_ids = args.bill_id if args.bill_id else None
    report = await generate_comparison_report(repo_root, requested_ids)
    output_path = Path(args.output) if args.output else _default_output_path(repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    compared = len(report["comparison_scope"]["bills_compared"])
    skipped = len(report["comparison_scope"]["bills_skipped"])
    print(f"PASS: wrote comparison report to {output_path}")
    print(f"PASS: compared={compared} skipped={skipped}")
    print(f"PASS: overall_counts={report['summary']['overall_counts']}")
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
