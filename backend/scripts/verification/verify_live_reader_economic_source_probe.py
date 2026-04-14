#!/usr/bin/env python3
"""Live/replay probe for reader-source quality on economics-bearing URLs.

This script is intentionally narrow: it tests whether selected live sources can
produce reader output with enough substance and numeric parameter signal to be
considered decision-grade candidates for downstream economic gates.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import URLError, HTTPError


FEATURE_KEY = "bd-2agbe.6"
PROBE_VERSION = "2026-04-14.live-reader-probe-v1"

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPLAY_FIXTURE = (
    REPO_ROOT
    / "backend"
    / "scripts"
    / "verification"
    / "fixtures"
    / "live_reader_economic_source_probe_replay.json"
)
DEFAULT_OUT_JSON = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "economic-evidence-quality"
    / "artifacts"
    / "live_reader_economic_source_probe_report.json"
)
DEFAULT_OUT_MD = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "economic-evidence-quality"
    / "artifacts"
    / "live_reader_economic_source_probe_report.md"
)

MODE_LIVE = "live"
MODE_REPLAY = "replay"
MODE_AUTO = "auto"

CASE_CATALOG = (
    {
        "case_id": "sanjose_legistar_cost_of_residential_development",
        "label": "San Jose Legistar meeting detail (Cost of Residential Development)",
        "source_family": "official_meeting_detail",
        "url": "https://sanjose.legistar.com/MeetingDetail.aspx?ID=1315729&GUID=3C17B03F-B014-43D5-B8DF-44024CDE065B&Options=info%7C&Search=",
    },
    {
        "case_id": "sanjose_records_contract_pdf_con667337_002",
        "label": "San Jose records PDF (CON667337-002)",
        "source_family": "official_record_pdf",
        "url": "https://records.sanjoseca.gov/Contracts/CON667337-002.pdf",
    },
    {
        "case_id": "sanjose_housing_council_memos_portal",
        "label": "San Jose housing council memos portal",
        "source_family": "official_portal_listing",
        "url": "https://www.sanjoseca.gov/your-government/departments-offices/housing/policies-and-data/reports-and-memos/city-council-memos",
    },
)

ECONOMICS_KEYWORDS = {
    "economic",
    "economics",
    "cost",
    "fiscal",
    "budget",
    "revenue",
    "fee",
    "tax",
    "housing",
    "development",
    "residential",
    "grant",
    "contract",
    "funding",
    "subsidy",
    "rent",
}

PORTAL_URL_SIGNALS = (
    "your-government",
    "reports-and-memos",
    "city-council-memos",
    "DepartmentDetail.aspx",
    "Calendar.aspx",
    "resource-library",
)

NAVIGATION_PHRASES = (
    "skip to main content",
    "city clerk",
    "search",
    "menu",
    "home",
    "privacy",
    "terms",
    "copyright",
    "all rights reserved",
    "sign in",
    "my account",
)

NUMERIC_PARAMETER_PATTERN = re.compile(
    r"(?:[$]\s?\d[\d,]*(?:\.\d+)?)|(?:\d+(?:\.\d+)?\s?(?:%|percent|basis points|bps|million|billion|thousand|usd|dollars))",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ProbeConfig:
    mode: str
    replay_fixture: Path
    out_json: Path
    out_md: Path
    save_live_replay: Path | None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _repo_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _extract_reader_content(payload: dict[str, Any]) -> str:
    data_block = payload.get("reader_result", payload)
    if not isinstance(data_block, dict):
        return ""
    for key in ("content", "markdown", "text"):
        value = data_block.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _looks_like_portal_or_navigation(*, url: str, content: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    lower_url = url.lower()
    for signal in PORTAL_URL_SIGNALS:
        if signal.lower() in lower_url:
            reasons.append(f"url_signal:{signal}")

    lower_content = content.lower()
    nav_hits = [phrase for phrase in NAVIGATION_PHRASES if phrase in lower_content]
    if len(nav_hits) >= 3:
        reasons.append(f"navigation_phrases:{len(nav_hits)}")

    records_pdf_url = "records.sanjoseca.gov/contracts/" in lower_url and lower_url.endswith(".pdf")
    if records_pdf_url and "city clerk" in lower_content:
        reasons.append("records_pdf_navigation_render")

    return (len(reasons) > 0, reasons)


def _economics_topic_signal(content: str) -> tuple[bool, list[str]]:
    tokens = {token.lower() for token in re.findall(r"[a-zA-Z]{3,}", content)}
    matched = sorted(keyword for keyword in ECONOMICS_KEYWORDS if keyword in tokens)
    return (len(matched) > 0, matched)


def _numeric_parameter_signal(content: str) -> tuple[bool, list[str]]:
    matches = NUMERIC_PARAMETER_PATTERN.findall(content)
    normalized = []
    for match in matches[:10]:
        if isinstance(match, tuple):
            joined = " ".join(part for part in match if part).strip()
            if joined:
                normalized.append(joined)
        elif isinstance(match, str) and match.strip():
            normalized.append(match.strip())
    return (len(normalized) > 0, normalized)


def classify_case(*, case_id: str, label: str, source_family: str, url: str, reader_payload: dict[str, Any], fetch_error: str = "") -> dict[str, Any]:
    content = _extract_reader_content(reader_payload)
    chars = len(content)

    reader_success = bool(content) and not fetch_error
    portal_like, portal_reasons = _looks_like_portal_or_navigation(url=url, content=content)

    substantive_text = reader_success and chars >= 400 and not portal_like
    econ_signal, econ_keywords = _economics_topic_signal(content)
    numeric_signal, numeric_examples = _numeric_parameter_signal(content)

    decision_grade_candidate = (
        reader_success
        and substantive_text
        and econ_signal
        and numeric_signal
        and not portal_like
    )

    blocking_gate = ""
    if not reader_success or portal_like:
        blocking_gate = "reader_source_quality"
    elif not substantive_text:
        blocking_gate = "reader_substance"
    elif not econ_signal:
        blocking_gate = "economic_topic_signal"
    elif not numeric_signal:
        blocking_gate = "parameterization_sufficiency"

    return {
        "case_id": case_id,
        "label": label,
        "source_family": source_family,
        "url": url,
        "reader_success": reader_success,
        "substantive_text": substantive_text,
        "economics_topic_signal": econ_signal,
        "numeric_parameter_signal": numeric_signal,
        "likely_portal_or_navigation": portal_like,
        "decision_grade_candidate": decision_grade_candidate,
        "blocking_gate": blocking_gate,
        "chars": chars,
        "fetch_error": fetch_error,
        "portal_reasons": portal_reasons,
        "economics_keywords": econ_keywords,
        "numeric_examples": numeric_examples,
        "content_excerpt": content[:700],
    }


def _fetch_live_payload_sync(url: str) -> tuple[dict[str, Any], str]:
    api_key = os.getenv("ZAI_API_KEY", "")
    if not api_key:
        return {"reader_result": {"content": ""}}, "missing_ZAI_API_KEY"
    endpoint = "https://api.z.ai/api/coding/paas/v4/reader"
    body = json.dumps({"url": url, "timeout": 60}).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=70) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if isinstance(payload, dict):
                return payload, ""
            return {"reader_result": {"content": ""}}, "reader_payload_not_dict"
    except HTTPError as exc:
        err_text = exc.read().decode("utf-8", errors="replace")
        return {"reader_result": {"content": ""}}, f"http_error:{exc.code}:{err_text[:300]}"
    except URLError as exc:
        return {"reader_result": {"content": ""}}, f"url_error:{exc.reason}"
    except Exception as exc:
        return {"reader_result": {"content": ""}}, str(exc)


async def _run_live(config: ProbeConfig) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not os.getenv("ZAI_API_KEY"):
        raise RuntimeError("ZAI_API_KEY missing for --mode live")

    probe_inputs: list[dict[str, Any]] = []
    classifications: list[dict[str, Any]] = []
    for case in CASE_CATALOG:
        payload, error = await asyncio.to_thread(_fetch_live_payload_sync, case["url"])
        probe_inputs.append(
            {
                "case_id": case["case_id"],
                "label": case["label"],
                "source_family": case["source_family"],
                "url": case["url"],
                "fetch_error": error,
                "reader_payload": payload,
            }
        )
        classifications.append(
            classify_case(
                case_id=case["case_id"],
                label=case["label"],
                source_family=case["source_family"],
                url=case["url"],
                reader_payload=payload,
                fetch_error=error,
            )
        )

    replay_payload = {"version": PROBE_VERSION, "generated_at": _now_iso(), "cases": probe_inputs}
    if config.save_live_replay:
        _write_json(config.save_live_replay, replay_payload)

    return classifications, replay_payload


def _run_replay(config: ProbeConfig) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fixture = _load_json(config.replay_fixture)
    entries = fixture.get("cases", [])
    if not isinstance(entries, list):
        raise ValueError("invalid replay fixture: cases must be a list")

    classifications: list[dict[str, Any]] = []
    for entry in entries:
        classifications.append(
            classify_case(
                case_id=str(entry.get("case_id", "")),
                label=str(entry.get("label", "")),
                source_family=str(entry.get("source_family", "")),
                url=str(entry.get("url", "")),
                reader_payload=entry.get("reader_payload", {}),
                fetch_error=str(entry.get("fetch_error", "")),
            )
        )
    return classifications, fixture


def _summarize(classifications: list[dict[str, Any]]) -> dict[str, Any]:
    blocking_counts: dict[str, int] = {}
    for row in classifications:
        key = row.get("blocking_gate", "") or "none"
        blocking_counts[key] = blocking_counts.get(key, 0) + 1

    return {
        "total_cases": len(classifications),
        "reader_success_cases": sum(1 for row in classifications if row["reader_success"]),
        "substantive_text_cases": sum(1 for row in classifications if row["substantive_text"]),
        "economics_topic_signal_cases": sum(1 for row in classifications if row["economics_topic_signal"]),
        "numeric_parameter_signal_cases": sum(1 for row in classifications if row["numeric_parameter_signal"]),
        "decision_grade_candidate_cases": sum(1 for row in classifications if row["decision_grade_candidate"]),
        "blocking_gate_counts": blocking_counts,
    }


def _build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Live Reader Economic Source Probe",
        "",
        f"- feature_key: `{report['feature_key']}`",
        f"- probe_version: `{report['probe_version']}`",
        f"- mode: `{report['mode']}`",
        f"- generated_at: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- total_cases: {report['summary']['total_cases']}",
        f"- reader_success_cases: {report['summary']['reader_success_cases']}",
        f"- substantive_text_cases: {report['summary']['substantive_text_cases']}",
        f"- economics_topic_signal_cases: {report['summary']['economics_topic_signal_cases']}",
        f"- numeric_parameter_signal_cases: {report['summary']['numeric_parameter_signal_cases']}",
        f"- decision_grade_candidate_cases: {report['summary']['decision_grade_candidate_cases']}",
        "",
        "## Cases",
        "",
        "| case_id | reader_success | substantive_text | economics_topic_signal | numeric_parameter_signal | likely_portal_or_navigation | decision_grade_candidate | blocking_gate |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]

    for case in report["cases"]:
        lines.append(
            "| "
            + f"{case['case_id']} | {str(case['reader_success']).lower()} | {str(case['substantive_text']).lower()} | "
            + f"{str(case['economics_topic_signal']).lower()} | {str(case['numeric_parameter_signal']).lower()} | "
            + f"{str(case['likely_portal_or_navigation']).lower()} | {str(case['decision_grade_candidate']).lower()} | "
            + f"{case['blocking_gate'] or '-'} |"
        )

    lines.extend(
        [
            "",
            "## Audit Notes",
            "",
            "- Topic text without numeric parameters is qualitative-only and not decision-grade.",
            "- Navigation/portal-like reader outputs are treated as reader/source-quality failures.",
            "",
        ]
    )

    for case in report["cases"]:
        lines.extend(
            [
                f"### {case['case_id']}",
                "",
                f"- url: {case['url']}",
                f"- blocking_gate: {case['blocking_gate'] or '-'}",
                f"- chars: {case['chars']}",
                f"- portal_reasons: {', '.join(case['portal_reasons']) if case['portal_reasons'] else '-'}",
                f"- economics_keywords: {', '.join(case['economics_keywords']) if case['economics_keywords'] else '-'}",
                f"- numeric_examples: {', '.join(case['numeric_examples']) if case['numeric_examples'] else '-'}",
                f"- fetch_error: {case['fetch_error'] or '-'}",
                "",
                "```text",
                case["content_excerpt"] or "",
                "```",
                "",
            ]
        )

    return "\n".join(lines)


def _write_report(config: ProbeConfig, report: dict[str, Any]) -> None:
    config.out_json.parent.mkdir(parents=True, exist_ok=True)
    config.out_md.parent.mkdir(parents=True, exist_ok=True)
    config.out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    config.out_md.write_text(_build_markdown(report), encoding="utf-8")


async def _run(config: ProbeConfig) -> dict[str, Any]:
    selected_mode = config.mode
    if selected_mode == MODE_AUTO:
        selected_mode = MODE_LIVE if os.getenv("ZAI_API_KEY") else MODE_REPLAY

    if selected_mode == MODE_LIVE:
        classifications, source_payload = await _run_live(config)
        replay_fixture_path = _repo_display_path(config.save_live_replay) if config.save_live_replay else ""
    elif selected_mode == MODE_REPLAY:
        classifications, source_payload = _run_replay(config)
        replay_fixture_path = _repo_display_path(config.replay_fixture)
    else:
        raise ValueError(f"unsupported mode: {selected_mode}")

    report = {
        "feature_key": FEATURE_KEY,
        "probe_version": PROBE_VERSION,
        "generated_at": _now_iso(),
        "mode": selected_mode,
        "inputs": {
            "replay_fixture_path": replay_fixture_path,
            "save_live_replay": _repo_display_path(config.save_live_replay) if config.save_live_replay else "",
        },
        "summary": _summarize(classifications),
        "cases": classifications,
        "source_payload": source_payload,
    }
    _write_report(config, report)
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe live/replay reader output quality for economic evidence readiness")
    parser.add_argument("--mode", choices=(MODE_AUTO, MODE_LIVE, MODE_REPLAY), default=MODE_AUTO)
    parser.add_argument("--replay-fixture", type=Path, default=DEFAULT_REPLAY_FIXTURE)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    parser.add_argument(
        "--save-live-replay",
        type=Path,
        default=None,
        help="Optional path to write replay payload when running in live mode",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    config = ProbeConfig(
        mode=str(args.mode),
        replay_fixture=Path(args.replay_fixture),
        out_json=Path(args.out_json),
        out_md=Path(args.out_md),
        save_live_replay=Path(args.save_live_replay) if args.save_live_replay else None,
    )
    report = asyncio.run(_run(config))
    print(json.dumps({"summary": report["summary"], "mode": report["mode"]}, indent=2))


if __name__ == "__main__":
    main()
