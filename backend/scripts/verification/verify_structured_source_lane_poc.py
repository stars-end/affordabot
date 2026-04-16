#!/usr/bin/env python3
"""No-secret structured-source live probe POC (bd-2agbe.1).

This verifier probes three structured source families with bounded requests:
1) California LegInfo PUBINFO official file feed
2) Legistar public Web API (San Jose)
3) Public ArcGIS REST/Hub Feature/Map service

It supports replay mode for deterministic tests without network.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError


FEATURE_KEY = "bd-2agbe.1"
POC_VERSION = "2026-04-14.structured-source-lane.v1"

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPLAY_FIXTURE = (
    REPO_ROOT
    / "backend"
    / "scripts"
    / "verification"
    / "fixtures"
    / "structured_source_lane_poc_replay.json"
)
DEFAULT_OUT_JSON = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "structured-source-lane"
    / "artifacts"
    / "structured_source_lane_poc_report.json"
)
DEFAULT_OUT_MD = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "structured-source-lane"
    / "artifacts"
    / "structured_source_lane_poc_report.md"
)

MODE_AUTO = "auto"
MODE_LIVE = "live"
MODE_REPLAY = "replay"

LEGINFO_ROOT = "https://downloads.leginfo.legislature.ca.gov/"
LEGINFO_README = "https://downloads.leginfo.legislature.ca.gov/pubinfo_Readme.pdf"
LEGINFO_DAILY = "https://downloads.leginfo.legislature.ca.gov/pubinfo_daily_Mon.zip"

LEGISTAR_ENDPOINT = "https://webapi.legistar.com/v1/sanjose/matters?$top=5"
LEGISTAR_SCHEMA_KEYS = (
    "MatterId",
    "MatterGuid",
    "MatterFile",
    "MatterLastModifiedUtc",
)

ARCGIS_SEARCH_ENDPOINT = "https://www.arcgis.com/sharing/rest/search"


@dataclass(frozen=True)
class ProbeConfig:
    mode: str
    timeout_seconds: float
    replay_fixture: Path
    out_json: Path
    out_md: Path
    save_live_replay: Path | None
    self_check: bool


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _http_request(
    *,
    method: str,
    url: str,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request = urllib.request.Request(url=url, method=method.upper())
    headers = headers or {}
    for key, value in headers.items():
        request.add_header(key, value)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        status = getattr(response, "status", response.getcode())
        raw_headers = dict(response.headers.items())
        body = response.read()
    return {"status": int(status), "headers": raw_headers, "body": body}


def _http_json_get(*, url: str, timeout_seconds: float) -> dict[str, Any]:
    response = _http_request(method="GET", url=url, timeout_seconds=timeout_seconds)
    body = response["body"]
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _probe_leginfo_live(timeout_seconds: float) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    targets = (
        ("HEAD", LEGINFO_ROOT, {}),
        ("GET", LEGINFO_README, {"Range": "bytes=0-1023"}),
        ("HEAD", LEGINFO_DAILY, {}),
    )
    for method, url, headers in targets:
        try:
            response = _http_request(
                method=method,
                url=url,
                timeout_seconds=timeout_seconds,
                headers=headers,
            )
            checks.append(
                {
                    "method": method,
                    "url": url,
                    "status": response["status"],
                    "content_type": response["headers"].get("Content-Type", ""),
                    "content_length": response["headers"].get("Content-Length", ""),
                }
            )
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            errors.append(f"{method} {url}: {exc}")
            checks.append({"method": method, "url": url, "status": 0, "error": str(exc)})

    root_ok = any(item["url"] == LEGINFO_ROOT and item.get("status", 0) >= 200 and item.get("status", 0) < 400 for item in checks)
    artifact_ok = any(
        item["url"] in {LEGINFO_README, LEGINFO_DAILY}
        and item.get("status", 0) >= 200
        and item.get("status", 0) < 400
        for item in checks
    )
    passed = root_ok and artifact_ok

    return {
        "source_family": "ca_leginfo_pubinfo",
        "probe_name": "California LegInfo PUBINFO official feed",
        "sample_pull_without_browser": passed,
        "status": "pass" if passed else "fail",
        "checks": checks,
        "errors": errors,
        "evidence": {
            "official_root_reachable": root_ok,
            "raw_artifact_endpoint_reachable": artifact_ok,
            "artifact_endpoints_checked": [LEGINFO_README, LEGINFO_DAILY],
        },
    }


def _probe_legistar_live(timeout_seconds: float) -> dict[str, Any]:
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    schema_presence = {key: False for key in LEGISTAR_SCHEMA_KEYS}

    try:
        payload = _http_json_get(url=LEGISTAR_ENDPOINT, timeout_seconds=timeout_seconds)
        if isinstance(payload, list):
            rows = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            data = payload.get("value")
            if isinstance(data, list):
                rows = [item for item in data if isinstance(item, dict)]
        if rows:
            first = rows[0]
            for key in LEGISTAR_SCHEMA_KEYS:
                schema_presence[key] = key in first
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    passed = len(rows) > 0
    sample_row = {
        key: rows[0].get(key)
        for key in LEGISTAR_SCHEMA_KEYS
        if rows and key in rows[0]
    }

    return {
        "source_family": "legistar_web_api",
        "probe_name": "Legistar Web API public San Jose endpoint",
        "endpoint": LEGISTAR_ENDPOINT,
        "sample_pull_without_browser": passed,
        "status": "pass" if passed else "fail",
        "row_count": len(rows),
        "schema_presence": schema_presence,
        "sample_row": sample_row,
        "errors": errors,
    }


def _arcgis_search_query_url() -> str:
    query = (
        '(("San Jose" OR "Santa Clara") AND '
        '("FeatureServer" OR "MapServer") AND '
        '("planning" OR "zoning" OR "housing" OR "parcel" OR "permit")) '
        '-type:"Web Mapping Application" -type:Code'
    )
    params = {
        "f": "json",
        "num": "20",
        "sortField": "numviews",
        "sortOrder": "desc",
        "q": query,
    }
    return f"{ARCGIS_SEARCH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def _arcgis_layer_candidates(search_results: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    for result in search_results:
        if not isinstance(result, dict):
            continue
        url = result.get("url")
        if not isinstance(url, str) or not url:
            continue
        lowered = url.lower()
        if "featureserver" not in lowered and "mapserver" not in lowered:
            continue
        base = url.rstrip("/")
        if base.rsplit("/", maxsplit=1)[-1].isdigit():
            layer_url = base
        else:
            layer_url = f"{base}/0"
        candidates.append((layer_url, result))
    return candidates


def _probe_arcgis_live(timeout_seconds: float) -> dict[str, Any]:
    errors: list[str] = []
    search_url = _arcgis_search_query_url()
    selected: dict[str, Any] | None = None

    try:
        search_payload = _http_json_get(url=search_url, timeout_seconds=timeout_seconds)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return {
            "source_family": "arcgis_rest_public",
            "probe_name": "Public ArcGIS REST/Hub Bay Area endpoint",
            "sample_pull_without_browser": False,
            "status": "fail",
            "search_url": search_url,
            "errors": [f"search_failed: {exc}"],
        }

    results = search_payload.get("results", [])
    if not isinstance(results, list):
        results = []

    candidates = _arcgis_layer_candidates(results)
    for layer_url, source_item in candidates:
        metadata_url = f"{layer_url}?f=json"
        query_params = urllib.parse.urlencode(
            {
                "f": "json",
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "false",
                "resultRecordCount": "3",
            }
        )
        query_url = f"{layer_url}/query?{query_params}"
        try:
            metadata = _http_json_get(url=metadata_url, timeout_seconds=timeout_seconds)
            fields = metadata.get("fields")
            if not isinstance(fields, list) or len(fields) == 0:
                continue
            query_payload = _http_json_get(url=query_url, timeout_seconds=timeout_seconds)
            features = query_payload.get("features")
            if not isinstance(features, list):
                continue

            field_names = [f.get("name", "") for f in fields if isinstance(f, dict)]
            field_types = [f.get("type", "") for f in fields if isinstance(f, dict)]
            identity_fields = [
                name
                for name, ftype in zip(field_names, field_types)
                if isinstance(name, str)
                and isinstance(ftype, str)
                and (ftype == "esriFieldTypeOID" or "globalid" in name.lower())
            ]
            date_fields = [
                name
                for name, ftype in zip(field_names, field_types)
                if isinstance(name, str) and ftype == "esriFieldTypeDate"
            ]
            sample_attributes = {}
            if features and isinstance(features[0], dict):
                attrs = features[0].get("attributes")
                if isinstance(attrs, dict):
                    sample_attributes = {
                        key: attrs[key]
                        for key in list(attrs.keys())[:8]
                    }

            selected = {
                "source_item_title": source_item.get("title", ""),
                "source_item_id": source_item.get("id", ""),
                "layer_url": layer_url,
                "metadata_url": metadata_url,
                "query_url": query_url,
                "row_count_sampled": len(features),
                "identity_fields": identity_fields,
                "date_fields": date_fields,
                "sample_attributes": sample_attributes,
            }
            break
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{layer_url}: {exc}")

    passed = selected is not None
    return {
        "source_family": "arcgis_rest_public",
        "probe_name": "Public ArcGIS REST/Hub Bay Area endpoint",
        "sample_pull_without_browser": passed,
        "status": "pass" if passed else "fail",
        "search_url": search_url,
        "candidate_count": len(candidates),
        "selected": selected or {},
        "errors": errors,
    }


def _build_summary(probes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    statuses = {name: item.get("status", "fail") for name, item in probes.items()}
    sample_pull_count = sum(1 for item in probes.values() if item.get("sample_pull_without_browser") is True)
    failed = sorted(name for name, status in statuses.items() if status != "pass")
    acceptance = (
        probes.get("legistar", {}).get("sample_pull_without_browser") is True
        and (
            probes.get("leginfo", {}).get("sample_pull_without_browser") is True
            or probes.get("arcgis", {}).get("sample_pull_without_browser") is True
        )
    )
    return {
        "total_sources": len(probes),
        "passed_sources": len(probes) - len(failed),
        "failed_sources": len(failed),
        "failed_source_ids": failed,
        "sample_pull_without_browser_count": sample_pull_count,
        "acceptance_legistar_and_one_other": acceptance,
        "acceptance_legistar_or_leginfo_or_arcgis": acceptance,
    }


def _source_catalog_from_probes(probes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    leginfo = probes.get("leginfo", {})
    legistar = probes.get("legistar", {})
    arcgis = probes.get("arcgis", {})
    arcgis_selected = arcgis.get("selected", {})
    if not isinstance(arcgis_selected, dict):
        arcgis_selected = {}

    return [
        {
            "source_family": "ca_pubinfo_leginfo",
            "probe_id": "leginfo",
            "signup_or_key_link": "none_required",
            "free_status": "free_public",
            "api_or_raw_confirmed": "raw_official_file",
            "sample_endpoint_or_file_url": LEGINFO_DAILY,
            "auth_required": "no",
            "recommendation": (
                "structured_lane"
                if leginfo.get("sample_pull_without_browser") is True
                else "blocked"
            ),
            "probe_status": leginfo.get("status", "fail"),
        },
        {
            "source_family": "legistar_sanjose",
            "probe_id": "legistar",
            "signup_or_key_link": "none_required",
            "free_status": "free_public",
            "api_or_raw_confirmed": "api",
            "sample_endpoint_or_file_url": LEGISTAR_ENDPOINT,
            "auth_required": "no",
            "recommendation": (
                "structured_lane"
                if legistar.get("sample_pull_without_browser") is True
                else "blocked"
            ),
            "probe_status": legistar.get("status", "fail"),
        },
        {
            "source_family": "arcgis_public_gis_dataset",
            "probe_id": "arcgis",
            "signup_or_key_link": "none_required",
            "free_status": "free_public",
            "api_or_raw_confirmed": "api",
            "sample_endpoint_or_file_url": arcgis_selected.get("query_url")
            or arcgis_selected.get("layer_url")
            or ARCGIS_SEARCH_ENDPOINT,
            "auth_required": "no",
            "recommendation": (
                "structured_lane"
                if arcgis.get("sample_pull_without_browser") is True
                else "blocked"
            ),
            "probe_status": arcgis.get("status", "fail"),
            "selected_title": arcgis_selected.get("source_item_title", ""),
        },
    ]


def _validate_report_contract(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("feature_key", "poc_version", "mode", "generated_at", "probes", "summary"):
        if key not in report:
            errors.append(f"missing_top_level_key:{key}")
    probes = report.get("probes")
    if not isinstance(probes, dict):
        errors.append("probes_not_object")
        return errors
    for source_id in ("leginfo", "legistar", "arcgis"):
        probe = probes.get(source_id)
        if not isinstance(probe, dict):
            errors.append(f"missing_probe:{source_id}")
            continue
        for key in ("source_family", "probe_name", "status", "sample_pull_without_browser"):
            if key not in probe:
                errors.append(f"missing_probe_key:{source_id}:{key}")
    summary = report.get("summary")
    if isinstance(summary, dict):
        if "acceptance_legistar_and_one_other" not in summary:
            errors.append("missing_summary_key:acceptance_legistar_and_one_other")
    else:
        errors.append("summary_not_object")
    sources = report.get("sources")
    if not isinstance(sources, list) or len(sources) != 3:
        errors.append("sources_not_three_item_list")
    return errors


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Structured Source Lane POC Report ({report['mode']})")
    lines.append("")
    lines.append(f"- Feature key: `{report['feature_key']}`")
    lines.append(f"- Version: `{report['poc_version']}`")
    lines.append(f"- Generated at: `{report['generated_at']}`")
    lines.append("")
    summary = report["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Sources passed: **{summary['passed_sources']} / {summary['total_sources']}**")
    lines.append(
        f"- `sample_pull_without_browser` count: **{summary['sample_pull_without_browser_count']}**"
    )
    lines.append(
        "- Acceptance (`legistar` and one of `leginfo`/`arcgis`): "
        + ("**PASS**" if summary["acceptance_legistar_and_one_other"] else "**FAIL**")
    )
    if summary["failed_source_ids"]:
        lines.append(f"- Failed source IDs: `{', '.join(summary['failed_source_ids'])}`")
    lines.append("")
    lines.append("## Probe Details")
    lines.append("")
    for source_id, probe in report["probes"].items():
        lines.append(f"### {source_id}")
        lines.append("")
        lines.append(f"- Source family: `{probe.get('source_family', '')}`")
        lines.append(f"- Probe name: `{probe.get('probe_name', '')}`")
        lines.append(f"- Status: `{probe.get('status', 'fail')}`")
        lines.append(
            "- sample_pull_without_browser: "
            + ("`yes`" if probe.get("sample_pull_without_browser") else "`no`")
        )
        errors = probe.get("errors", [])
        if isinstance(errors, list) and errors:
            lines.append(f"- Errors: `{'; '.join(str(e) for e in errors[:3])}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_replay(config: ProbeConfig) -> dict[str, dict[str, Any]]:
    fixture = _load_json(config.replay_fixture)
    probes = fixture.get("probes", {})
    if not isinstance(probes, dict):
        raise ValueError("replay fixture missing probes object")
    required = {"leginfo", "legistar", "arcgis"}
    if not required.issubset(set(probes.keys())):
        raise ValueError("replay fixture missing required probes")
    return {
        "leginfo": dict(probes["leginfo"]),
        "legistar": dict(probes["legistar"]),
        "arcgis": dict(probes["arcgis"]),
    }


def _run_live(config: ProbeConfig) -> dict[str, dict[str, Any]]:
    probes = {
        "leginfo": _probe_leginfo_live(config.timeout_seconds),
        "legistar": _probe_legistar_live(config.timeout_seconds),
        "arcgis": _probe_arcgis_live(config.timeout_seconds),
    }
    if config.save_live_replay is not None:
        _write_json(config.save_live_replay, {"probes": probes, "saved_at": _now_iso()})
    return probes


def _run(config: ProbeConfig) -> dict[str, Any]:
    if config.mode == MODE_REPLAY:
        probes = _run_replay(config)
    elif config.mode == MODE_LIVE:
        probes = _run_live(config)
    else:
        if config.replay_fixture.exists():
            probes = _run_replay(config)
        else:
            probes = _run_live(config)

    report = {
        "feature_key": FEATURE_KEY,
        "poc_version": POC_VERSION,
        "mode": config.mode,
        "generated_at": _now_iso(),
        "probes": probes,
        "sources": _source_catalog_from_probes(probes),
        "summary": _build_summary(probes),
    }
    _write_json(config.out_json, report)
    _write_markdown(config.out_md, _render_markdown(report))

    if config.self_check:
        contract_errors = _validate_report_contract(report)
        if contract_errors:
            for err in contract_errors:
                print(err, file=sys.stderr)
            raise SystemExit(2)
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=(MODE_AUTO, MODE_LIVE, MODE_REPLAY), default=MODE_AUTO)
    parser.add_argument("--timeout-seconds", type=float, default=12.0)
    parser.add_argument("--replay-fixture", type=Path, default=DEFAULT_REPLAY_FIXTURE)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    parser.add_argument("--save-live-replay", type=Path, default=None)
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Validate generated report contract and exit non-zero on contract errors.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    config = ProbeConfig(
        mode=args.mode,
        timeout_seconds=args.timeout_seconds,
        replay_fixture=args.replay_fixture,
        out_json=args.out_json,
        out_md=args.out_md,
        save_live_replay=args.save_live_replay,
        self_check=args.self_check,
    )
    _run(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
