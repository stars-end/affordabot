#!/usr/bin/env python3
"""Structured-source breadth and policy relevance audit (bd-2agbe.9).

This script audits public/no-key structured source candidates for wave-1 intake.
It separates source availability, auth status, API/raw accessibility, policy
relevance, and downstream economic usefulness.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError


FEATURE_KEY = "bd-2agbe.9"
ARTIFACT_VERSION = "2026-04-14.structured-source-breadth.v1"

MODE_LIVE = "live"
MODE_REPLAY = "replay"

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "structured-source-lane"
    / "artifacts"
    / "structured_source_breadth_audit.json"
)
OUT_MD = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "structured-source-lane"
    / "artifacts"
    / "structured_source_breadth_audit.md"
)
CATALOG_BASENAME_JSON = "structured_source_catalog.json"
CATALOG_BASENAME_MD = "structured_source_catalog.md"

LEGISTAR_URL = "https://webapi.legistar.com/v1/sanjose/matters?$top=3"
LEGINFO_ROOT = "https://downloads.leginfo.legislature.ca.gov/"
LEGINFO_DAILY = "https://downloads.leginfo.legislature.ca.gov/pubinfo_daily_Mon.zip"
ARCGIS_SEARCH = "https://www.arcgis.com/sharing/rest/search"
CA_CKAN_SEARCH = "https://data.ca.gov/api/3/action/package_search?rows=3&q=housing+zoning+permit"
ODS_PUBLIC_CATALOG = "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets?limit=1"
CENSUS_XLSX = (
    "https://www2.census.gov/programs-surveys/metro-micro/geographies/"
    "reference-files/2023/delineation-files/list1_2023.xlsx"
)


REPLAY_CANDIDATES: list[dict[str, Any]] = [
    {
        "source_family": "legistar_sanjose",
        "jurisdiction_scope": "city_san_jose",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "api",
        "sample_endpoint_or_file_url": LEGISTAR_URL,
        "auth_required": "no",
        "recommendation": "structured_lane",
        "policy_mechanism_relevance": "direct_fiscal",
        "live_probe_status": "pass",
        "evidence_summary": "Replay fixture indicates row payload with Matter identifiers.",
        "downstream_economic_usefulness": "high",
    },
    {
        "source_family": "ca_pubinfo_leginfo",
        "jurisdiction_scope": "state_california",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "raw_official_file",
        "sample_endpoint_or_file_url": LEGINFO_DAILY,
        "auth_required": "no",
        "recommendation": "structured_lane",
        "policy_mechanism_relevance": "land_use_capacity",
        "live_probe_status": "pass",
        "evidence_summary": "Replay fixture indicates official PUBINFO feed and daily archive reachable.",
        "downstream_economic_usefulness": "high",
    },
    {
        "source_family": "arcgis_public_gis_dataset",
        "jurisdiction_scope": "regional_public_gis",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "api",
        "sample_endpoint_or_file_url": "https://services2.arcgis.com/.../FeatureServer/0/query",
        "auth_required": "no",
        "recommendation": "structured_lane",
        "policy_mechanism_relevance": "contextual_only",
        "live_probe_status": "pass",
        "evidence_summary": "Replay fixture confirms ArcGIS REST mechanics only; policy-specific zoning/parcel relevance not guaranteed.",
        "downstream_economic_usefulness": "medium",
    },
    {
        "source_family": "ca_ckan_open_data_catalog",
        "jurisdiction_scope": "state_california",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "api",
        "sample_endpoint_or_file_url": CA_CKAN_SEARCH,
        "auth_required": "no",
        "recommendation": "structured_lane",
        "policy_mechanism_relevance": "household_affordability",
        "live_probe_status": "pass",
        "evidence_summary": "Replay fixture includes CKAN package_search response envelope.",
        "downstream_economic_usefulness": "medium",
    },
    {
        "source_family": "public_opendatasoft_catalog",
        "jurisdiction_scope": "multi_jurisdiction",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "api",
        "sample_endpoint_or_file_url": ODS_PUBLIC_CATALOG,
        "auth_required": "no",
        "recommendation": "backlog",
        "policy_mechanism_relevance": "unknown",
        "live_probe_status": "pass",
        "evidence_summary": "Replay fixture confirms ODS catalog API shape; local-jurisdiction dataset mapping still required.",
        "downstream_economic_usefulness": "low",
    },
    {
        "source_family": "official_static_xlsx_census",
        "jurisdiction_scope": "national_context",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "raw_public_file",
        "sample_endpoint_or_file_url": CENSUS_XLSX,
        "auth_required": "no",
        "recommendation": "backlog",
        "policy_mechanism_relevance": "contextual_only",
        "live_probe_status": "pass",
        "evidence_summary": "Replay fixture confirms direct XLSX retrieval from official Census domain.",
        "downstream_economic_usefulness": "low",
    },
    {
        "source_family": "socrata_open_data_portals",
        "jurisdiction_scope": "city_county_varies",
        "signup_or_key_link": "https://dev.socrata.com/",
        "free_status": "free_tier_key_optional_limits",
        "api_or_raw_confirmed": "api",
        "sample_endpoint_or_file_url": "https://dev.socrata.com/foundry/data.sanjoseca.gov/example",
        "auth_required": "no_key_for_small_queries_but_key_recommended",
        "recommendation": "backlog",
        "policy_mechanism_relevance": "direct_fiscal",
        "live_probe_status": "not_run",
        "evidence_summary": "Excluded from this POC by explicit user constraint: no Socrata signup now.",
        "downstream_economic_usefulness": "high",
    },
    {
        "source_family": "granicus_agenda_portals",
        "jurisdiction_scope": "city_county_varies",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "not_confirmed",
        "sample_endpoint_or_file_url": "https://johnscreekga.granicus.com/ViewPublisher.php?view_id=1",
        "auth_required": "no",
        "recommendation": "scrape_reader_lane",
        "policy_mechanism_relevance": "compliance_cost",
        "live_probe_status": "not_run",
        "evidence_summary": "Agenda portals are generally HTML/PDF-first and belong to scrape+reader lane.",
        "downstream_economic_usefulness": "medium",
    },
]

SOURCE_CATALOG_PROFILES: dict[str, dict[str, Any]] = {
    "legistar_sanjose": {
        "access_method": "rest_api",
        "jurisdiction_coverage": "city_san_jose",
        "cadence_freshness": "agenda_and_minutes_event_driven",
        "storage_target": "postgres_source_snapshots+minio_raw_artifacts",
        "mechanism_economic_usefulness_score": 95,
        "runtime_integration_status": "runtime_integrated",
    },
    "ca_pubinfo_leginfo": {
        "access_method": "official_raw_file_zip",
        "jurisdiction_coverage": "state_california",
        "cadence_freshness": "daily_pubinfo_feed",
        "storage_target": "postgres_source_snapshots+minio_raw_artifacts",
        "mechanism_economic_usefulness_score": 92,
        "runtime_integration_status": "runtime_integrated",
    },
    "arcgis_public_gis_dataset": {
        "access_method": "rest_api_feature_service",
        "jurisdiction_coverage": "regional_multi_county",
        "cadence_freshness": "dataset_defined_variable",
        "storage_target": "postgres_source_snapshots+minio_raw_artifacts",
        "mechanism_economic_usefulness_score": 62,
        "runtime_integration_status": "poc_only",
    },
    "ca_ckan_open_data_catalog": {
        "access_method": "ckan_api",
        "jurisdiction_coverage": "state_california",
        "cadence_freshness": "dataset_defined_variable",
        "storage_target": "postgres_source_snapshots+minio_raw_artifacts",
        "mechanism_economic_usefulness_score": 70,
        "runtime_integration_status": "poc_only",
    },
    "public_opendatasoft_catalog": {
        "access_method": "catalog_api",
        "jurisdiction_coverage": "multi_jurisdiction",
        "cadence_freshness": "dataset_defined_variable",
        "storage_target": "candidate_catalog_only",
        "mechanism_economic_usefulness_score": 35,
        "runtime_integration_status": "poc_only",
    },
    "official_static_xlsx_census": {
        "access_method": "raw_file_download",
        "jurisdiction_coverage": "national_context",
        "cadence_freshness": "annual_or_periodic_release",
        "storage_target": "candidate_catalog_only",
        "mechanism_economic_usefulness_score": 40,
        "runtime_integration_status": "poc_only",
    },
    "socrata_open_data_portals": {
        "access_method": "socrata_api",
        "jurisdiction_coverage": "city_county_varies",
        "cadence_freshness": "dataset_defined_variable",
        "storage_target": "candidate_catalog_only",
        "mechanism_economic_usefulness_score": 76,
        "runtime_integration_status": "poc_only",
    },
    "granicus_agenda_portals": {
        "access_method": "html_pdf_portal",
        "jurisdiction_coverage": "city_county_varies",
        "cadence_freshness": "meeting_event_driven",
        "storage_target": "scrape_reader_lane_minio_raw_artifacts",
        "mechanism_economic_usefulness_score": 58,
        "runtime_integration_status": "poc_only",
    },
}


@dataclass(frozen=True)
class AuditConfig:
    mode: str
    timeout_seconds: float
    out_json: Path
    out_md: Path
    self_check: bool


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _http_request(
    *,
    url: str,
    method: str,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    req = urllib.request.Request(url=url, method=method.upper())
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        return {
            "status": int(getattr(response, "status", response.getcode())),
            "headers": dict(response.headers.items()),
            "body": response.read(),
        }


def _json_get(url: str, timeout_seconds: float) -> Any:
    resp = _http_request(url=url, method="GET", timeout_seconds=timeout_seconds)
    body = resp["body"]
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _probe_legistar(timeout_seconds: float) -> dict[str, Any]:
    row_count = 0
    keys_present = False
    error = ""
    try:
        payload = _json_get(LEGISTAR_URL, timeout_seconds)
        rows = payload if isinstance(payload, list) else []
        row_count = len(rows)
        if rows and isinstance(rows[0], dict):
            keys_present = all(k in rows[0] for k in ("MatterId", "MatterFile"))
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        error = str(exc)

    status = "pass" if row_count > 0 and keys_present else "fail"
    evidence = (
        f"rows={row_count}, keys_present={keys_present}"
        if status == "pass"
        else f"probe_error={error or 'empty payload'}"
    )
    return {
        "source_family": "legistar_sanjose",
        "jurisdiction_scope": "city_san_jose",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "api" if status == "pass" else "not_confirmed",
        "sample_endpoint_or_file_url": LEGISTAR_URL,
        "auth_required": "no",
        "recommendation": "structured_lane",
        "policy_mechanism_relevance": "direct_fiscal",
        "live_probe_status": status,
        "evidence_summary": evidence,
        "downstream_economic_usefulness": "high",
    }


def _probe_leginfo(timeout_seconds: float) -> dict[str, Any]:
    root_status = 0
    daily_status = 0
    error = ""
    try:
        root_resp = _http_request(url=LEGINFO_ROOT, method="HEAD", timeout_seconds=timeout_seconds)
        root_status = int(root_resp["status"])
        daily_resp = _http_request(url=LEGINFO_DAILY, method="HEAD", timeout_seconds=timeout_seconds)
        daily_status = int(daily_resp["status"])
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        error = str(exc)

    ok = 200 <= root_status < 400 and 200 <= daily_status < 400
    return {
        "source_family": "ca_pubinfo_leginfo",
        "jurisdiction_scope": "state_california",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "raw_official_file" if ok else "not_confirmed",
        "sample_endpoint_or_file_url": LEGINFO_DAILY,
        "auth_required": "no",
        "recommendation": "structured_lane",
        "policy_mechanism_relevance": "land_use_capacity",
        "live_probe_status": "pass" if ok else "fail",
        "evidence_summary": (
            f"root_head={root_status}, daily_head={daily_status}" if ok else f"probe_error={error or 'non-2xx/3xx status'}"
        ),
        "downstream_economic_usefulness": "high",
    }


def _arcgis_search_url() -> str:
    q = (
        '("San Jose" OR "Santa Clara") AND '
        '("zoning" OR "parcel" OR "permit" OR "housing" OR "fee" OR "budget" OR "flood") AND '
        '("FeatureServer" OR "MapServer")'
    )
    params = {
        "f": "json",
        "num": "15",
        "sortField": "numviews",
        "sortOrder": "desc",
        "q": q,
    }
    return f"{ARCGIS_SEARCH}?{urllib.parse.urlencode(params)}"


def _probe_arcgis(timeout_seconds: float) -> dict[str, Any]:
    error = ""
    selected_url = ""
    title = ""
    policy_specific = False
    try:
        payload = _json_get(_arcgis_search_url(), timeout_seconds)
        results = payload.get("results", []) if isinstance(payload, dict) else []
        for item in results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            if "FeatureServer" not in url and "MapServer" not in url:
                continue
            selected_url = url
            title = str(item.get("title") or "")
            combined = f"{title} {item.get('snippet', '')}".lower()
            policy_specific = any(x in combined for x in ("zoning", "parcel", "permit", "housing", "budget", "fee"))
            break
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        error = str(exc)

    if selected_url:
        status = "pass"
        api_conf = "api"
        policy_relevance = "land_use_capacity" if policy_specific else "contextual_only"
        evidence = (
            f"selected_title={title!r}; policy_specific_match={policy_specific}. "
            "ArcGIS probe confirms public GIS API mechanics; policy-specific San Jose zoning/parcel/housing may require tighter curation."
        )
    else:
        status = "fail"
        api_conf = "not_confirmed"
        policy_relevance = "unknown"
        evidence = f"probe_error={error or 'no FeatureServer/MapServer hit'}"

    return {
        "source_family": "arcgis_public_gis_dataset",
        "jurisdiction_scope": "regional_public_gis",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": api_conf,
        "sample_endpoint_or_file_url": selected_url or _arcgis_search_url(),
        "auth_required": "no",
        "recommendation": "structured_lane" if status == "pass" else "backlog",
        "policy_mechanism_relevance": policy_relevance,
        "live_probe_status": status,
        "evidence_summary": evidence,
        "downstream_economic_usefulness": "medium",
    }


def _probe_ckan(timeout_seconds: float) -> dict[str, Any]:
    count = 0
    error = ""
    try:
        payload = _json_get(CA_CKAN_SEARCH, timeout_seconds)
        if isinstance(payload, dict):
            result = payload.get("result", {})
            if isinstance(result, dict):
                count = int(result.get("count") or 0)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        error = str(exc)
    ok = count >= 0 and not error
    return {
        "source_family": "ca_ckan_open_data_catalog",
        "jurisdiction_scope": "state_california",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "api" if ok else "not_confirmed",
        "sample_endpoint_or_file_url": CA_CKAN_SEARCH,
        "auth_required": "no",
        "recommendation": "structured_lane" if ok else "backlog",
        "policy_mechanism_relevance": "household_affordability",
        "live_probe_status": "pass" if ok else "fail",
        "evidence_summary": f"package_count={count}" if ok else f"probe_error={error}",
        "downstream_economic_usefulness": "medium",
    }


def _probe_opendatasoft(timeout_seconds: float) -> dict[str, Any]:
    count = 0
    error = ""
    try:
        payload = _json_get(ODS_PUBLIC_CATALOG, timeout_seconds)
        if isinstance(payload, dict):
            total = payload.get("total_count")
            count = int(total) if total is not None else 0
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        error = str(exc)
    ok = count >= 0 and not error
    return {
        "source_family": "public_opendatasoft_catalog",
        "jurisdiction_scope": "multi_jurisdiction",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "api" if ok else "not_confirmed",
        "sample_endpoint_or_file_url": ODS_PUBLIC_CATALOG,
        "auth_required": "no",
        "recommendation": "backlog",
        "policy_mechanism_relevance": "unknown",
        "live_probe_status": "pass" if ok else "fail",
        "evidence_summary": (
            f"catalog_total_count={count}; API reachable, but local policy-specific dataset binding not done."
            if ok
            else f"probe_error={error}"
        ),
        "downstream_economic_usefulness": "low",
    }


def _probe_static_xlsx(timeout_seconds: float) -> dict[str, Any]:
    status = 0
    error = ""
    try:
        resp = _http_request(
            url=CENSUS_XLSX,
            method="GET",
            timeout_seconds=timeout_seconds,
            headers={"Range": "bytes=0-2048"},
        )
        status = int(resp["status"])
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        error = str(exc)
    ok = 200 <= status < 400
    return {
        "source_family": "official_static_xlsx_census",
        "jurisdiction_scope": "national_context",
        "signup_or_key_link": "none_required",
        "free_status": "free_public",
        "api_or_raw_confirmed": "raw_public_file" if ok else "not_confirmed",
        "sample_endpoint_or_file_url": CENSUS_XLSX,
        "auth_required": "no",
        "recommendation": "backlog",
        "policy_mechanism_relevance": "contextual_only",
        "live_probe_status": "pass" if ok else "fail",
        "evidence_summary": f"http_status={status}" if ok else f"probe_error={error or status}",
        "downstream_economic_usefulness": "low",
    }


def _manual_backlog_entries() -> list[dict[str, Any]]:
    return [
        {
            "source_family": "socrata_open_data_portals",
            "jurisdiction_scope": "city_county_varies",
            "signup_or_key_link": "https://dev.socrata.com/",
            "free_status": "free_tier_key_optional_limits",
            "api_or_raw_confirmed": "api",
            "sample_endpoint_or_file_url": "https://dev.socrata.com/foundry/data.sanjoseca.gov/example",
            "auth_required": "no_key_for_small_queries_but_key_recommended",
            "recommendation": "backlog",
            "policy_mechanism_relevance": "direct_fiscal",
            "live_probe_status": "not_run",
            "evidence_summary": "Explicitly excluded from this POC by user decision: no Socrata signup at this time.",
            "downstream_economic_usefulness": "high",
        },
        {
            "source_family": "granicus_agenda_portals",
            "jurisdiction_scope": "city_county_varies",
            "signup_or_key_link": "none_required",
            "free_status": "free_public",
            "api_or_raw_confirmed": "not_confirmed",
            "sample_endpoint_or_file_url": "https://johnscreekga.granicus.com/ViewPublisher.php?view_id=1",
            "auth_required": "no",
            "recommendation": "scrape_reader_lane",
            "policy_mechanism_relevance": "compliance_cost",
            "live_probe_status": "not_run",
            "evidence_summary": "Portal-first HTML/PDF source; classify into scrape+reader lane.",
            "downstream_economic_usefulness": "medium",
        },
    ]


def _live_candidates(timeout_seconds: float) -> list[dict[str, Any]]:
    out = [
        _probe_legistar(timeout_seconds),
        _probe_leginfo(timeout_seconds),
        _probe_arcgis(timeout_seconds),
        _probe_ckan(timeout_seconds),
        _probe_opendatasoft(timeout_seconds),
        _probe_static_xlsx(timeout_seconds),
    ]
    out.extend(_manual_backlog_entries())
    return out


def _summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    by_recommendation: dict[str, int] = {}
    by_probe: dict[str, int] = {}
    for item in candidates:
        rec = str(item["recommendation"])
        by_recommendation[rec] = by_recommendation.get(rec, 0) + 1
        probe = str(item["live_probe_status"])
        by_probe[probe] = by_probe.get(probe, 0) + 1
    wave1_families = [
        item["source_family"]
        for item in candidates
        if item["recommendation"] == "structured_lane"
        and item["downstream_economic_usefulness"] in {"high", "medium"}
    ]
    runtime_status_counts: dict[str, int] = {}
    score_total = 0
    score_count = 0
    for item in candidates:
        runtime_status = str(item.get("runtime_integration_status", "unknown"))
        runtime_status_counts[runtime_status] = runtime_status_counts.get(runtime_status, 0) + 1
        score = item.get("mechanism_economic_usefulness_score")
        if isinstance(score, int):
            score_total += score
            score_count += 1
    return {
        "total_candidates": len(candidates),
        "by_recommendation": by_recommendation,
        "by_live_probe_status": by_probe,
        "by_runtime_integration_status": runtime_status_counts,
        "average_mechanism_economic_usefulness_score": (
            round(score_total / score_count, 2) if score_count else 0.0
        ),
        "wave1_structured_feeds": wave1_families,
        "notes": (
            "ArcGIS confirms public GIS API mechanics. Policy-specific zoning/parcel/housing "
            "coverage still needs catalog curation before production reliance."
        ),
    }


def _enrich_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    source_family = str(candidate.get("source_family", ""))
    profile = SOURCE_CATALOG_PROFILES.get(source_family, {})
    enriched = dict(candidate)
    enriched["access_method"] = profile.get("access_method", "unknown")
    enriched["jurisdiction_coverage"] = profile.get("jurisdiction_coverage", "unknown")
    enriched["cadence_freshness"] = profile.get("cadence_freshness", "unknown")
    enriched["storage_target"] = profile.get("storage_target", "candidate_catalog_only")
    enriched["mechanism_economic_usefulness_score"] = int(
        profile.get("mechanism_economic_usefulness_score", 0)
    )
    enriched["runtime_integration_status"] = profile.get(
        "runtime_integration_status", "poc_only"
    )
    return enriched


def _catalog_paths(config: AuditConfig) -> tuple[Path, Path]:
    return (
        config.out_json.with_name(CATALOG_BASENAME_JSON),
        config.out_md.with_name(CATALOG_BASENAME_MD),
    )


def _render_catalog_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Structured Source Catalog",
        "",
        f"- Feature key: `{payload['feature_key']}`",
        f"- Artifact version: `{payload['artifact_version']}`",
        f"- Mode: `{payload['mode']}`",
        f"- Generated at: `{payload['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- Total catalog rows: `{payload['summary']['total_rows']}`",
        f"- Runtime integrated: `{payload['summary']['runtime_integrated_count']}`",
        f"- POC only: `{payload['summary']['poc_only_count']}`",
        f"- Average usefulness score: `{payload['summary']['average_mechanism_economic_usefulness_score']}`",
        "",
        "## Catalog Matrix",
        "",
        "| source_family | free_status | signup_or_key | access_method | jurisdiction_coverage | cadence_freshness | storage_target | runtime_status | usefulness_score |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["catalog_rows"]:
        lines.append(
            "| {source_family} | {free_status} | {signup_or_key_link} | {access_method} | "
            "{jurisdiction_coverage} | {cadence_freshness} | {storage_target} | "
            "{runtime_integration_status} | {mechanism_economic_usefulness_score} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def _build_catalog_payload(
    *,
    candidates: list[dict[str, Any]],
    mode: str,
    generated_at: str,
) -> dict[str, Any]:
    rows = [
        {
            "source_family": item["source_family"],
            "free_status": item["free_status"],
            "signup_or_key_link": item["signup_or_key_link"],
            "access_method": item["access_method"],
            "api_or_raw_confirmed": item["api_or_raw_confirmed"],
            "jurisdiction_coverage": item["jurisdiction_coverage"],
            "jurisdiction_scope": item["jurisdiction_scope"],
            "cadence_freshness": item["cadence_freshness"],
            "storage_target": item["storage_target"],
            "policy_mechanism_relevance": item["policy_mechanism_relevance"],
            "mechanism_economic_usefulness_score": item["mechanism_economic_usefulness_score"],
            "runtime_integration_status": item["runtime_integration_status"],
            "recommendation": item["recommendation"],
            "live_probe_status": item["live_probe_status"],
            "sample_endpoint_or_file_url": item["sample_endpoint_or_file_url"],
        }
        for item in candidates
    ]
    runtime_integrated_count = len(
        [row for row in rows if row["runtime_integration_status"] == "runtime_integrated"]
    )
    score_values = [row["mechanism_economic_usefulness_score"] for row in rows]
    return {
        "feature_key": FEATURE_KEY,
        "artifact_version": ARTIFACT_VERSION,
        "mode": mode,
        "generated_at": generated_at,
        "catalog_rows": rows,
        "summary": {
            "total_rows": len(rows),
            "runtime_integrated_count": runtime_integrated_count,
            "poc_only_count": len(rows) - runtime_integrated_count,
            "average_mechanism_economic_usefulness_score": (
                round(sum(score_values) / len(score_values), 2) if score_values else 0.0
            ),
        },
    }


def _validate(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_top = ("feature_key", "artifact_version", "mode", "generated_at", "candidates", "summary")
    for key in required_top:
        if key not in report:
            errors.append(f"missing_top_key:{key}")
    candidates = report.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("invalid_candidates")
        return errors
    required_candidate = (
        "source_family",
        "jurisdiction_scope",
        "signup_or_key_link",
        "free_status",
        "api_or_raw_confirmed",
        "access_method",
        "jurisdiction_coverage",
        "cadence_freshness",
        "storage_target",
        "mechanism_economic_usefulness_score",
        "runtime_integration_status",
        "sample_endpoint_or_file_url",
        "auth_required",
        "recommendation",
        "policy_mechanism_relevance",
        "live_probe_status",
        "evidence_summary",
        "downstream_economic_usefulness",
    )
    for i, item in enumerate(candidates):
        if not isinstance(item, dict):
            errors.append(f"candidate_not_object:{i}")
            continue
        for key in required_candidate:
            if key not in item:
                errors.append(f"candidate_missing_key:{i}:{key}")
    return errors


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Structured Source Breadth Audit",
        "",
        f"- Feature key: `{report['feature_key']}`",
        f"- Artifact version: `{report['artifact_version']}`",
        f"- Mode: `{report['mode']}`",
        f"- Generated at: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- Total candidates: `{report['summary']['total_candidates']}`",
        f"- By recommendation: `{json.dumps(report['summary']['by_recommendation'], sort_keys=True)}`",
        f"- By live probe status: `{json.dumps(report['summary']['by_live_probe_status'], sort_keys=True)}`",
        f"- Wave-1 structured feeds: `{', '.join(report['summary']['wave1_structured_feeds'])}`",
        f"- Note: {report['summary']['notes']}",
        "",
        "## Candidate Matrix",
        "",
        "| source_family | scope | recommendation | relevance | probe | api/raw | usefulness |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in report["candidates"]:
        lines.append(
            "| {source_family} | {jurisdiction_scope} | {recommendation} | "
            "{policy_mechanism_relevance} | {live_probe_status} | {api_or_raw_confirmed} | "
            "{downstream_economic_usefulness} |".format(**item)
        )
    lines.extend(["", "## Evidence Notes", ""])
    for item in report["candidates"]:
        lines.append(f"- `{item['source_family']}`: {item['evidence_summary']}")
    lines.append("")
    return "\n".join(lines)


def _run(config: AuditConfig) -> dict[str, Any]:
    if config.mode == MODE_REPLAY:
        candidates = [dict(item) for item in REPLAY_CANDIDATES]
    else:
        candidates = _live_candidates(config.timeout_seconds)
    candidates = [_enrich_candidate(item) for item in candidates]
    generated_at = _now_iso()
    report = {
        "feature_key": FEATURE_KEY,
        "artifact_version": ARTIFACT_VERSION,
        "mode": config.mode,
        "generated_at": generated_at,
        "candidates": candidates,
        "summary": _summary(candidates),
    }
    _write_json(config.out_json, report)
    config.out_md.parent.mkdir(parents=True, exist_ok=True)
    config.out_md.write_text(_to_markdown(report), encoding="utf-8")
    catalog_json_path, catalog_md_path = _catalog_paths(config)
    catalog_payload = _build_catalog_payload(
        candidates=candidates,
        mode=config.mode,
        generated_at=generated_at,
    )
    _write_json(catalog_json_path, catalog_payload)
    catalog_md_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_md_path.write_text(
        _render_catalog_markdown(catalog_payload),
        encoding="utf-8",
    )
    return report


def _parse_args() -> AuditConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=(MODE_LIVE, MODE_REPLAY), default=MODE_REPLAY)
    parser.add_argument("--timeout-seconds", type=float, default=12.0)
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=OUT_MD)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    return AuditConfig(
        mode=args.mode,
        timeout_seconds=float(args.timeout_seconds),
        out_json=args.out_json,
        out_md=args.out_md,
        self_check=bool(args.self_check),
    )


def main() -> int:
    config = _parse_args()
    report = _run(config)
    if config.self_check:
        errors = _validate(report)
        if errors:
            for error in errors:
                print(f"SELF_CHECK_ERROR {error}")
            return 1
        print("SELF_CHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
