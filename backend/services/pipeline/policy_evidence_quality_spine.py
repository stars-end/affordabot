"""Data-quality matrix and runtime harness for bd-3wefe.13 (Agent A slice)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import subprocess
import sys
from statistics import mean
from pathlib import Path
from typing import Any

from schemas.analysis import ScenarioBounds
from schemas.economic_evidence import UnitValidationStatus
from services.pipeline.policy_evidence_package_builder import PolicyEvidencePackageBuilder
from services.pipeline.policy_evidence_package_storage import (
    InMemoryArtifactProbe,
    InMemoryArtifactWriter,
    InMemoryPolicyEvidencePackageStore,
    PolicyEvidencePackageStorageService,
)

READINESS_QUANTIFIED = "quantified_ready"
READINESS_SECONDARY = "secondary_research_needed"
READINESS_QUAL = "qualitative_only"
READINESS_FAIL = "fail_closed"

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
WINDMILL_ORCHESTRATION_REPORT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-package-windmill"
    / "artifacts"
    / "policy_evidence_package_windmill_orchestration_report.json"
)


def _attach_quality_spine_model(package_payload: dict[str, Any], *, mechanism_family: str) -> dict[str, Any]:
    """Attach a deterministic model projection for the vertical quality-spine proof."""
    if not package_payload.get("economic_handoff_ready"):
        return package_payload

    parameter_ids = [
        card["id"]
        for card in package_payload.get("parameter_cards", [])
        if card.get("state") == "resolved"
    ]
    if not parameter_ids:
        return package_payload

    assumption_ids = [card["id"] for card in package_payload.get("assumption_cards", [])]
    package_payload = dict(package_payload)
    package_payload["assumption_usage"] = [
        {
            "assumption_id": assumption_id,
            "used_for_quantitative_claim": True,
            "applicable": True,
            "stale": False,
        }
        for assumption_id in assumption_ids
    ]
    package_payload["model_cards"] = [
        {
            "id": "model-quality-spine-vertical-1",
            "mechanism_family": mechanism_family,
            "formula_id": f"{mechanism_family}.quality_spine_projection.v1",
            "input_parameter_ids": parameter_ids,
            "assumption_ids": assumption_ids,
            "scenario_bounds": ScenarioBounds(
                conservative=1200.0,
                central=1800.0,
                aggressive=2600.0,
            ).model_dump(mode="json"),
            "arithmetic_valid": True,
            "unit_validation_status": UnitValidationStatus.VALID.value,
            "quantification_eligible": True,
            "failure_codes": [],
        }
    ]
    return package_payload


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _maybe_refresh_windmill_report(live_mode: str) -> tuple[str, str | None]:
    if live_mode != "auto":
        return "not_attempted", None

    cmd = [
        sys.executable,
        "scripts/verification/verify_policy_evidence_package_windmill_orchestration.py",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(BACKEND_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "attempted", "windmill_verifier_execution_failed"
    if proc.returncode == 0:
        return "attempted", None
    stderr_text = proc.stderr.strip()
    if "live_windmill_auth_or_cli_unavailable_noninteractive" in stderr_text:
        return "attempted", "live_windmill_auth_or_cli_unavailable_noninteractive"
    if "Flow not found" in stderr_text:
        return "attempted", "flow_not_deployed_in_windmill_workspace"
    return "attempted", "windmill_verifier_execution_failed"


def _build_orchestration_proof(*, package_id: str, live_mode: str) -> dict[str, Any]:
    verifier_attempt, verifier_blocker = _maybe_refresh_windmill_report(live_mode)
    report = _safe_load_json(WINDMILL_ORCHESTRATION_REPORT)

    base = {
        "windmill_flow_path": "f/affordabot/policy_evidence_package_orchestration__flow",
        "windmill_run_id": None,
        "windmill_job_id": None,
        "backend_command_id": None,
        "package_id": package_id,
        "source": "quality_spine_runtime",
        "proof_mode": "none",
        "proof_status": "blocked",
        "blocker": "windmill_orchestration_report_missing",
        "historical_stub_flow_proof": None,
        "linked_to_current_vertical_package": False,
        "verifier_attempt": verifier_attempt,
    }

    if report is None:
        if verifier_blocker:
            base["blocker"] = verifier_blocker
        return base

    historical_stub = {
        "feature_key": report.get("feature_key"),
        "report_version": report.get("report_version"),
        "generated_at": report.get("generated_at"),
        "live_status": report.get("live_status"),
        "local_status": report.get("local_status"),
        "local_backend_endpoint_status": report.get("local_backend_endpoint_status"),
        "backend_endpoint_package_id": (report.get("backend_endpoint_local_path") or {}).get("package_id"),
        "stub_run_result": (report.get("live_surface_probe") or {}).get("stub_run_result"),
    }

    backend_package_id = (report.get("backend_endpoint_local_path") or {}).get("package_id")
    stub_package_id = ((report.get("live_surface_probe") or {}).get("stub_run_result") or {}).get("package_id")
    linked = package_id in {backend_package_id, stub_package_id}

    base.update(
        {
            "source": str(WINDMILL_ORCHESTRATION_REPORT.relative_to(REPO_ROOT)),
            "proof_mode": "historical_stub_flow_proof",
            "proof_status": "not_proven",
            "blocker": "windmill_proof_not_linked_to_current_vertical_package",
            "historical_stub_flow_proof": historical_stub,
            "linked_to_current_vertical_package": linked,
        }
    )

    if linked:
        base["proof_status"] = "not_proven"
        base["blocker"] = "historical_stub_not_current_live_run"
    elif verifier_blocker:
        base["proof_status"] = "blocked"
        base["blocker"] = verifier_blocker
    return base


@dataclass(frozen=True)
class ProviderCandidate:
    provider: str
    rank: int
    url: str
    title: str
    artifact_grade: bool
    official_domain: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "rank": self.rank,
            "url": self.url,
            "title": self.title,
            "artifact_grade": self.artifact_grade,
            "official_domain": self.official_domain,
        }


def _case_fixtures() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "sj-parking-minimum-amendment",
            "title": "San Jose multifamily parking minimum amendment",
            "jurisdiction": "san_jose_ca",
            "mechanism_family": "compliance_cost",
            "policy_surface": "legistar + planning code",
            "source_provenance": {
                "artifact_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=13050001&GUID=PK-1",
                "artifact_url_source": "linked",
                "canonical_document_key_source": "fixture-derived",
                "structured_facts_source": "observed",
                "reader_source": "observed",
            },
            "provider_results": {
                "private_searxng": {
                    "status": "strong",
                    "reason_code": "artifact_top3",
                    "candidates": [
                        ProviderCandidate(
                            provider="private_searxng",
                            rank=1,
                            url="https://sanjoseca.gov/your-government/agendas-minutes",
                            title="Agendas and Minutes",
                            artifact_grade=False,
                            official_domain=True,
                        ),
                        ProviderCandidate(
                            provider="private_searxng",
                            rank=2,
                            url="https://sanjose.legistar.com/MeetingDetail.aspx?ID=13050001&GUID=PK-1",
                            title="Meeting Detail",
                            artifact_grade=True,
                            official_domain=True,
                        ),
                        ProviderCandidate(
                            provider="private_searxng",
                            rank=3,
                            url="https://sanjose.legistar.com/View.ashx?M=F&ID=13050001&GUID=PK-1",
                            title="Staff Report PDF",
                            artifact_grade=True,
                            official_domain=True,
                        ),
                    ],
                },
                "tavily_fallback": {"executed": True, "reason_code": "searx_portal_top1", "status": "improved"},
                "exa_eval": {"executed": False, "reason_code": "subset_cap_not_selected"},
            },
            "selected_candidate": {
                "provider": "tavily",
                "rank": 1,
                "url": "https://sanjose.legistar.com/View.ashx?M=F&ID=13050001&GUID=PK-1",
                "selection_reason": "artifact_pdf_after_portal_penalty",
            },
            "reader_status": {
                "status": "passed",
                "reason_code": "substantive_minutes_actions_detected",
                "reader_artifact_refs": ["https://backend.artifacts/scrape/sj-parking-minimum-reader.txt"],
            },
            "structured_enrichment": {
                "status": "enriched",
                "source_family": "legistar",
                "access_method": "public_api",
                "endpoint_or_file_url": "https://webapi.legistar.com/v1/sanjose/events/13050001",
                "facts": [
                    {"field": "required_parking_spaces_per_unit", "value": 1.0, "unit": "spaces_per_unit"},
                    {"field": "affected_project_units", "value": 3200, "unit": "units"},
                ],
            },
        },
        {
            "case_id": "sj-planning-fee-schedule",
            "title": "San Jose planning and permit fee schedule update",
            "jurisdiction": "san_jose_ca",
            "mechanism_family": "fee_or_tax_pass_through",
            "policy_surface": "city fee schedule",
            "source_provenance": {
                "artifact_url": "https://www.sanjoseca.gov/home/showdocument?id=112345",
                "artifact_url_source": "observed",
                "canonical_document_key_source": "fixture-derived",
                "structured_facts_source": "observed",
                "reader_source": "observed",
            },
            "provider_results": {
                "private_searxng": {
                    "status": "strong",
                    "reason_code": "artifact_top2",
                    "candidates": [
                        ProviderCandidate(
                            provider="private_searxng",
                            rank=1,
                            url="https://www.sanjoseca.gov/your-government/departments-offices/planning-building-code-enforcement/planning-division/planning-fees",
                            title="Planning Fees Portal",
                            artifact_grade=False,
                            official_domain=True,
                        ),
                        ProviderCandidate(
                            provider="private_searxng",
                            rank=2,
                            url="https://www.sanjoseca.gov/home/showdocument?id=112345",
                            title="Fee Schedule PDF",
                            artifact_grade=True,
                            official_domain=True,
                        ),
                    ],
                },
                "tavily_fallback": {"executed": False, "reason_code": "searx_artifact_sufficient", "status": "not_needed"},
                "exa_eval": {"executed": True, "reason_code": "eval_subset_row", "status": "neutral"},
            },
            "selected_candidate": {
                "provider": "private_searxng",
                "rank": 2,
                "url": "https://www.sanjoseca.gov/home/showdocument?id=112345",
                "selection_reason": "artifact_boost_pdf",
            },
            "reader_status": {
                "status": "passed",
                "reason_code": "contains_fee_tables_and_effective_date",
                "reader_artifact_refs": ["https://backend.artifacts/scrape/sj-planning-fees-reader.txt"],
            },
            "structured_enrichment": {
                "status": "enriched",
                "source_family": "ckan",
                "access_method": "api",
                "endpoint_or_file_url": "https://data.sanjoseca.gov/api/3/action/package_show?id=permit-fees",
                "facts": [
                    {"field": "average_fee_increase_pct", "value": 0.12, "unit": "ratio"},
                    {"field": "annual_permits", "value": 1800, "unit": "permits_per_year"},
                ],
            },
        },
        {
            "case_id": "sj-tenant-relocation-assistance",
            "title": "San Jose tenant relocation assistance threshold revision",
            "jurisdiction": "san_jose_ca",
            "mechanism_family": "adoption_take_up",
            "policy_surface": "city ordinance + displacement reports",
            "source_provenance": {
                "artifact_url": "https://sanjose.legistar.com/View.ashx?M=F&ID=13052222&GUID=TR-1",
                "artifact_url_source": "linked",
                "canonical_document_key_source": "fixture-derived",
                "structured_facts_source": "linked",
                "reader_source": "observed",
            },
            "provider_results": {
                "private_searxng": {
                    "status": "ambiguous",
                    "reason_code": "portal_and_press_release_mix",
                    "candidates": [
                        ProviderCandidate(
                            provider="private_searxng",
                            rank=1,
                            url="https://www.sanjoseca.gov/news-stories",
                            title="News and Updates",
                            artifact_grade=False,
                            official_domain=True,
                        ),
                        ProviderCandidate(
                            provider="private_searxng",
                            rank=2,
                            url="https://sanjose.legistar.com/View.ashx?M=F&ID=13052222&GUID=TR-1",
                            title="Relocation Assistance Staff Report",
                            artifact_grade=True,
                            official_domain=True,
                        ),
                    ],
                },
                "tavily_fallback": {"executed": True, "reason_code": "ambiguity_guardrail", "status": "improved"},
                "exa_eval": {"executed": False, "reason_code": "subset_cap_not_selected"},
            },
            "selected_candidate": {
                "provider": "tavily",
                "rank": 1,
                "url": "https://sanjose.legistar.com/View.ashx?M=F&ID=13052222&GUID=TR-1",
                "selection_reason": "artifact_selected_after_ambiguity",
            },
            "reader_status": {
                "status": "passed",
                "reason_code": "contains eligibility and payout schedule",
                "reader_artifact_refs": ["https://backend.artifacts/scrape/sj-relocation-reader.txt"],
            },
            "structured_enrichment": {
                "status": "partial",
                "source_family": "openstates",
                "access_method": "api_with_key",
                "endpoint_or_file_url": "https://v3.openstates.org/bills?jurisdiction=California",
                "facts": [{"field": "related_state_bill_count", "value": 2, "unit": "count"}],
            },
        },
        {
            "case_id": "ca-ab-2533-embodied-carbon",
            "title": "California embodied carbon reporting requirement",
            "jurisdiction": "california_state",
            "mechanism_family": "compliance_cost",
            "policy_surface": "LegInfo pubinfo + bill text",
            "source_provenance": {
                "artifact_url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260AB2533",
                "artifact_url_source": "observed",
                "canonical_document_key_source": "fixture-derived",
                "structured_facts_source": "observed",
                "reader_source": "linked",
            },
            "provider_results": {
                "private_searxng": {
                    "status": "strong",
                    "reason_code": "official_bill_text_top1",
                    "candidates": [
                        ProviderCandidate(
                            provider="private_searxng",
                            rank=1,
                            url="https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260AB2533",
                            title="AB-2533 Bill Text",
                            artifact_grade=True,
                            official_domain=True,
                        )
                    ],
                },
                "tavily_fallback": {"executed": False, "reason_code": "searx_artifact_sufficient", "status": "not_needed"},
                "exa_eval": {"executed": True, "reason_code": "eval_subset_row", "status": "neutral"},
            },
            "selected_candidate": {
                "provider": "private_searxng",
                "rank": 1,
                "url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260AB2533",
                "selection_reason": "official_bill_text",
            },
            "reader_status": {
                "status": "passed",
                "reason_code": "bill sections parsed",
                "reader_artifact_refs": ["https://backend.artifacts/scrape/ca-ab2533-reader.txt"],
            },
            "structured_enrichment": {
                "status": "enriched",
                "source_family": "leginfo",
                "access_method": "public_raw_files",
                "endpoint_or_file_url": "https://downloads.leginfo.legislature.ca.gov/pubinfo_daily_Tue.zip",
                "facts": [
                    {"field": "compliance_deadline_year", "value": 2028, "unit": "year"},
                    {"field": "reporting_entities", "value": 1250, "unit": "entities"},
                ],
            },
        },
        {
            "case_id": "ca-sb-684-lot-split",
            "title": "California lot split streamlining bill",
            "jurisdiction": "california_state",
            "mechanism_family": "adoption_take_up",
            "policy_surface": "state bill + permit context",
            "source_provenance": {
                "artifact_url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260SB684",
                "artifact_url_source": "observed",
                "canonical_document_key_source": "fixture-derived",
                "structured_facts_source": "linked",
                "reader_source": "observed",
            },
            "provider_results": {
                "private_searxng": {
                    "status": "weak",
                    "reason_code": "official_hit_rank_gt3",
                    "candidates": [
                        ProviderCandidate(
                            provider="private_searxng",
                            rank=1,
                            url="https://ballotpedia.org/California_SB684",
                            title="SB684 summary",
                            artifact_grade=False,
                            official_domain=False,
                        ),
                        ProviderCandidate(
                            provider="private_searxng",
                            rank=4,
                            url="https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260SB684",
                            title="SB-684 Bill Text",
                            artifact_grade=True,
                            official_domain=True,
                        ),
                    ],
                },
                "tavily_fallback": {"executed": True, "reason_code": "weak_rank_guardrail", "status": "improved"},
                "exa_eval": {"executed": False, "reason_code": "subset_cap_not_selected"},
            },
            "selected_candidate": {
                "provider": "tavily",
                "rank": 1,
                "url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260SB684",
                "selection_reason": "fallback_promoted_official_text",
            },
            "reader_status": {
                "status": "passed",
                "reason_code": "policy sections and eligibility parsed",
                "reader_artifact_refs": ["https://backend.artifacts/scrape/ca-sb684-reader.txt"],
            },
            "structured_enrichment": {
                "status": "partial",
                "source_family": "arcgis",
                "access_method": "public_rest_api",
                "endpoint_or_file_url": "https://services.arcgis.com/example/housing-permits/FeatureServer/0/query",
                "facts": [{"field": "permit_latency_months", "value": 11.0, "unit": "months"}],
            },
        },
        {
            "case_id": "scc-impact-fee-adjustment",
            "title": "Santa Clara County impact fee adjustment memo",
            "jurisdiction": "santa_clara_county_ca",
            "mechanism_family": "fee_or_tax_pass_through",
            "policy_surface": "county memo portal",
            "source_provenance": {
                "artifact_url": "https://sccgov.org/sites/ceo/impact-fee-memos",
                "artifact_url_source": "blocked",
                "canonical_document_key_source": "fixture-derived",
                "structured_facts_source": "blocked",
                "reader_source": "blocked",
            },
            "provider_results": {
                "private_searxng": {
                    "status": "weak",
                    "reason_code": "portal_only",
                    "candidates": [
                        ProviderCandidate(
                            provider="private_searxng",
                            rank=1,
                            url="https://sccgov.org/sites/ceo/impact-fee-memos",
                            title="Impact Fee Memos",
                            artifact_grade=False,
                            official_domain=True,
                        )
                    ],
                },
                "tavily_fallback": {"executed": True, "reason_code": "portal_only", "status": "no_improvement"},
                "exa_eval": {"executed": False, "reason_code": "subset_cap_not_selected"},
            },
            "selected_candidate": {
                "provider": "private_searxng",
                "rank": 1,
                "url": "https://sccgov.org/sites/ceo/impact-fee-memos",
                "selection_reason": "only_candidate_portal",
            },
            "reader_status": {
                "status": "failed",
                "reason_code": "prefetch_skipped_low_value_portal",
                "reader_artifact_refs": [],
            },
            "structured_enrichment": {
                "status": "none",
                "source_family": "none",
                "access_method": "none",
                "endpoint_or_file_url": "https://example.invalid/no-structured-source",
                "facts": [],
            },
        },
    ]


def _numeric_fact_count(facts: list[dict[str, Any]]) -> int:
    return sum(1 for fact in facts if isinstance(fact.get("value"), (int, float)))


def _url_is_portal(url: str) -> bool:
    lowered = url.lower()
    portal_signals = (
        "/agendas-minutes",
        "/resource-library",
        "/news-stories",
        "planning-fees",
        "impact-fee-memos",
        "departmentdetail.aspx",
        "calendar.aspx",
    )
    return any(signal in lowered for signal in portal_signals)


def _url_artifact_grade(url: str) -> bool:
    lowered = url.lower()
    artifact_signals = (
        "view.ashx?m=f",
        "meetingdetail.aspx",
        "billtextclient.xhtml",
        "showdocument",
        ".pdf",
    )
    return any(signal in lowered for signal in artifact_signals)


def _url_official_domain(url: str) -> bool:
    lowered = url.lower()
    return any(
        domain in lowered
        for domain in (
            "sanjose.legistar.com",
            "sanjoseca.gov",
            "leginfo.legislature.ca.gov",
            "sccgov.org",
        )
    )


def _selected_artifact_quality(case: dict[str, Any]) -> dict[str, Any]:
    selected = case["selected_candidate"]
    selected_url = str(selected["url"])
    selected_rank = int(selected.get("rank") or 1)
    candidate_list = case["provider_results"]["private_searxng"]["candidates"]

    matched_candidate = next(
        (
            candidate
            for candidate in candidate_list
            if candidate.url == selected_url and int(candidate.rank) == selected_rank
        ),
        None,
    )

    official_domain = matched_candidate.official_domain if matched_candidate else _url_official_domain(selected_url)
    artifact_grade = matched_candidate.artifact_grade if matched_candidate else _url_artifact_grade(selected_url)
    portal_selected = _url_is_portal(selected_url)

    searx_status = case["provider_results"]["private_searxng"]["status"]
    searx_base = {"strong": 80.0, "ambiguous": 60.0, "weak": 45.0}.get(searx_status, 50.0)
    score = searx_base
    if artifact_grade:
        score += 10.0
    if official_domain:
        score += 5.0
    if portal_selected:
        score -= 20.0
    score += 5.0 if case["reader_status"]["status"] == "passed" else -20.0
    score = max(0.0, min(100.0, score))
    threshold = 70.0

    return {
        "selected_artifact_url": selected_url,
        "selected_artifact_provider": str(selected["provider"]),
        "selected_artifact_rank": selected_rank,
        "selected_artifact_official_domain": official_domain,
        "selected_artifact_artifact_grade": artifact_grade,
        "selected_artifact_is_portal": portal_selected,
        "reader_substance_status": str(case["reader_status"]["status"]),
        "provider_quality_score": round(score, 2),
        "provider_quality_threshold": threshold,
        "provider_quality_status": "pass" if score >= threshold else "weak",
        "metric_source": "fixture_selected_path",
    }


def _choose_readiness(case: dict[str, Any]) -> tuple[str, str]:
    selected_url = str(case["selected_candidate"]["url"]).strip()
    reader_status = case["reader_status"]["status"]
    structured_status = case["structured_enrichment"]["status"]
    numeric_count = _numeric_fact_count(case["structured_enrichment"]["facts"])
    searx_status = case["provider_results"]["private_searxng"]["status"]

    if not selected_url or reader_status == "failed":
        return READINESS_FAIL, "reader_quality"
    if numeric_count > 0 and structured_status in {"enriched", "partial"}:
        if searx_status in {"weak", "ambiguous"} and case["provider_results"]["tavily_fallback"]["executed"]:
            return READINESS_QUANTIFIED, "none"
        if searx_status == "strong":
            return READINESS_QUANTIFIED, "none"
    if reader_status == "passed" and numeric_count == 0 and structured_status == "none":
        return READINESS_SECONDARY, "structured_source_coverage"
    if reader_status == "passed" and numeric_count == 0:
        return READINESS_QUAL, "sufficiency_gate"
    return READINESS_FAIL, "scraped_search_quality"


def _quality_score(readiness: str, reader_status: str, structured_status: str) -> float:
    base = {
        READINESS_QUANTIFIED: 90.0,
        READINESS_SECONDARY: 62.0,
        READINESS_QUAL: 54.0,
        READINESS_FAIL: 28.0,
    }[readiness]
    if reader_status == "failed":
        base -= 8.0
    if structured_status == "none":
        base -= 10.0
    elif structured_status == "partial":
        base -= 4.0
    return max(0.0, min(100.0, base))


def _as_scraped_candidate(case: dict[str, Any]) -> dict[str, Any]:
    selected = case["selected_candidate"]
    reader = case["reader_status"]
    return {
        "source_lane": "scrape_search",
        "provider": selected["provider"],
        "canonical_document_key": f"{case['jurisdiction']}::{case['case_id']}",
        "jurisdiction": case["jurisdiction"],
        "artifact_url": selected["url"],
        "artifact_type": "staff_report",
        "source_tier": "tier_a" if case["provider_results"]["private_searxng"]["status"] == "strong" else "tier_b",
        "content_hash": f"fixture::{case['case_id']}::scraped",
        "retrieved_at": "2026-04-15T00:00:00+00:00",
        "query_text": case["title"],
        "search_snapshot_id": f"snapshot::{case['case_id']}",
        "candidate_rank": int(selected.get("rank") or 1),
        "reader_artifact_refs": list(reader["reader_artifact_refs"]),
        "reader_substance_reason": "ok" if reader["status"] == "passed" else reader["reason_code"],
        "selected_impact_mode": "compliance_cost",
        "mechanism_family": case["mechanism_family"],
        "source_family": "meeting_minutes",
    }


def _as_structured_candidate(case: dict[str, Any]) -> dict[str, Any]:
    structured = case["structured_enrichment"]
    if structured["status"] == "none":
        return {}
    return {
        "source_lane": "structured",
        "provider": structured["source_family"],
        "canonical_document_key": f"{case['jurisdiction']}::{case['case_id']}",
        "jurisdiction": case["jurisdiction"],
        "artifact_url": case["source_provenance"]["artifact_url"],
        "artifact_type": "staff_report",
        "source_tier": "tier_a" if structured["status"] == "enriched" else "tier_b",
        "content_hash": f"fixture::{case['case_id']}::structured",
        "retrieved_at": "2026-04-15T00:05:00+00:00",
        "structured_policy_facts": list(structured["facts"]),
        "selected_impact_mode": "compliance_cost",
        "mechanism_family": case["mechanism_family"],
        "source_family": structured["source_family"],
        "access_method": structured["access_method"],
    }


def build_horizontal_matrix(
    *,
    attempt_id: str,
    retry_round: int,
    targeted_tweak: str,
    before_score: float | None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    cases = _case_fixtures()
    for case in cases:
        readiness, dominant_failure_class = _choose_readiness(case)
        selected_quality = _selected_artifact_quality(case)
        score = _quality_score(
            readiness=readiness,
            reader_status=case["reader_status"]["status"],
            structured_status=case["structured_enrichment"]["status"],
        )
        row = {
            "case_id": case["case_id"],
            "title": case["title"],
            "jurisdiction": case["jurisdiction"],
            "mechanism_family": case["mechanism_family"],
            "provider_results": {
                "private_searxng": {
                    "status": case["provider_results"]["private_searxng"]["status"],
                    "reason_code": case["provider_results"]["private_searxng"]["reason_code"],
                    "candidates": [
                        candidate.to_json()
                        for candidate in case["provider_results"]["private_searxng"]["candidates"]
                    ],
                },
                "tavily_fallback": dict(case["provider_results"]["tavily_fallback"]),
                "exa_eval": dict(case["provider_results"]["exa_eval"]),
            },
            "selected_candidate": dict(case["selected_candidate"]),
            "selected_artifact_quality": selected_quality,
            "reader_status": dict(case["reader_status"]),
            "structured_enrichment_status": {
                "status": case["structured_enrichment"]["status"],
                "source_family": case["structured_enrichment"]["source_family"],
                "facts_count": len(case["structured_enrichment"]["facts"]),
            },
            "canonical_identity": {
                "canonical_document_key": f"{case['jurisdiction']}::{case['case_id']}",
                "identity_source": case["source_provenance"]["canonical_document_key_source"],
            },
            "evidence_card_extraction_status": (
                "ready" if readiness in {READINESS_QUANTIFIED, READINESS_QUAL, READINESS_SECONDARY} else "blocked"
            ),
            "package_readiness_classification": readiness,
            "dominant_failure_class": dominant_failure_class,
            "score": score,
            "attempt_id": attempt_id,
            "retry_round": retry_round,
            "targeted_tweak": targeted_tweak,
            "before_score": before_score,
            "after_score": score,
            "stop_continue_decision": "continue" if readiness == READINESS_FAIL else "proceed",
            "field_provenance": dict(case["source_provenance"]),
        }
        rows.append(row)

    family_counts: dict[str, int] = {}
    readiness_counts: dict[str, int] = {}
    failure_counts: dict[str, int] = {}
    for row in rows:
        family = row["mechanism_family"]
        readiness = row["package_readiness_classification"]
        failure = row["dominant_failure_class"]
        family_counts[family] = family_counts.get(family, 0) + 1
        readiness_counts[readiness] = readiness_counts.get(readiness, 0) + 1
        failure_counts[failure] = failure_counts.get(failure, 0) + 1

    average_score = round(mean(float(row["score"]) for row in rows), 2)
    dominant_failure_class = max(failure_counts.items(), key=lambda item: item[1])[0] if failure_counts else "none"
    threshold = 75.0
    matrix = {
        "feature_key": "bd-3wefe.13",
        "generated_at": datetime.now(UTC).isoformat(),
        "attempt_metadata": {
            "attempt_id": attempt_id,
            "retry_round": retry_round,
            "dominant_failure_class": dominant_failure_class,
            "targeted_tweak": targeted_tweak,
            "before_score": before_score,
            "after_score": average_score,
            "stop_continue_decision": "stop" if average_score >= threshold else "continue",
            "quality_threshold": threshold,
        },
        "summary": {
            "total_cases": len(rows),
            "jurisdiction_count": len({row["jurisdiction"] for row in rows}),
            "mechanism_family_counts": family_counts,
            "readiness_counts": readiness_counts,
            "dominant_failure_counts": failure_counts,
            "average_score": average_score,
            "provider_policy": {
                "searxng_required_on_all_rows": True,
                "tavily_fallback_when_searx_weak_or_ambiguous": True,
                "exa_eval_subset_cap": 2,
            },
        },
        "rows": rows,
    }
    return matrix


def build_data_runtime_evidence(
    *,
    matrix: dict[str, Any],
    vertical_case_id: str,
    live_mode: str = "off",
) -> dict[str, Any]:
    fixtures = {case["case_id"]: case for case in _case_fixtures()}
    case = fixtures[vertical_case_id]
    scraped_candidate = _as_scraped_candidate(case)
    structured_candidate = _as_structured_candidate(case)
    selected_quality = _selected_artifact_quality(case)

    package_payload = PolicyEvidencePackageBuilder().build(
        package_id=f"pkg-{vertical_case_id}",
        jurisdiction=case["jurisdiction"],
        scraped_candidates=[scraped_candidate],
        structured_candidates=[structured_candidate] if structured_candidate else [],
        freshness_gate={"freshness_status": "fresh"},
        economic_hints={"impact_mode": "compliance_cost", "mechanism_family": case["mechanism_family"]},
        storage_refs={
            "postgres_package_row": f"policy_evidence_packages:{vertical_case_id}",
            "reader_artifact": (
                case["reader_status"]["reader_artifact_refs"][0]
                if case["reader_status"]["reader_artifact_refs"]
                else f"minio://policy-evidence/reader/{vertical_case_id}.txt"
            ),
            "pgvector_chunk_ref": f"chunk:{vertical_case_id}:1",
        },
    )
    package_payload = _attach_quality_spine_model(
        package_payload,
        mechanism_family=case["mechanism_family"],
    )

    store = InMemoryPolicyEvidencePackageStore()
    writer = InMemoryArtifactWriter()
    package_uri = f"minio://policy-evidence/packages/pkg-{vertical_case_id}.json"
    reader_uri = (
        case["reader_status"]["reader_artifact_refs"][0]
        if case["reader_status"]["reader_artifact_refs"]
        else f"minio://policy-evidence/reader/{vertical_case_id}.txt"
    )
    probe = InMemoryArtifactProbe(known_uris={package_uri, reader_uri})
    storage = PolicyEvidencePackageStorageService(store=store, artifact_writer=writer, artifact_probe=probe)
    storage_result = storage.persist(
        package_payload=package_payload,
        idempotency_key=f"idem-{vertical_case_id}-baseline",
    )
    record = store.get_by_idempotency(idempotency_key=f"idem-{vertical_case_id}-baseline")

    live_probe: dict[str, Any] = {"status": "skipped", "reason": "live_mode_off"}
    if live_mode != "off":
        missing_env: list[str] = []
        # Intentionally avoid secret fetch and live writes in this offline-first harness.
        for env_name in ("DATABASE_URL", "MINIO_URL", "S3_ENDPOINT"):
            # Presence check only; values are never printed.
            from os import getenv

            if not getenv(env_name):
                missing_env.append(env_name)
        if missing_env:
            live_probe = {
                "status": "blocked",
                "failure_class": "live_storage_env_missing",
                "blockers": missing_env,
                "fail_closed": True,
            }
        else:
            live_probe = {
                "status": "blocked",
                "failure_class": "offline_first_harness_no_live_write",
                "reason": "live mode requested but this verifier is deterministic/offline by contract",
                "fail_closed": True,
            }

    orchestration_proof = _build_orchestration_proof(
        package_id=package_payload["package_id"],
        live_mode=live_mode,
    )

    return {
        "feature_key": "bd-3wefe.13",
        "generated_at": datetime.now(UTC).isoformat(),
        "attempt_metadata": dict(matrix["attempt_metadata"]),
        "vertical_candidate_case_id": vertical_case_id,
        "vertical_candidate": {
            "jurisdiction": case["jurisdiction"],
            "title": case["title"],
            "mechanism_family": case["mechanism_family"],
        },
        "package_build": {
            "package_id": package_payload["package_id"],
            "canonical_document_key": package_payload["canonical_document_key"],
            "source_lanes": package_payload["source_lanes"],
            "evidence_card_count": len(package_payload["evidence_cards"]),
            "parameter_card_count": len(package_payload["parameter_cards"]),
            "economic_handoff_ready": package_payload["economic_handoff_ready"],
        },
        "vertical_package_payload": package_payload,
        "persisted_record": None if record is None else record.to_row_json(),
        "storage_readback": {
            "storage_mode": "in_memory",
            "storage_backend": "in_memory_policy_evidence_store",
            "artifact_store_mode": "in_memory_artifact_writer",
            "proof_status": "in_memory_only",
            "proof_blocker": "real_postgres_minio_not_exercised_in_deterministic_harness",
            "real_postgres_minio_proven": False,
            "stored": storage_result.stored,
            "idempotent_reuse": storage_result.idempotent_reuse,
            "fail_closed": storage_result.fail_closed,
            "failure_class": storage_result.failure_class,
            "artifact_write_status": storage_result.artifact_write_status,
            "artifact_readback_status": storage_result.artifact_readback_status,
            "record_present": record is not None,
        },
        "vertical_selected_artifact_quality": selected_quality,
        "orchestration_proof": orchestration_proof,
        "live_probe": live_probe,
        "matrix_score_snapshot": {
            "average_score": matrix["summary"]["average_score"],
            "readiness_counts": matrix["summary"]["readiness_counts"],
            "dominant_failure_counts": matrix["summary"]["dominant_failure_counts"],
        },
    }
