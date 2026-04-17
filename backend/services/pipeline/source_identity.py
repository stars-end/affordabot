"""Central source identity, officialness, and durability classification.

This module is the single backend-owned surface for source identity gates used
by ranking, package assembly, and quality-spine scorecards.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from services.substrate_promotion import classify_host


SOURCE_IDENTITY_RULESET_VERSION = "2026-04-17.local-government-source-identity.v1"

OFFICIAL_DOMINANCE_TARGETS = {
    "audited_p0_p1_target_percent": 90.0,
    "corpus_target_percent": 85.0,
    "hard_fail_below_percent": 80.0,
}

SECONDARY_PROVIDER_PRIMARY_CAPS = {
    "audited_tavily_exa_max_percent": 0.0,
    "corpus_tavily_exa_max_percent": 5.0,
}

_SECONDARY_SEARCH_PROVIDERS = {
    "tavily",
    "tavily_search",
    "tavily_search_api",
    "exa",
    "exa_search",
}

_APPROVED_PROMOTION_AUDIT_STATUSES = {
    "approved",
    "audited_pass",
    "manual_approved",
    "reviewed",
}

_EXTERNAL_ADVOCACY_HINTS = (
    "sierraclub",
    "nrdc",
    "coalition",
    "advocacy",
    "actionnetwork",
    "campaign",
    "nonprofit",
)

_EXTERNAL_NEWS_HINTS = (
    "news",
    "times",
    "post",
    "tribune",
    "chronicle",
    "planetizen",
    "press",
    "journal",
    "patch.com",
)

_EXTERNAL_VENDOR_HINTS = (
    "vendor",
    "consulting",
    "services",
    "civicplus",
    "municodeweb",
    "mygovservice",
    "opengov",
)

_AMBIGUOUS_PORTAL_HINTS = (
    "portal",
    "agendaonline",
    "cityplatform",
    "civicclerk",
    "govqa",
)

_POLICY_FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "commercial_linkage_fee": (
        "commercial linkage",
        "linkage fee",
        "impact fee",
        "fee schedule",
    ),
    "parking_policy": ("parking", "parking minimum", "parking requirement"),
    "housing_permits": ("housing permit", "building permit", "permit issuance"),
    "business_compliance": (
        "business license",
        "inspection",
        "compliance",
        "code enforcement",
    ),
    "meeting_action": ("agenda", "minutes", "ordinance", "resolution", "council"),
    "zoning_land_use": ("zoning", "land use", "general plan", "rezoning"),
    "procurement_contract": ("procurement", "contract award", "rfp", "bid"),
    "public_safety": ("public safety", "police", "fire department", "emergency"),
    "general_governance": (
        "policy",
        "regulation",
        "regulatory",
        "rulemaking",
        "governance",
        "municipal code",
    ),
}

_CADENCE_DAYS = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "quarterly": 90,
    "annual": 365,
}


def source_identity_rules_snapshot() -> dict[str, Any]:
    """Machine-readable identity and gate policy snapshot for artifacts."""
    return {
        "ruleset_version": SOURCE_IDENTITY_RULESET_VERSION,
        "official_dominance_targets": dict(OFFICIAL_DOMINANCE_TARGETS),
        "secondary_provider_primary_caps": dict(SECONDARY_PROVIDER_PRIMARY_CAPS),
        "approved_external_promotion_audit_statuses": sorted(
            _APPROVED_PROMOTION_AUDIT_STATUSES
        ),
        "source_officialness_values": [
            "official_government",
            "official_civic_partner",
            "official_regional_body",
            "external_advocacy",
            "external_news",
            "external_vendor",
            "ambiguous_portal",
            "external_other",
            "unknown",
        ],
        "source_of_truth_roles": [
            "primary_official",
            "primary_external_promoted",
            "secondary_context",
            "discovery_only",
        ],
    }


def classify_source_candidate(
    *,
    candidate: Mapping[str, Any],
    jurisdiction: str | None = None,
    policy_families: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Classify one source candidate for officialness and primary-evidence policy."""
    url = str(candidate.get("artifact_url") or candidate.get("url") or "").strip()
    title = str(candidate.get("title") or "").strip()
    snippet = str(candidate.get("snippet") or candidate.get("excerpt") or "").strip()
    provider = str(candidate.get("provider") or "").strip().lower()
    source_lane = str(candidate.get("source_lane") or "").strip().lower()
    policy_families_list = [
        str(item).strip().lower()
        for item in (policy_families or candidate.get("policy_families") or [])
        if str(item).strip()
    ]
    if not policy_families_list:
        raw_policy_family = str(candidate.get("policy_family") or "").strip().lower()
        if raw_policy_family:
            policy_families_list = [raw_policy_family]

    host = (urlsplit(url).hostname or "").lower()
    host_classification = classify_host(url) if url else "unknown"
    source_officialness = _derive_source_officialness(
        host=host,
        title=title,
        snippet=snippet,
        host_classification=host_classification,
    )
    jurisdiction_match = _derive_jurisdiction_match(
        jurisdiction=jurisdiction or str(candidate.get("jurisdiction") or ""),
        host=host,
        url=url,
        title=title,
        snippet=snippet,
    )
    if source_officialness.startswith("official_") and jurisdiction_match == "mismatch":
        jurisdiction_text = str(jurisdiction or "").strip().lower()
        combined_context = f"{host} {url} {title} {snippet}".lower()
        if "county" in jurisdiction_text and "county" in combined_context:
            jurisdiction_match = "partial"
        elif "state" in jurisdiction_text and (
            "state" in combined_context or host.endswith(".ca.gov")
        ):
            jurisdiction_match = "partial"
    if (
        source_officialness == "official_regional_body"
        and jurisdiction_match == "mismatch"
    ):
        jurisdiction_match = "partial"
    policy_family_match = _derive_policy_family_match(
        policy_families=policy_families_list,
        title=title,
        snippet=snippet,
        url=url,
    )

    reason_codes: list[str] = [
        f"host_classification:{host_classification}",
        f"jurisdiction_match:{jurisdiction_match}",
        f"policy_family_match:{policy_family_match}",
    ]
    if provider:
        reason_codes.append(f"provider:{provider}")

    derived_via_secondary_search = provider in _SECONDARY_SEARCH_PROVIDERS
    if derived_via_secondary_search:
        reason_codes.append("secondary_provider:derived")
    if source_lane.startswith("structured_secondary"):
        reason_codes.append("secondary_lane:structured_secondary")

    external_context_allowed = source_officialness in {
        "external_advocacy",
        "external_news",
        "external_vendor",
        "ambiguous_portal",
        "external_other",
    }

    promotion_rule_id = str(
        candidate.get("source_identity_promotion_rule_id")
        or candidate.get("promotion_rule_id")
        or ""
    ).strip()
    promotion_reason = str(
        candidate.get("source_identity_promotion_reason")
        or candidate.get("promotion_reason")
        or ""
    ).strip()
    promotion_audit_status = str(
        candidate.get("source_identity_promotion_audit_status")
        or candidate.get("promotion_audit_status")
        or "pending"
    ).strip()

    primary_evidence_allowed = False
    source_of_truth_role = (
        "discovery_only"
        if (
            derived_via_secondary_search
            or source_lane.startswith("structured_secondary")
        )
        else "secondary_context"
    )

    if source_officialness.startswith("official_"):
        if jurisdiction_match == "mismatch":
            reason_codes.append("official_source_blocked_jurisdiction_mismatch")
        elif policy_family_match == "mismatch":
            reason_codes.append("official_source_blocked_policy_family_mismatch")
        else:
            primary_evidence_allowed = True
            source_of_truth_role = "primary_official"
            reason_codes.append("official_primary_allowed")
    elif external_context_allowed:
        reason_codes.append("external_context_only_default")
        if promotion_rule_id:
            reason_codes.append(f"external_promotion_rule:{promotion_rule_id}")
            if promotion_reason:
                reason_codes.append("external_promotion_reason_present")
            if promotion_audit_status.lower() in _APPROVED_PROMOTION_AUDIT_STATUSES:
                primary_evidence_allowed = True
                source_of_truth_role = "primary_external_promoted"
                reason_codes.append("external_promotion_audit_approved")
            else:
                reason_codes.append("external_promotion_audit_missing_or_pending")
        else:
            reason_codes.append("external_primary_blocked_default")
    else:
        reason_codes.append("unknown_source_officialness")

    if (
        provider in _SECONDARY_SEARCH_PROVIDERS
        and source_of_truth_role == "primary_official"
    ):
        reason_codes.append("secondary_provider_primary_candidate")

    classification_id = _hash_payload(
        {
            "url": url,
            "provider": provider,
            "source_lane": source_lane,
            "jurisdiction": jurisdiction,
            "policy_families": policy_families_list,
        }
    )

    return {
        "classification_id": classification_id,
        "ruleset_version": SOURCE_IDENTITY_RULESET_VERSION,
        "source_url": url,
        "source_host": host,
        "provider": provider or "unknown",
        "source_lane": source_lane or "unknown",
        "source_officialness": source_officialness,
        "source_of_truth_role": source_of_truth_role,
        "jurisdiction_match": jurisdiction_match,
        "policy_family_match": policy_family_match,
        "external_context_allowed": external_context_allowed,
        "primary_evidence_allowed": primary_evidence_allowed,
        "derived_via_secondary_search": derived_via_secondary_search,
        "promotion_rule_id": promotion_rule_id or None,
        "promotion_reason": promotion_reason or None,
        "promotion_audit_status": promotion_audit_status or "pending",
        "reason_codes": sorted(set(reason_codes)),
    }


def build_source_durability_profile(
    *,
    candidate: Mapping[str, Any],
    freshness_status: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build freshness/drift/durability primitives for one source candidate."""
    current = now if now is not None else datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)

    retrieved_at_raw = (
        candidate.get("retrieved_at")
        or candidate.get("last_retrieved_at")
        or candidate.get("created_at")
    )
    retrieved_at = _parse_datetime(retrieved_at_raw)
    source_date_fields = _extract_source_date_fields(candidate)

    cadence = _infer_update_cadence(candidate)
    cadence_days = _CADENCE_DAYS.get(cadence)

    last_successful_refresh = _parse_datetime(
        candidate.get("last_successful_refresh") or retrieved_at_raw
    )
    source_shape_fingerprint = _shape_fingerprint(candidate)
    source_shape_changed = _source_shape_changed(candidate)
    update_cadence_drift = _cadence_drift(
        cadence_days=cadence_days,
        last_successful_refresh=last_successful_refresh,
        now=current,
    )

    stale_for_policy_use = (
        freshness_status in {"stale_blocked", "empty_blocked"}
        or source_shape_changed
        or update_cadence_drift
    )
    if stale_for_policy_use:
        next_refresh_recommendation = "refresh_immediately"
    elif cadence_days is not None and last_successful_refresh is not None:
        next_refresh_recommendation = (
            last_successful_refresh + timedelta(days=cadence_days)
        ).isoformat()
    else:
        next_refresh_recommendation = "set_source_cadence_or_manual_review"

    return {
        "retrieved_at": retrieved_at.isoformat() if retrieved_at else None,
        "source_date_fields": source_date_fields,
        "cadence": cadence,
        "last_successful_refresh": (
            last_successful_refresh.isoformat() if last_successful_refresh else None
        ),
        "source_shape_fingerprint": source_shape_fingerprint,
        "source_shape_changed": source_shape_changed,
        "update_cadence_drift": update_cadence_drift,
        "stale_for_policy_use": stale_for_policy_use,
        "next_refresh_recommendation": next_refresh_recommendation,
    }


def build_external_source_promotion_entry(
    *,
    classification: Mapping[str, Any],
    package_id: str,
) -> dict[str, Any] | None:
    """Return promotion register entry for external sources promoted to primary."""
    source_officialness = str(classification.get("source_officialness") or "")
    if source_officialness.startswith("official_"):
        return None
    if not bool(classification.get("primary_evidence_allowed")):
        return None
    rule_id = str(classification.get("promotion_rule_id") or "").strip()
    if not rule_id:
        return {
            "package_id": package_id,
            "source_url": str(classification.get("source_url") or ""),
            "rule_id": None,
            "reason": "missing_promotion_rule_id_for_external_primary",
            "audit_status": "fail",
        }
    return {
        "package_id": package_id,
        "source_url": str(classification.get("source_url") or ""),
        "rule_id": rule_id,
        "reason": str(
            classification.get("promotion_reason")
            or "external_source_promoted_to_primary_by_rule"
        ),
        "audit_status": str(classification.get("promotion_audit_status") or "pending"),
    }


def compute_official_source_dominance(
    *,
    classifications: Sequence[Mapping[str, Any]],
    audited_classification_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Compute dominance and cap metrics for scorecards and gate enforcement."""
    normalized: list[dict[str, Any]] = [dict(item) for item in classifications]
    primary = [
        item
        for item in normalized
        if str(item.get("source_of_truth_role") or "").strip()
        in {"primary_official", "primary_external_promoted"}
    ]
    official_primary = [
        item
        for item in primary
        if str(item.get("source_of_truth_role") or "").strip() == "primary_official"
    ]
    secondary_provider_primary = [
        item for item in primary if bool(item.get("derived_via_secondary_search"))
    ]

    audited_rows: list[dict[str, Any]]
    if audited_classification_ids:
        audited_rows = [
            item
            for item in primary
            if str(item.get("classification_id") or "") in audited_classification_ids
        ]
    else:
        audited_rows = list(primary)

    audited_official = [
        item
        for item in audited_rows
        if str(item.get("source_of_truth_role") or "").strip() == "primary_official"
    ]
    audited_secondary_provider_primary = [
        item for item in audited_rows if bool(item.get("derived_via_secondary_search"))
    ]

    audited_official_percent = _pct(len(audited_official), len(audited_rows))
    corpus_official_percent = _pct(len(official_primary), len(primary))
    audited_secondary_provider_primary_percent = _pct(
        len(audited_secondary_provider_primary), len(audited_rows)
    )
    corpus_secondary_provider_primary_percent = _pct(
        len(secondary_provider_primary), len(primary)
    )

    failure_codes: list[str] = []
    if audited_official_percent < OFFICIAL_DOMINANCE_TARGETS["hard_fail_below_percent"]:
        failure_codes.append("official_dominance_audited_hard_fail")
    if corpus_official_percent < OFFICIAL_DOMINANCE_TARGETS["hard_fail_below_percent"]:
        failure_codes.append("official_dominance_corpus_hard_fail")
    if (
        audited_secondary_provider_primary_percent
        > SECONDARY_PROVIDER_PRIMARY_CAPS["audited_tavily_exa_max_percent"]
    ):
        failure_codes.append("secondary_provider_primary_cap_exceeded_audited")
    if (
        corpus_secondary_provider_primary_percent
        > SECONDARY_PROVIDER_PRIMARY_CAPS["corpus_tavily_exa_max_percent"]
    ):
        failure_codes.append("secondary_provider_primary_cap_exceeded_corpus")

    hard_fail = any(code.endswith("hard_fail") for code in failure_codes)
    target_met = (
        audited_official_percent
        >= OFFICIAL_DOMINANCE_TARGETS["audited_p0_p1_target_percent"]
        and corpus_official_percent
        >= OFFICIAL_DOMINANCE_TARGETS["corpus_target_percent"]
    )
    caps_met = not any("cap_exceeded" in code for code in failure_codes)

    if hard_fail or not caps_met:
        status = "fail"
    elif target_met:
        status = "pass"
    else:
        status = "not_proven"

    return {
        "status": status,
        "failure_codes": failure_codes,
        "audited_primary_count": len(audited_rows),
        "audited_official_primary_count": len(audited_official),
        "audited_official_primary_percent": audited_official_percent,
        "corpus_primary_count": len(primary),
        "corpus_official_primary_count": len(official_primary),
        "corpus_official_primary_percent": corpus_official_percent,
        "audited_tavily_exa_primary_percent": audited_secondary_provider_primary_percent,
        "corpus_tavily_exa_primary_percent": corpus_secondary_provider_primary_percent,
        **OFFICIAL_DOMINANCE_TARGETS,
        **SECONDARY_PROVIDER_PRIMARY_CAPS,
    }


def _derive_source_officialness(
    *,
    host: str,
    title: str,
    snippet: str,
    host_classification: str,
) -> str:
    host_text = host.lower()
    combined = f"{title} {snippet} {host_text}".strip().lower()
    if host_classification == "official_government":
        if (
            "regional" in combined
            or "air quality" in combined
            or "metropolitan" in combined
        ):
            return "official_regional_body"
        return "official_government"
    if host_classification == "official_civic_partner":
        return "official_civic_partner"
    if host.endswith(".org") and (
        "gov" in host
        or "county" in host
        or "city" in host
        or host.startswith("cityof")
        or host.startswith("countyof")
    ):
        return "official_government"
    if any(token in combined for token in _EXTERNAL_ADVOCACY_HINTS):
        return "external_advocacy"
    if any(token in combined for token in _EXTERNAL_NEWS_HINTS):
        return "external_news"
    if any(token in combined for token in _EXTERNAL_VENDOR_HINTS):
        return "external_vendor"
    if any(token in combined for token in _AMBIGUOUS_PORTAL_HINTS):
        return "ambiguous_portal"
    if combined:
        return "external_other"
    return "unknown"


def _derive_jurisdiction_match(
    *,
    jurisdiction: str,
    host: str,
    url: str,
    title: str,
    snippet: str,
) -> str:
    normalized_jurisdiction = str(jurisdiction or "").strip().lower()
    if not normalized_jurisdiction:
        return "unknown"
    raw_tokens = re.split(r"[^a-z0-9]+", normalized_jurisdiction)
    tokens = [
        token
        for token in raw_tokens
        if token and token not in {"city", "county", "state", "us", "usa"}
    ]
    if not tokens:
        return "unknown"

    combined = f"{host} {url} {title} {snippet}".lower()
    combined_compact = re.sub(r"[^a-z0-9]", "", combined)
    direct_slug = re.sub(r"[^a-z0-9]", "", normalized_jurisdiction)
    if direct_slug and direct_slug in combined_compact:
        return "exact"

    matched = [token for token in tokens if token in combined]
    if len(matched) >= max(2, len(tokens)):
        return "exact"
    if matched:
        return "partial"
    return "mismatch"


def _derive_policy_family_match(
    *,
    policy_families: Sequence[str],
    title: str,
    snippet: str,
    url: str,
) -> str:
    if not policy_families:
        return "unknown"
    combined = f"{title} {snippet} {url}".lower()
    matches = 0
    partial = False
    saw_matchable_family = False
    for family in policy_families:
        keywords = _POLICY_FAMILY_KEYWORDS.get(family, ())
        if not keywords:
            continue
        saw_matchable_family = True
        if any(keyword in combined for keyword in keywords):
            matches += 1
            continue
        if any(word in combined for word in family.split("_")):
            partial = True
    if matches > 0:
        return "exact"
    if partial:
        return "partial"
    if not saw_matchable_family or set(policy_families) == {"general_governance"}:
        return "unknown"
    if not title and not snippet:
        return "unknown"
    return "mismatch"


def _extract_source_date_fields(candidate: Mapping[str, Any]) -> dict[str, str | None]:
    lineage_metadata = candidate.get("lineage_metadata")
    lineage = lineage_metadata if isinstance(lineage_metadata, Mapping) else {}
    keys = (
        "published_date",
        "meeting_date",
        "event_date",
        "adoption_date",
        "effective_date",
    )
    output: dict[str, str | None] = {}
    for key in keys:
        value = candidate.get(key)
        if value is None:
            value = lineage.get(key)
        text = str(value or "").strip()
        output[key] = text or None
    return output


def _infer_update_cadence(candidate: Mapping[str, Any]) -> str:
    explicit = (
        str(
            candidate.get("source_update_cadence")
            or candidate.get("update_cadence")
            or candidate.get("cadence")
            or ""
        )
        .strip()
        .lower()
    )
    if explicit in _CADENCE_DAYS:
        return explicit

    source_family = str(candidate.get("source_family") or "").strip().lower()
    provider = str(candidate.get("provider") or "").strip().lower()
    artifact_type = str(candidate.get("artifact_type") or "").strip().lower()
    if "legistar" in source_family or "legistar" in provider:
        return "weekly"
    if "granicus" in source_family or "granicus" in provider:
        return "weekly"
    if "ckan" in source_family or "open_data" in source_family:
        return "monthly"
    if "minutes" in artifact_type or "agenda" in artifact_type:
        return "weekly"
    if "ordinance" in artifact_type or "resolution" in artifact_type:
        return "quarterly"
    return "unknown"


def _source_shape_changed(candidate: Mapping[str, Any]) -> bool:
    reconciliation_status = (
        str(candidate.get("reconciliation_status") or "").strip().lower()
    )
    if (
        "source_shape_changed" in reconciliation_status
        or "shape_changed" in reconciliation_status
    ):
        return True
    alerts = [
        str(item).strip().lower()
        for item in (candidate.get("alerts") or [])
        if str(item).strip()
    ]
    return any(
        "shape_drift" in alert or "source_shape_changed" in alert for alert in alerts
    )


def _shape_fingerprint(candidate: Mapping[str, Any]) -> str:
    facts = candidate.get("structured_policy_facts")
    structured_fields: list[str] = []
    if isinstance(facts, list):
        for item in facts:
            if not isinstance(item, Mapping):
                continue
            field = str(item.get("field") or "").strip().lower()
            if field:
                structured_fields.append(field)
    payload = {
        "source_family": str(candidate.get("source_family") or "").strip().lower(),
        "artifact_type": str(candidate.get("artifact_type") or "").strip().lower(),
        "source_lane": str(candidate.get("source_lane") or "").strip().lower(),
        "fact_fields": sorted(set(structured_fields)),
    }
    return _hash_payload(payload)


def _cadence_drift(
    *,
    cadence_days: int | None,
    last_successful_refresh: datetime | None,
    now: datetime,
) -> bool:
    if cadence_days is None or last_successful_refresh is None:
        return False
    if last_successful_refresh.tzinfo is None:
        last_successful_refresh = last_successful_refresh.replace(tzinfo=UTC)
    allowed = timedelta(days=max(1, cadence_days * 2))
    return now - last_successful_refresh > allowed


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _hash_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((float(numerator) / float(denominator)) * 100.0, 2)
