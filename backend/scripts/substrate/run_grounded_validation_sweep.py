#!/usr/bin/env python3
"""Run the bd-sc6o.5 grounded substrate validation sweep.

This sweep captures four concrete real-world pages and reports:
- what landed in raw_scrapes
- ingestion-truth stage
- trust classification
- promotion state and reason
- whether each case is useful for moat and/or analysis
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from db.postgres_client import PostgresDB
from scripts.substrate.manual_capture import capture_document
from scripts.substrate.manual_capture import parse_metadata_blob
from services.substrate_promotion import CAPTURED_CANDIDATE
from services.substrate_promotion import DURABLE_RAW
from services.substrate_promotion import OFFICIAL_HOST_CLASSES
from services.substrate_promotion import OFFICIAL_TRUST_TIERS
from services.substrate_promotion import PROMOTED_SUBSTRATE
from services.substrate_promotion import evaluate_rules
from services.substrate_promotion import parse_json_blob


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = (
    REPO_ROOT / "backend/scripts/substrate/artifacts/bd-sc6o.5_grounded_validation_report.json"
)
SWEEP_VERSION = "2026-04-01.v1"


@dataclass(frozen=True)
class SweepCase:
    case_id: str
    case_type: str
    description: str
    url: str
    source_name: str
    source_type: str
    document_type: str
    trust_tier: str
    expected_promotion_states: tuple[str, ...]
    expected_official_path: bool
    expected_analysis_useful: bool
    expected_moat_useful: bool
    ingest: bool = True


def default_cases() -> list[SweepCase]:
    return [
        SweepCase(
            case_id="official_html_meeting_detail",
            case_type="official_html_meeting_detail",
            description=(
                "Official HTML meeting detail page should capture and remain in trusted path."
            ),
            url=(
                "https://sanjose.legistar.com/MeetingDetail.aspx?"
                "LEGID=7616&GID=317&G=920296E4-80BE-4CA2-A78F-32C5EFCF78AF"
            ),
            source_name="Grounded Sweep: SJ Meeting Detail",
            source_type="meetings",
            document_type="meeting_detail",
            trust_tier="primary_government",
            expected_promotion_states=(PROMOTED_SUBSTRATE, DURABLE_RAW),
            expected_official_path=True,
            expected_analysis_useful=True,
            expected_moat_useful=True,
        ),
        SweepCase(
            case_id="official_pdf_agenda",
            case_type="official_pdf_agenda",
            description="Official PDF agenda should be durably captured without text-ingest failures.",
            url=(
                "https://legistar.granicus.com/sanjose/meetings/2026/4/"
                "7616_A_City_Council_26-04-07_Agenda.pdf"
            ),
            source_name="Grounded Sweep: SJ Agenda PDF",
            source_type="meetings",
            document_type="agenda",
            trust_tier="primary_government",
            expected_promotion_states=(PROMOTED_SUBSTRATE, DURABLE_RAW),
            expected_official_path=True,
            expected_analysis_useful=True,
            expected_moat_useful=True,
        ),
        SweepCase(
            case_id="official_code_page",
            case_type="official_code_page",
            description=(
                "Official code/ordinance surface should preserve official raw capture; "
                "thin shell pages should avoid auto-promotion."
            ),
            url="https://library.municode.com/ca/san_jose/codes/code_of_ordinances",
            source_name="Grounded Sweep: SJ Municipal Code",
            source_type="code",
            document_type="municipal_code",
            trust_tier="official_partner",
            expected_promotion_states=(DURABLE_RAW,),
            expected_official_path=True,
            expected_analysis_useful=False,
            expected_moat_useful=True,
        ),
        SweepCase(
            case_id="third_party_deny_path",
            case_type="third_party_deny_path",
            description=(
                "Third-party general informational page must not enter trusted "
                "official promotion path."
            ),
            url="https://www.dwellito.com/blog/san-jose-adu-rules",
            source_name="Grounded Sweep: Third-Party ADU Info",
            source_type="general",
            document_type="general_info",
            trust_tier="non_official",
            expected_promotion_states=(CAPTURED_CANDIDATE, DURABLE_RAW),
            expected_official_path=False,
            expected_analysis_useful=False,
            expected_moat_useful=False,
        ),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Report path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        help="Optional case id filter (repeatable).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not perform capture/DB writes; output selected case contract only.",
    )
    return parser.parse_args()


def filter_cases(cases: list[SweepCase], selected_ids: set[str] | None) -> list[SweepCase]:
    if not selected_ids:
        return cases
    return [case for case in cases if case.case_id in selected_ids]


def is_official_path(metadata: dict[str, Any]) -> bool:
    trust_tier = (metadata.get("trust_tier") or "").strip().lower()
    host_class = (metadata.get("trust_host_classification") or "").strip().lower()
    return trust_tier in OFFICIAL_TRUST_TIERS or host_class in OFFICIAL_HOST_CLASSES


def compute_usefulness(metadata: dict[str, Any]) -> dict[str, bool]:
    promotion_state = metadata.get("promotion_state")
    truth = parse_json_blob(metadata.get("ingestion_truth"))
    official = is_official_path(metadata)

    analysis_useful = promotion_state == PROMOTED_SUBSTRATE
    moat_useful = (
        official
        and promotion_state in {DURABLE_RAW, PROMOTED_SUBSTRATE}
        and truth.get("raw_captured") is True
    )
    return {
        "analysis_useful": analysis_useful,
        "moat_useful": moat_useful,
        "overall_useful": analysis_useful or moat_useful,
    }


def evaluate_case_checks(
    *,
    case: SweepCase,
    metadata: dict[str, Any],
) -> dict[str, bool]:
    usefulness = compute_usefulness(metadata)
    observed_state = metadata.get("promotion_state")
    official_path = is_official_path(metadata)
    checks = {
        "promotion_state_expected": observed_state in set(case.expected_promotion_states),
        "official_path_expected": official_path == case.expected_official_path,
        "analysis_useful_expected": usefulness["analysis_useful"] == case.expected_analysis_useful,
        "moat_useful_expected": usefulness["moat_useful"] == case.expected_moat_useful,
    }
    checks["all_expected"] = all(checks.values())
    return checks


async def fetch_capture_rows(
    db: PostgresDB,
    *,
    scrape_id: str,
    source_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    scrape_row = await db._fetchrow(
        """
        SELECT id, source_id, url, content_type, storage_uri, error_message, document_id, metadata
        FROM raw_scrapes
        WHERE id = $1
        """,
        scrape_id,
    )
    if not scrape_row:
        raise RuntimeError(f"Missing raw_scrapes row for scrape_id={scrape_id}")

    source_row = await db._fetchrow(
        """
        SELECT id, name, type, url, metadata
        FROM sources
        WHERE id = $1
        """,
        source_id,
    )
    if not source_row:
        raise RuntimeError(f"Missing sources row for source_id={source_id}")

    return dict(scrape_row), dict(source_row)


async def run_case(case: SweepCase) -> dict[str, Any]:
    args = argparse.Namespace(
        url=case.url,
        jurisdiction_name="San Jose",
        jurisdiction_type="city",
        source_name=case.source_name,
        source_type=case.source_type,
        document_type=case.document_type,
        trust_tier=case.trust_tier,
        capture_method="manual_http_grounded_sweep_v2",
        title=None,
        ingest=case.ingest,
    )

    capture_result = await capture_document(args)
    db = PostgresDB()
    scrape_row, source_row = await fetch_capture_rows(
        db,
        scrape_id=capture_result["scrape_id"],
        source_id=capture_result["source_id"],
    )

    metadata = parse_metadata_blob(scrape_row.get("metadata"))
    source_metadata = parse_metadata_blob(source_row.get("metadata"))
    truth = parse_json_blob(metadata.get("ingestion_truth"))
    rules_decision = evaluate_rules(metadata)
    usefulness = compute_usefulness(metadata)
    checks = evaluate_case_checks(case=case, metadata=metadata)

    observed = {
        "promotion_state": metadata.get("promotion_state"),
        "promotion_reason_category": metadata.get("promotion_reason_category"),
        "promotion_confidence": metadata.get("promotion_confidence"),
        "promotion_method": metadata.get("promotion_method"),
        "trust_tier": metadata.get("trust_tier"),
        "trust_host_classification": metadata.get("trust_host_classification"),
        "content_class": metadata.get("content_class"),
        "document_type": metadata.get("document_type"),
        "ingestion_stage": truth.get("stage"),
        "retrievable": truth.get("retrievable"),
        "blob_stored": truth.get("blob_stored"),
        "storage_uri_present": truth.get("storage_uri_present"),
        "storage_uri": scrape_row.get("storage_uri"),
        "scrape_error_message": scrape_row.get("error_message"),
        "rules_recheck": {
            "promotion_state": rules_decision.promotion_state,
            "reason_category": rules_decision.reason_category,
            "confidence": rules_decision.confidence,
            "method": rules_decision.method,
        },
    }

    return {
        "case": asdict(case),
        "status": "pass" if checks["all_expected"] else "fail",
        "capture_result": capture_result,
        "scrape_row": {
            "id": str(scrape_row.get("id")),
            "source_id": str(scrape_row.get("source_id")),
            "document_id": str(scrape_row.get("document_id")) if scrape_row.get("document_id") else None,
            "url": scrape_row.get("url"),
            "content_type": scrape_row.get("content_type"),
            "storage_uri": scrape_row.get("storage_uri"),
        },
        "source_row": {
            "id": str(source_row.get("id")),
            "name": source_row.get("name"),
            "type": source_row.get("type"),
            "url": source_row.get("url"),
            "metadata": source_metadata,
        },
        "observed": observed,
        "usefulness": usefulness,
        "checks": checks,
    }


def build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    promotion_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    usefulness_counts: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []

    for result in results:
        status_counts[result.get("status", "unknown")] += 1
        if result.get("status") == "error":
            failures.append(
                {
                    "case_id": result.get("case", {}).get("case_id"),
                    "error": result.get("error"),
                }
            )
            continue

        observed = result.get("observed", {})
        promotion_counts[str(observed.get("promotion_state") or "null")] += 1
        reason_counts[str(observed.get("promotion_reason_category") or "null")] += 1
        usefulness = result.get("usefulness", {})
        usefulness_counts["analysis_useful_true"] += int(bool(usefulness.get("analysis_useful")))
        usefulness_counts["analysis_useful_false"] += int(not bool(usefulness.get("analysis_useful")))
        usefulness_counts["moat_useful_true"] += int(bool(usefulness.get("moat_useful")))
        usefulness_counts["moat_useful_false"] += int(not bool(usefulness.get("moat_useful")))
        usefulness_counts["overall_useful_true"] += int(bool(usefulness.get("overall_useful")))
        usefulness_counts["overall_useful_false"] += int(not bool(usefulness.get("overall_useful")))
        if result.get("status") == "fail":
            failures.append(
                {
                    "case_id": result.get("case", {}).get("case_id"),
                    "failed_checks": [
                        key for key, value in result.get("checks", {}).items() if key != "all_expected" and not value
                    ],
                }
            )

    return {
        "case_count": len(results),
        "status_counts": dict(status_counts),
        "promotion_state_counts": dict(promotion_counts),
        "promotion_reason_counts": dict(reason_counts),
        "usefulness_counts": dict(usefulness_counts),
        "failures": failures,
        "framework_worked": not failures and len(results) > 0,
    }


def build_framework_assessment(summary: dict[str, Any]) -> dict[str, Any]:
    worked = bool(summary.get("framework_worked"))
    strengths = [
        "Sweep records ingestion truth, trust classification, and promotion state together.",
        "Report is machine-readable and reproducible from fixed case definitions.",
    ]
    weaknesses: list[str] = []
    if summary.get("failures"):
        weaknesses.append("One or more required validation cases failed expectations.")
    if summary.get("status_counts", {}).get("error", 0) > 0:
        weaknesses.append("At least one capture failed due to runtime or URL availability issues.")
    if not weaknesses:
        weaknesses.append("No contract violations observed in this run.")

    return {
        "worked": worked,
        "strengths": strengths,
        "remaining_weaknesses": weaknesses,
    }


async def execute_sweep(args: argparse.Namespace) -> dict[str, Any]:
    cases = filter_cases(default_cases(), set(args.case_ids or []))
    if not cases:
        raise RuntimeError("No cases selected for sweep")

    if args.dry_run:
        return {
            "sweep_version": SWEEP_VERSION,
            "run_mode": "dry_run",
            "run_at": datetime.now(timezone.utc).isoformat(),
            "cases": [asdict(case) for case in cases],
            "summary": {
                "case_count": len(cases),
                "status_counts": {"not_run": len(cases)},
                "framework_worked": False,
            },
            "framework_assessment": {
                "worked": False,
                "strengths": [],
                "remaining_weaknesses": ["Dry run does not execute live capture."],
            },
        }

    results: list[dict[str, Any]] = []
    for case in cases:
        try:
            result = await run_case(case)
        except Exception as exc:  # noqa: BLE001 - sweep must report truthful failures per case
            result = {
                "case": asdict(case),
                "status": "error",
                "error": str(exc),
            }
        results.append(result)

    summary = build_summary(results)
    return {
        "sweep_version": SWEEP_VERSION,
        "run_mode": "live_capture",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "cases": results,
        "summary": summary,
        "framework_assessment": build_framework_assessment(summary),
    }


def main() -> None:
    args = parse_args()
    report = asyncio.run(execute_sweep(args))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote grounded sweep report to {output_path}")


if __name__ == "__main__":
    main()
