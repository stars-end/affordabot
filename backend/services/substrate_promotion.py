"""Rules-first substrate promotion policy helpers.

This module keeps promotion semantics machine-checkable for new captures while
remaining safe for legacy rows that do not carry staged ingestion truth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import urlsplit


PROMOTION_POLICY_VERSION = "2026-04-01.v1"

CAPTURED_CANDIDATE = "captured_candidate"
DURABLE_RAW = "durable_raw"
PROMOTED_SUBSTRATE = "promoted_substrate"

OFFICIAL_TRUST_TIERS = {"primary_government", "official_partner"}
OFFICIAL_HOST_CLASSES = {"official_government", "official_civic_partner"}

SUBSTANTIVE_DOCUMENT_TYPES = {
    "agenda",
    "minutes",
    "meeting_detail",
    "staff_report",
    "fiscal_note",
    "attachment",
    "municipal_code",
    "legislation",
}
INDEX_OR_SHELL_DOCUMENT_TYPES = {
    "meeting_calendar",
    "calendar",
    "index",
    "homepage",
}
SHELL_HINTS = {
    "municode library",
    "calendar",
    "index",
    "home",
    "homepage",
}


@dataclass(frozen=True)
class PromotionDecision:
    promotion_state: Optional[str]
    reason_category: str
    confidence: str
    method: str
    promotion_error: Optional[str] = None


class GLM46VPromotionBoundary:
    """Mockable boundary for optional ambiguous-case LLM classification.

    This class intentionally isolates the provider call behind an injectable
    transport. In production, pass a transport that calls Z.ai with model
    `glm-4.6v`. In tests, pass a lightweight mock transport.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str],
        model: str = "glm-4.6v",
        enabled: bool = False,
        transport: Optional[Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.enabled = enabled
        self.transport = transport

    async def classify_ambiguous(self, metadata: dict[str, Any]) -> PromotionDecision:
        if not self.enabled:
            raise RuntimeError("LLM promotion disabled")
        if not self.api_key:
            raise RuntimeError("ZAI_API_KEY missing")
        if self.transport is None:
            raise RuntimeError("GLM transport not configured")

        payload = {
            "model": self.model,
            "task": "substrate_promotion_ambiguous_resolution",
            "metadata": metadata,
            "schema": {
                "promotion_decision": "promote|keep_durable_raw",
                "reason_category": (
                    "substantive_official_document|index_or_shell_page|"
                    "insufficient_substance|unclear"
                ),
                "confidence": "high|medium|low",
            },
        }
        result = await self.transport(payload)
        decision = (result.get("promotion_decision") or "").strip().lower()
        if decision == "promote":
            state = PROMOTED_SUBSTRATE
        elif decision == "keep_durable_raw":
            state = DURABLE_RAW
        else:
            raise RuntimeError("LLM boundary returned invalid promotion_decision")

        reason = (result.get("reason_category") or "unclear").strip().lower()
        confidence = (result.get("confidence") or "low").strip().lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
        return PromotionDecision(
            promotion_state=state,
            reason_category=reason,
            confidence=confidence,
            method="llm",
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_json_blob(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def hostname_from_url(url: str) -> str:
    if not url:
        return ""
    return (urlsplit(url).hostname or "").lower()


def classify_host(url: str) -> str:
    host = hostname_from_url(url)
    if not host:
        return "unknown"
    if host.endswith(".gov") or host.endswith(".gov.us"):
        return "official_government"
    if host.endswith(".ca.gov"):
        return "official_government"
    if host.endswith("legistar.com") or host.endswith("granicus.com") or host.endswith("municode.com"):
        return "official_civic_partner"
    return "non_official"


def is_official_trust_tier(trust_tier: str) -> bool:
    return (trust_tier or "").strip().lower() in OFFICIAL_TRUST_TIERS


def is_official_host_classification(host_classification: str) -> bool:
    return (host_classification or "").strip().lower() in OFFICIAL_HOST_CLASSES


def classify_trust(
    *,
    canonical_url: str,
    trust_tier: Optional[str],
) -> tuple[str, str]:
    host_classification = classify_host(canonical_url)
    normalized_tier = (trust_tier or "").strip().lower()
    if normalized_tier:
        return normalized_tier, host_classification
    if is_official_host_classification(host_classification):
        return "official_partner", host_classification
    return "non_official", host_classification


def is_shell_or_index(
    *,
    document_type: str,
    title: str,
    preview_text: str,
) -> bool:
    normalized_type = (document_type or "").strip().lower()
    if normalized_type in INDEX_OR_SHELL_DOCUMENT_TYPES:
        return True
    combined = f"{title or ''} {preview_text or ''}".strip().lower()
    if not combined:
        return False
    return any(hint in combined for hint in SHELL_HINTS)


def has_substance(
    *,
    content_class: str,
    preview_text: str,
    ingestion_truth: dict[str, Any],
) -> bool:
    if content_class == "pdf_binary":
        return ingestion_truth.get("retrievable") is True
    if ingestion_truth.get("retrievable") is True:
        return True
    return len((preview_text or "").strip()) >= 120


def seed_capture_promotion_metadata(
    *,
    metadata: dict[str, Any],
    canonical_url: str,
    trust_tier: Optional[str],
) -> dict[str, Any]:
    updated = dict(metadata)
    normalized_tier, host_class = classify_trust(
        canonical_url=canonical_url,
        trust_tier=trust_tier,
    )
    updated["trust_tier"] = normalized_tier
    updated["trust_host_classification"] = host_class
    updated["promotion_policy_version"] = PROMOTION_POLICY_VERSION
    updated.setdefault("promotion_error", None)
    updated["promotion_last_evaluated_at"] = now_iso()

    official = is_official_trust_tier(normalized_tier) or is_official_host_classification(host_class)
    if official:
        updated["promotion_state"] = DURABLE_RAW
        updated["promotion_method"] = "rules"
        updated["promotion_reason_category"] = "captured_preserved_official"
        updated["promotion_confidence"] = "high"
    else:
        updated["promotion_state"] = CAPTURED_CANDIDATE
        updated["promotion_method"] = "rules"
        updated["promotion_reason_category"] = "captured_untrusted_needs_review"
        updated["promotion_confidence"] = "low"
    return updated


def evaluate_rules(metadata: dict[str, Any]) -> PromotionDecision:
    canonical_url = metadata.get("canonical_url") or metadata.get("url") or ""
    trust_tier = (metadata.get("trust_tier") or "").strip().lower()
    host_class = metadata.get("trust_host_classification") or classify_host(canonical_url)
    state = metadata.get("promotion_state")
    ingestion_truth = parse_json_blob(metadata.get("ingestion_truth"))

    if not ingestion_truth and state is None:
        return PromotionDecision(
            promotion_state=None,
            reason_category="legacy_unknown",
            confidence="low",
            method="rules",
        )

    official = is_official_trust_tier(trust_tier) or is_official_host_classification(host_class)
    if state is None:
        state = DURABLE_RAW if official else CAPTURED_CANDIDATE
    if state == CAPTURED_CANDIDATE and official:
        state = DURABLE_RAW

    if not official:
        return PromotionDecision(
            promotion_state=state,
            reason_category="untrusted_source",
            confidence="low",
            method="rules",
        )

    document_type = (metadata.get("document_type") or "").strip().lower()
    title = metadata.get("title") or metadata.get("page_title") or ""
    preview_text = metadata.get("preview_text") or ""
    if is_shell_or_index(document_type=document_type, title=title, preview_text=preview_text):
        return PromotionDecision(
            promotion_state=DURABLE_RAW,
            reason_category="index_or_shell_page",
            confidence="high",
            method="rules",
        )

    content_class = (metadata.get("content_class") or "").strip().lower()
    substantive = has_substance(
        content_class=content_class,
        preview_text=preview_text,
        ingestion_truth=ingestion_truth,
    )
    if document_type in SUBSTANTIVE_DOCUMENT_TYPES and substantive:
        confidence = "high" if ingestion_truth.get("retrievable") is True else "medium"
        return PromotionDecision(
            promotion_state=PROMOTED_SUBSTRATE,
            reason_category="substantive_official_document",
            confidence=confidence,
            method="rules",
        )

    return PromotionDecision(
        promotion_state=DURABLE_RAW,
        reason_category="unclear",
        confidence="low",
        method="rules",
    )


async def evaluate_with_fallback(
    *,
    metadata: dict[str, Any],
    llm_boundary: Optional[GLM46VPromotionBoundary] = None,
) -> PromotionDecision:
    rules_decision = evaluate_rules(metadata)
    if rules_decision.reason_category != "unclear":
        return rules_decision

    if llm_boundary is None:
        return rules_decision

    try:
        return await llm_boundary.classify_ambiguous(metadata)
    except Exception as exc:  # noqa: BLE001 - persist operational failure for QA surfaces
        return PromotionDecision(
            promotion_state=rules_decision.promotion_state,
            reason_category=rules_decision.reason_category,
            confidence=rules_decision.confidence,
            method="llm_fallback_rules",
            promotion_error=str(exc),
        )


def apply_promotion_decision(
    *,
    metadata: dict[str, Any],
    decision: PromotionDecision,
    canonical_url: Optional[str] = None,
) -> dict[str, Any]:
    updated = dict(metadata)
    effective_url = canonical_url or updated.get("canonical_url") or updated.get("url") or ""
    host_class = updated.get("trust_host_classification") or classify_host(effective_url)
    updated["trust_host_classification"] = host_class
    updated["promotion_policy_version"] = PROMOTION_POLICY_VERSION
    updated["promotion_state"] = decision.promotion_state
    updated["promotion_method"] = decision.method
    updated["promotion_reason_category"] = decision.reason_category
    updated["promotion_confidence"] = decision.confidence
    updated["promotion_last_evaluated_at"] = now_iso()
    updated["promotion_error"] = decision.promotion_error
    return updated
