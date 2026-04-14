#!/usr/bin/env python3
"""Source expansion/API-key readiness matrix verifier (bd-2agbe.12)."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FEATURE_KEY = "bd-2agbe.12"
ARTIFACT_VERSION = "2026-04-14.source-expansion-api-key-matrix.v1"

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "source-expansion"
    / "artifacts"
    / "source_expansion_api_key_matrix.json"
)
OUT_MD = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "source-expansion"
    / "artifacts"
    / "source_expansion_api_key_matrix.md"
)

REQUIRED_FIELDS = (
    "source_family",
    "lane",
    "free_status",
    "signup_url",
    "api_key_required",
    "railway_variable_needed",
    "already_configured_assumption",
    "sample_endpoint",
    "api_or_raw_access",
    "economic_value",
    "wave",
    "reason",
)

MATRIX_ROWS: list[dict[str, str]] = [
    {
        "source_family": "legistar_public_api",
        "lane": "structured",
        "free_status": "free_public",
        "signup_url": "none_required",
        "api_key_required": "no",
        "railway_variable_needed": "none",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://webapi.legistar.com/v1/sanjose/matters?$top=5",
        "api_or_raw_access": "api",
        "economic_value": "high",
        "wave": "wave1",
        "reason": "Direct local legislative records; high utility for policy facts and linked artifact refs.",
    },
    {
        "source_family": "ca_leginfo_pubinfo_raw_files",
        "lane": "structured",
        "free_status": "free_public",
        "signup_url": "none_required",
        "api_key_required": "no",
        "railway_variable_needed": "none",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://downloads.leginfo.legislature.ca.gov/pubinfo_daily_Mon.zip",
        "api_or_raw_access": "raw_file",
        "economic_value": "high",
        "wave": "wave1",
        "reason": "Official state feed suitable for deterministic ingestion and canonical document identity.",
    },
    {
        "source_family": "ca_ckan_open_data_api",
        "lane": "structured",
        "free_status": "free_public",
        "signup_url": "none_required",
        "api_key_required": "no",
        "railway_variable_needed": "none",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://data.ca.gov/api/3/action/package_search?rows=3&q=housing+zoning+permit",
        "api_or_raw_access": "api",
        "economic_value": "medium",
        "wave": "wave1",
        "reason": "Free catalog for supplemental policy data; useful but requires dataset-level curation.",
    },
    {
        "source_family": "opendatasoft_public_catalog_api",
        "lane": "structured",
        "free_status": "free_public",
        "signup_url": "none_required",
        "api_key_required": "no",
        "railway_variable_needed": "none",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets?limit=1",
        "api_or_raw_access": "api",
        "economic_value": "medium",
        "wave": "wave2",
        "reason": "API is easy, but policy relevance depends on dataset/jurisdiction bindings not yet curated.",
    },
    {
        "source_family": "official_static_csv_xlsx_raw",
        "lane": "contextual",
        "free_status": "free_public",
        "signup_url": "none_required",
        "api_key_required": "no",
        "railway_variable_needed": "none",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx",
        "api_or_raw_access": "raw_file",
        "economic_value": "low",
        "wave": "backlog",
        "reason": "Good denominators/context; usually not primary evidence for local policy mechanism quantification.",
    },
    {
        "source_family": "arcgis_hub_rest_public",
        "lane": "structured",
        "free_status": "free_public",
        "signup_url": "none_required",
        "api_key_required": "no",
        "railway_variable_needed": "none",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://www.arcgis.com/sharing/rest/search?q=San+Jose+zoning+FeatureServer&f=json",
        "api_or_raw_access": "api",
        "economic_value": "medium",
        "wave": "wave2",
        "reason": "Mechanics proven, but requires policy-specific curation (zoning/parcel/permit) before production use.",
    },
    {
        "source_family": "openstates_plural_api",
        "lane": "structured",
        "free_status": "free_tier_available",
        "signup_url": "https://open.pluralpolicy.com/signup",
        "api_key_required": "yes",
        "railway_variable_needed": "OPENSTATES_API_KEY",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://open.pluralpolicy.com/graphql",
        "api_or_raw_access": "api",
        "economic_value": "medium",
        "wave": "wave2",
        "reason": "Useful structured legislative metadata; key needed for robust rate limits and stable operations.",
    },
    {
        "source_family": "socrata_open_data",
        "lane": "structured",
        "free_status": "free_tier_key_optional_limits",
        "signup_url": "https://dev.socrata.com/",
        "api_key_required": "deferred",
        "railway_variable_needed": "SOCRATA_APP_TOKEN",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://dev.socrata.com/foundry/data.sanjoseca.gov/example",
        "api_or_raw_access": "api",
        "economic_value": "high",
        "wave": "backlog",
        "reason": "Potentially high value where available, but explicitly deferred by user (no signup this wave).",
    },
    {
        "source_family": "private_searxng",
        "lane": "search_provider",
        "free_status": "self_hosted_infra_cost_only",
        "signup_url": "none_required",
        "api_key_required": "no",
        "railway_variable_needed": "SEARXNG_BASE_URL",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://<private-searxng>/search?q=san+jose+meeting+minutes&format=json",
        "api_or_raw_access": "api",
        "economic_value": "high",
        "wave": "wave1",
        "reason": "Primary discovery lane for reader artifacts; not a structured source but critical complement.",
    },
    {
        "source_family": "tavily_search_api",
        "lane": "search_provider",
        "free_status": "free_tier_capped",
        "signup_url": "https://app.tavily.com/sign-in",
        "api_key_required": "yes",
        "railway_variable_needed": "TAVILY_API_KEY",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://api.tavily.com/search",
        "api_or_raw_access": "api",
        "economic_value": "medium",
        "wave": "wave2",
        "reason": "Useful fallback to mitigate SearXNG quality failures; reserve for targeted runs due to quota.",
    },
    {
        "source_family": "exa_search_api",
        "lane": "search_provider",
        "free_status": "free_tier_capped",
        "signup_url": "https://dashboard.exa.ai/",
        "api_key_required": "yes",
        "railway_variable_needed": "EXA_API_KEY",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://api.exa.ai/search",
        "api_or_raw_access": "api",
        "economic_value": "medium",
        "wave": "wave2",
        "reason": "Useful as bakeoff/eval fallback; avoid default routing due to monthly quota limits.",
    },
    {
        "source_family": "granicus_civicplus_boarddocs_portals",
        "lane": "scrape_reader",
        "free_status": "free_public",
        "signup_url": "none_required",
        "api_key_required": "no",
        "railway_variable_needed": "none",
        "already_configured_assumption": "unknown",
        "sample_endpoint": "https://johnscreekga.granicus.com/ViewPublisher.php?view_id=1",
        "api_or_raw_access": "html_pdf_scrape",
        "economic_value": "high",
        "wave": "wave1",
        "reason": "Core local-government artifact lane; no easy structured API, requires scrape+reader pipeline.",
    },
]


@dataclass(frozen=True)
class MatrixConfig:
    out_json: Path
    out_md: Path
    self_check: bool


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _markdown_table(rows: list[dict[str, str]]) -> str:
    header = (
        "| source_family | lane | free_status | api_key_required | railway_variable_needed | "
        "economic_value | wave |\n"
    )
    divider = "|---|---|---|---|---|---|---|\n"
    lines = []
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["source_family"],
                    row["lane"],
                    row["free_status"],
                    row["api_key_required"],
                    row["railway_variable_needed"],
                    row["economic_value"],
                    row["wave"],
                ]
            )
            + " |"
        )
    return header + divider + "\n".join(lines) + "\n"


def _build_actions(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    required_now: list[dict[str, str]] = []
    optional_soon: list[dict[str, str]] = []
    defer: list[dict[str, str]] = []
    do_not_add: list[dict[str, str]] = []

    for row in rows:
        variable = row["railway_variable_needed"]
        if variable == "none":
            continue
        action = {"railway_variable": variable, "source_family": row["source_family"], "reason": row["reason"]}
        if row["wave"] == "wave1":
            required_now.append(action)
            continue
        if row["wave"] == "wave2":
            optional_soon.append(action)
            continue
        if row["wave"] == "backlog" or row["api_key_required"] == "deferred":
            defer.append(action)
            continue
        if row["wave"] == "reject":
            do_not_add.append(action)

    return {
        "required_now": required_now,
        "optional_soon": optional_soon,
        "defer": defer,
        "do_not_add": do_not_add,
    }


def _mapping_note() -> dict[str, str]:
    return {
        "mechanism_family_strategy": (
            "Source expansion does not change canonical MechanismFamily or ImpactMode ownership. "
            "Those mappings stay backend-authored in economic analysis contracts."
        ),
        "impact_mode_strategy": (
            "New sources broaden evidence availability but must map into existing deterministic "
            "parameterization and assumption gates, not introduce ad-hoc per-source impact logic."
        ),
        "key_strategy": (
            "No new API key is required for wave1 structured/scrape baseline. "
            "Use OPENSTATES_API_KEY/TAVILY_API_KEY/EXA_API_KEY only when enabling wave2 lanes; "
            "keep SOCRATA_APP_TOKEN deferred."
        ),
    }


def _build_report() -> dict[str, Any]:
    rows = MATRIX_ROWS
    actions = _build_actions(rows)
    return {
        "feature_key": FEATURE_KEY,
        "artifact_version": ARTIFACT_VERSION,
        "generated_at": _now_iso(),
        "matrix": rows,
        "actions": actions,
        "mapping_notes": _mapping_note(),
        "quality_honesty": (
            "Breadth alone is insufficient. A source is wave-eligible only when it can provide "
            "policy facts or linked artifacts that improve evidence cards for deterministic "
            "economic quantification."
        ),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    rows: list[dict[str, str]] = report["matrix"]
    actions: dict[str, list[dict[str, str]]] = report["actions"]
    lines: list[str] = []
    lines.append("# Source Expansion API-Key Matrix")
    lines.append("")
    lines.append(f"- Date: {report['generated_at']}")
    lines.append(f"- Feature key: `{report['feature_key']}`")
    lines.append(f"- Artifact version: `{report['artifact_version']}`")
    lines.append("")
    lines.append("## Matrix")
    lines.append("")
    lines.append(_markdown_table(rows))
    lines.append("## Key Actions")
    lines.append("")
    for section in ("required_now", "optional_soon", "defer", "do_not_add"):
        lines.append(f"### {section}")
        items = actions.get(section, [])
        if not items:
            lines.append("- none")
            lines.append("")
            continue
        for item in items:
            lines.append(
                f"- `{item['railway_variable']}` -> `{item['source_family']}`: {item['reason']}"
            )
        lines.append("")
    lines.append("## Mapping Notes")
    lines.append("")
    mapping_notes: dict[str, str] = report["mapping_notes"]
    lines.append(f"- MechanismFamily: {mapping_notes['mechanism_family_strategy']}")
    lines.append(f"- ImpactMode: {mapping_notes['impact_mode_strategy']}")
    lines.append(f"- Key strategy: {mapping_notes['key_strategy']}")
    lines.append("")
    lines.append("## Quality Guardrail")
    lines.append("")
    lines.append(f"- {report['quality_honesty']}")
    lines.append("")
    return "\n".join(lines)


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_markdown(report), encoding="utf-8")


def _validate(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    matrix = report.get("matrix")
    if not isinstance(matrix, list) or not matrix:
        errors.append("matrix_missing_or_empty")
        return errors

    for idx, row in enumerate(matrix):
        if not isinstance(row, dict):
            errors.append(f"matrix_row_not_object:{idx}")
            continue
        for field in REQUIRED_FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"row_missing_field:{idx}:{field}")

        lane = row.get("lane")
        if lane not in {"structured", "scrape_reader", "search_provider", "contextual"}:
            errors.append(f"invalid_lane:{idx}:{lane}")
        api_key_required = row.get("api_key_required")
        if api_key_required not in {"yes", "no", "optional", "deferred"}:
            errors.append(f"invalid_api_key_required:{idx}:{api_key_required}")
        wave = row.get("wave")
        if wave not in {"wave1", "wave2", "backlog", "reject"}:
            errors.append(f"invalid_wave:{idx}:{wave}")
        economic_value = row.get("economic_value")
        if economic_value not in {"high", "medium", "low", "none"}:
            errors.append(f"invalid_economic_value:{idx}:{economic_value}")

    actions = report.get("actions")
    if not isinstance(actions, dict):
        errors.append("actions_missing")
    else:
        for key in ("required_now", "optional_soon", "defer", "do_not_add"):
            if key not in actions or not isinstance(actions[key], list):
                errors.append(f"actions_missing_section:{key}")
    return errors


def _run(config: MatrixConfig) -> dict[str, Any]:
    report = _build_report()
    _write_json(config.out_json, report)
    _write_markdown(config.out_md, report)
    return report


def _parse_args() -> MatrixConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=OUT_MD)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    return MatrixConfig(
        out_json=args.out_json,
        out_md=args.out_md,
        self_check=bool(args.self_check),
    )


def main() -> int:
    config = _parse_args()
    report = _run(config)
    if not config.self_check:
        return 0
    errors = _validate(report)
    if errors:
        print("SELF_CHECK_FAIL")
        for item in errors:
            print(f"- {item}")
        return 1
    print("SELF_CHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
