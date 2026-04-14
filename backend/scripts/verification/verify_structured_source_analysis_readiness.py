#!/usr/bin/env python3
"""Structured-source economic readiness overlay verifier.

This verifier reads a structured-source probe artifact and emits a deterministic
overlay answering:
- what can become policy facts directly from structured records,
- what still requires linked artifact reader extraction,
- what can seed second-round economic research,
- whether first no-key POC scope is sufficient for wave-1 implementation.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FEATURE_KEY = "bd-2agbe.1"
VERIFIER_VERSION = "2026-04-14.structured-source-overlay-v1"

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_PROBE_REPORT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "structured-source-lane"
    / "artifacts"
    / "structured_source_lane_poc_report.json"
)
DEFAULT_OUT_JSON = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "structured-source-lane"
    / "artifacts"
    / "structured_source_economic_readiness_overlay.json"
)
DEFAULT_OUT_MD = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "structured-source-lane"
    / "artifacts"
    / "structured_source_economic_readiness_overlay.md"
)

NO_KEY_SCOPE = (
    "ca_pubinfo_leginfo",
    "legistar_sanjose",
    "arcgis_public_gis_dataset",
)

STRUCTURED_LANE_FAMILIES = {
    "openstates_ca",
    "ca_pubinfo_leginfo",
    "legistar_sanjose",
    "arcgis_public_gis_dataset",
    "socrata_public_dataset",
    "ckan_public_dataset",
    "opendatasoft_public_dataset",
    "static_official_csv_xlsx",
}

SOURCE_FAMILY_ALIASES = {
    "ca_leginfo_pubinfo": "ca_pubinfo_leginfo",
    "legistar_web_api": "legistar_sanjose",
    "arcgis_rest_public": "arcgis_public_gis_dataset",
    "arcgis_public_planning_dataset": "arcgis_public_gis_dataset",
}

BACKLOG_SOURCE_FAMILIES = {
    "granicus_public_pages",
    "civicplus_agenda_center",
    "boarddocs_public_portal",
    "novusagenda_public_portal",
    "primegov_public_portal",
    "swagit_public_archive",
    "escribe_public_filestream",
    "opengov_budget_book",
    "cleargov_budget_book",
}

SOURCE_FACT_MAP: dict[str, list[str]] = {
    "openstates_ca": [
        "jurisdiction",
        "bill_identifier",
        "session",
        "bill_title",
        "bill_status",
        "actions[]",
        "sponsors[]",
        "source_urls[]",
    ],
    "ca_pubinfo_leginfo": [
        "session_year",
        "bill_number",
        "bill_version",
        "bill_status",
        "history_actions[]",
        "committee_analysis_refs[]",
        "vote_rows[]",
    ],
    "legistar_sanjose": [
        "matter_id",
        "matter_file",
        "matter_guid",
        "matter_title",
        "matter_status",
        "matter_intro_date",
        "agenda_refs[]",
        "minutes_refs[]",
    ],
    "arcgis_public_gis_dataset": [
        "dataset_id",
        "layer_id",
        "objectid",
        "jurisdiction",
        "gis_attribute_code",
        "geometry_or_area_measure",
        "update_timestamp",
    ],
    "socrata_public_dataset": [
        "dataset_id",
        "row_id_or_primary_key",
        "jurisdiction",
        "field_schema",
        "reporting_period",
        "last_modified",
    ],
}

SOURCE_READER_REQUIREMENTS: dict[str, list[str]] = {
    "openstates_ca": [
        "Follow source_urls[] to official bill text/analysis documents.",
        "Reader required for committee analyses and fiscal-note PDFs when not already in structured payload.",
    ],
    "ca_pubinfo_leginfo": [
        "Reader required for linked bill text/analysis pages when downstream model needs clause-level evidence excerpts.",
    ],
    "legistar_sanjose": [
        "Reader required for agenda packet PDFs, minutes attachments, and staff reports linked from Matter records.",
    ],
    "arcgis_public_gis_dataset": [
        "Reader optional for ordinance, staff-report, or metadata links referenced in feature attributes.",
    ],
    "socrata_public_dataset": [
        "Reader optional for external reference URLs included in records.",
    ],
}

SOURCE_RESEARCH_SEEDS: dict[str, list[str]] = {
    "openstates_ca": [
        "query: \"{bill_identifier} fiscal impact analysis\"",
        "query: \"{bill_identifier} cost estimate legislative analyst\"",
        "query: \"{policy_mechanism} pass-through incidence literature\"",
    ],
    "ca_pubinfo_leginfo": [
        "query: \"{bill_number} committee analysis fiscal\"",
        "query: \"{bill_number} implementation cost estimate\"",
        "query: \"{policy_mechanism} compliance cost evidence\"",
    ],
    "legistar_sanjose": [
        "query: \"San Jose {matter_file} staff report fiscal impact\"",
        "query: \"San Jose {policy_mechanism} implementation cost\"",
        "query: \"{policy_mechanism} housing price impact literature\"",
    ],
    "arcgis_public_gis_dataset": [
        "query: \"{jurisdiction} development cost benchmark\"",
        "query: \"{gis_attribute_code} housing supply or development feasibility impact\"",
        "query: \"{policy_mechanism} household affordability impact\"",
    ],
}


@dataclass(frozen=True)
class VerifierConfig:
    probe_report: Path
    out_json: Path
    out_md: Path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _normalize_source_name(raw: str) -> str:
    normalized = raw.strip().lower().replace("-", "_").replace(" ", "_")
    return SOURCE_FAMILY_ALIASES.get(normalized, normalized)


def _sources_from_probe_report(probe_report: dict[str, Any]) -> list[dict[str, Any]]:
    """Accept both the normalized catalog and the raw live-probe report shape."""
    sources = probe_report.get("sources")
    if isinstance(sources, list):
        return [item for item in sources if isinstance(item, dict)]

    probes = probe_report.get("probes")
    if not isinstance(probes, dict):
        return []

    normalized: list[dict[str, Any]] = []
    for probe_id, family, endpoint_getter in (
        ("leginfo", "ca_pubinfo_leginfo", lambda item: "https://downloads.leginfo.legislature.ca.gov/pubinfo_daily_Mon.zip"),
        ("legistar", "legistar_sanjose", lambda item: item.get("endpoint")),
        (
            "arcgis",
            "arcgis_public_gis_dataset",
            lambda item: (
                item.get("selected", {}).get("query_url")
                if isinstance(item.get("selected"), dict)
                else None
            ),
        ),
    ):
        probe = probes.get(probe_id, {})
        if not isinstance(probe, dict):
            continue
        normalized.append(
            {
                "source_family": family,
                "probe_id": probe_id,
                "signup_or_key_link": "none_required",
                "free_status": "free_public",
                "api_or_raw_confirmed": "raw_official_file" if probe_id == "leginfo" else "api",
                "sample_endpoint_or_file_url": endpoint_getter(probe),
                "auth_required": "no",
                "recommendation": (
                    "structured_lane"
                    if probe.get("sample_pull_without_browser") is True
                    else "blocked"
                ),
                "probe_status": probe.get("status", "fail"),
            }
        )
    return normalized


def _build_source_overlay(source: dict[str, Any]) -> dict[str, Any]:
    family = _normalize_source_name(str(source.get("source_family", "")))
    recommendation = str(source.get("recommendation", "")).strip().lower()
    facts = SOURCE_FACT_MAP.get(family, [])
    reader_requirements = SOURCE_READER_REQUIREMENTS.get(
        family,
        ["Reader requirements not yet mapped; treat linked documents as required until classified."],
    )
    research_seeds = SOURCE_RESEARCH_SEEDS.get(
        family,
        ["query: \"{policy_mechanism} economic impact literature\""],
    )
    return {
        "source_family": family,
        "recommendation": recommendation,
        "signup_or_key_link": source.get("signup_or_key_link"),
        "free_status": source.get("free_status"),
        "api_or_raw_confirmed": source.get("api_or_raw_confirmed"),
        "sample_endpoint_or_file_url": source.get("sample_endpoint_or_file_url"),
        "policy_fact_fields": facts,
        "requires_reader_for_linked_artifacts": reader_requirements,
        "economic_research_seed_queries": research_seeds,
        "ready_for_structured_lane": (
            recommendation == "structured_lane" and family in STRUCTURED_LANE_FAMILIES
        ),
    }


def _compare_pipeline_paths() -> dict[str, Any]:
    return {
        "thin_windmill_domain_path": {
            "entrypoint": "backend/main.py:521 (/cron/pipeline/domain/run-scope)",
            "search_read_analyze_steps": [
                "backend/services/pipeline/domain/bridge.py:479 (_search_materialize)",
                "backend/services/pipeline/domain/bridge.py:635 (_read_fetch)",
                "backend/services/pipeline/domain/bridge.py:1127 (_analyze)",
            ],
            "analysis_behavior": (
                "Analyze step prompts LLM for strict JSON with keys: summary, key_points, "
                "sufficiency_state over selected evidence chunks."
            ),
            "citation": "backend/services/pipeline/domain/bridge.py:1204",
        },
        "canonical_analysis_pipeline_path": {
            "entrypoint": "backend/main.py:258 (AnalysisPipeline construction)",
            "research_invocation": "backend/services/llm/orchestrator.py:1126 (_research_step)",
            "research_behavior": [
                "backend/services/legislation_research.py:260 (research)",
                "backend/services/legislation_research.py:405 (_web_research)",
                "backend/services/legislation_research.py:743 (_derive_wave1_candidates)",
                "backend/services/legislation_research.py:794 (_derive_wave2_prerequisites)",
            ],
            "generation_behavior": "backend/services/llm/orchestrator.py:1248 (_generate_step)",
        },
        "current_disconnect": (
            "Windmill domain bridge analyze path does not call AnalysisPipeline or "
            "LegislationResearchService directly; it runs a thin question-over-chunks analysis."
        ),
        "handoff_boundary": (
            "Structured-source lane should publish policy facts + linked artifact refs into "
            "backend-owned evidence contracts, then invoke canonical AnalysisPipeline for "
            "economic research and quantification gating."
        ),
    }


def _evaluate_no_key_scope(sources: list[dict[str, Any]]) -> dict[str, Any]:
    indexed = {item.get("source_family"): item for item in sources}
    missing = [family for family in NO_KEY_SCOPE if family not in indexed]
    present = [family for family in NO_KEY_SCOPE if family in indexed]
    structured_ready = [
        family
        for family in present
        if bool(indexed[family].get("ready_for_structured_lane"))
    ]

    sufficient = not missing and len(structured_ready) == len(NO_KEY_SCOPE)
    return {
        "required_source_families": list(NO_KEY_SCOPE),
        "present_source_families": present,
        "missing_source_families": missing,
        "structured_ready_source_families": structured_ready,
        "sufficient_for_wave1": sufficient,
        "reason": (
            "no_key_scope_ready_for_wave1"
            if sufficient
            else "missing_or_not_ready_no_key_scope_sources"
        ),
    }


def _render_markdown(report: dict[str, Any], config: VerifierConfig) -> str:
    lines: list[str] = []
    lines.append("# Structured Source Economic Readiness Overlay")
    lines.append("")
    lines.append(f"- feature_key: `{FEATURE_KEY}`")
    lines.append(f"- verifier_version: `{VERIFIER_VERSION}`")
    lines.append(f"- generated_at: `{report['generated_at']}`")
    lines.append(f"- probe_report: `{_repo_display_path(config.probe_report)}`")
    lines.append("")
    lines.append("## No-Key Scope Verdict")
    lines.append("")
    scope = report["no_key_scope_verdict"]
    lines.append(f"- sufficient_for_wave1: `{scope['sufficient_for_wave1']}`")
    lines.append(f"- reason: `{scope['reason']}`")
    lines.append(f"- present_source_families: `{scope['present_source_families']}`")
    lines.append(f"- missing_source_families: `{scope['missing_source_families']}`")
    lines.append("")
    lines.append("## Source Overlay")
    lines.append("")
    lines.append("| source_family | structured_ready | policy_fact_field_count | reader_handoff_count | seed_query_count |")
    lines.append("|---|---:|---:|---:|---:|")
    for item in report["source_overlay"]:
        lines.append(
            "| {family} | {ready} | {facts} | {reader} | {seeds} |".format(
                family=item["source_family"],
                ready="yes" if item["ready_for_structured_lane"] else "no",
                facts=len(item["policy_fact_fields"]),
                reader=len(item["requires_reader_for_linked_artifacts"]),
                seeds=len(item["economic_research_seed_queries"]),
            )
        )
    lines.append("")
    lines.append("## Path Comparison")
    lines.append("")
    compare = report["pipeline_path_comparison"]
    lines.append("- thin_windmill_domain_path entrypoint: `{}`".format(compare["thin_windmill_domain_path"]["entrypoint"]))
    lines.append("- canonical_analysis_pipeline_path entrypoint: `{}`".format(compare["canonical_analysis_pipeline_path"]["entrypoint"]))
    lines.append(f"- current_disconnect: `{compare['current_disconnect']}`")
    lines.append(f"- handoff_boundary: `{compare['handoff_boundary']}`")
    lines.append("")
    lines.append("## Backlog Preserved")
    lines.append("")
    lines.append(
        "- Sources intentionally kept in scrape/reader backlog for this POC: "
        f"`{report['scrape_reader_backlog_source_families']}`"
    )
    lines.append(
        "- Rationale: first POC validates boundary across three no-key structured shapes "
        "(state feed, local legislative API, public GIS dataset) before broad adapter expansion."
    )
    return "\n".join(lines) + "\n"


def run(config: VerifierConfig) -> dict[str, Any]:
    probe_report = _load_json(config.probe_report)
    raw_sources = _sources_from_probe_report(probe_report)
    if not raw_sources:
        raise ValueError("probe report must contain normalized 'sources' or raw 'probes'")

    overlays = [_build_source_overlay(item) for item in raw_sources if isinstance(item, dict)]
    scope_verdict = _evaluate_no_key_scope(overlays)

    report = {
        "feature_key": FEATURE_KEY,
        "verifier_version": VERIFIER_VERSION,
        "generated_at": _now_iso(),
        "probe_report_summary": {
            "source_count": len(raw_sources),
            "structured_lane_candidates": sum(
                1 for item in overlays if item.get("ready_for_structured_lane")
            ),
        },
        "source_overlay": overlays,
        "no_key_scope_verdict": scope_verdict,
        "pipeline_path_comparison": _compare_pipeline_paths(),
        "scrape_reader_backlog_source_families": sorted(BACKLOG_SOURCE_FAMILIES),
    }

    config.out_json.parent.mkdir(parents=True, exist_ok=True)
    config.out_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    config.out_md.write_text(_render_markdown(report, config), encoding="utf-8")
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe-report",
        type=Path,
        default=DEFAULT_PROBE_REPORT,
        help="Path to structured source probe artifact JSON.",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=DEFAULT_OUT_JSON,
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=DEFAULT_OUT_MD,
        help="Output markdown report path.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    config = VerifierConfig(
        probe_report=args.probe_report,
        out_json=args.out_json,
        out_md=args.out_md,
    )
    report = run(config)
    print(
        json.dumps(
            {
                "status": "ok",
                "feature_key": FEATURE_KEY,
                "source_count": report["probe_report_summary"]["source_count"],
                "structured_lane_candidates": report["probe_report_summary"][
                    "structured_lane_candidates"
                ],
                "sufficient_for_wave1": report["no_key_scope_verdict"][
                    "sufficient_for_wave1"
                ],
                "out_json": _repo_display_path(config.out_json),
                "out_md": _repo_display_path(config.out_md),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
