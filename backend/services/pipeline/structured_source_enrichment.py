"""Structured-source enrichment for PolicyEvidencePackage materialization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from io import BytesIO
import os
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import httpx

from services.pipeline.non_fee_extraction_templates import extract_non_fee_policy_facts
from services.pipeline.structured_source_catalog import san_jose_structured_source_catalog


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _is_san_jose_jurisdiction(value: str) -> bool:
    normalized = value.strip().lower().replace(" ", "_")
    return "san_jose" in normalized or "san-jose" in normalized


def _is_california_state_jurisdiction(value: str) -> bool:
    normalized = value.strip().lower().replace(" ", "_")
    return normalized in {"california", "california_state", "ca_state"} or "california" in normalized


def _policy_match_key_for_url(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if "legistar.com" in raw:
        for token in ("guid=", "id=", "key=", "legid="):
            if token in raw:
                return f"legistar::{token.rstrip('=')}::{raw.split(token, 1)[1].split('&', 1)[0]}"
        return f"legistar::{raw}"
    return raw


_ECONOMIC_DATASET_TOKENS = {
    "housing",
    "rent",
    "permit",
    "development",
    "construction",
    "planning",
    "zoning",
    "affordable",
    "income",
    "wage",
    "employment",
    "tax",
    "fee",
    "budget",
    "property",
    "parcel",
    "cost",
}

_MATTER_CONTEXT_STOPWORDS = {
    "san",
    "jose",
    "city",
    "council",
    "policy",
    "priority",
    "agenda",
    "minutes",
    "meeting",
    "item",
    "document",
}

_MONTH_NUMBER_BY_NAME = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}

_HIGH_VALUE_ATTACHMENT_FAMILIES = {
    "ordinance",
    "resolution",
    "memorandum",
    "staff_report",
    "fee_study",
    "nexus_study",
    "feasibility_study",
    "fee_schedule",
}

_IDENTITY_LINKED_ATTACHMENT_FAMILIES = {
    "ordinance",
    "resolution",
    "memorandum",
    "staff_report",
    "fee_study",
    "nexus_study",
    "feasibility_study",
    "fee_schedule",
}

_BINARY_CONTENT_TYPE_SIGNALS = (
    "application/pdf",
    "application/octet-stream",
    "application/msword",
    "application/vnd.",
    "application/vnd-",
    "application/zip",
    "application/x-zip",
    "application/x-download",
    "image/",
    "audio/",
    "video/",
)


@dataclass(frozen=True)
class StructuredEnrichmentResult:
    status: str
    candidates: list[dict[str, Any]]
    alerts: list[str]
    source_catalog: list[dict[str, Any]]


class StructuredSourceEnricher:
    """Runtime structured-source collector for jurisdiction-aware source families."""

    def __init__(
        self, *, timeout_seconds: float = 4.0, tavily_api_key: str | None = None
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.tavily_api_key = (tavily_api_key or os.getenv("TAVILY_API_KEY") or "").strip()

    async def enrich(
        self,
        *,
        jurisdiction: str,
        source_family: str,
        search_query: str,
        selected_url: str,
        selected_candidate_context: str = "",
    ) -> StructuredEnrichmentResult:
        catalog = san_jose_structured_source_catalog()
        candidates: list[dict[str, Any]] = []
        alerts: list[str] = []
        supported_jurisdiction = _is_san_jose_jurisdiction(jurisdiction) or _is_california_state_jurisdiction(
            jurisdiction
        )
        if supported_jurisdiction:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                if _is_san_jose_jurisdiction(jurisdiction):
                    legistar_matter_candidate = await self._fetch_legistar_matter_metadata(
                        client=client,
                        selected_url=selected_url,
                        search_query=search_query,
                        selected_candidate_context=selected_candidate_context,
                    )
                    if legistar_matter_candidate:
                        candidates.append(legistar_matter_candidate)
                    else:
                        legistar_event_candidate = await self._fetch_legistar_event_metadata(client=client)
                        if legistar_event_candidate:
                            candidates.append(legistar_event_candidate)
                        else:
                            alerts.append("structured_enrichment_legistar_unavailable")

                    ckan_candidate = await self._fetch_san_jose_ckan_metadata(
                        client=client,
                        search_query=search_query,
                        selected_url=selected_url,
                    )
                    if ckan_candidate:
                        candidates.append(ckan_candidate)
                    else:
                        alerts.append("structured_enrichment_ckan_unavailable")

                    if self._should_probe_tavily_secondary(
                        source_family=source_family,
                        search_query=search_query,
                        selected_url=selected_url,
                    ):
                        tavily_candidate = await self._fetch_tavily_secondary_fee_metadata(
                            client=client,
                            source_family=source_family,
                            search_query=search_query,
                            selected_url=selected_url,
                        )
                        if tavily_candidate:
                            candidates.append(tavily_candidate)
                        else:
                            alerts.append("structured_enrichment_tavily_secondary_unavailable")
                else:
                    california_candidate = await self._fetch_california_ckan_metadata(
                        client=client,
                        jurisdiction=jurisdiction,
                        search_query=search_query,
                        selected_url=selected_url,
                        selected_candidate_context=selected_candidate_context,
                    )
                    if california_candidate:
                        candidates.append(california_candidate)
                    else:
                        alerts.append("structured_enrichment_california_ckan_unavailable")
        else:
            alerts.append("structured_enrichment_skipped_unsupported_jurisdiction")

        status = "integrated" if candidates else ("unavailable" if supported_jurisdiction else "not_applicable")
        if not candidates and selected_url and supported_jurisdiction:
            alerts.append("structured_enrichment_no_candidates_for_selected_url_context")
        _ = source_family  # reserved for runtime route selection
        source_catalog = self._annotate_source_catalog(
            catalog=catalog,
            candidates=candidates,
            alerts=alerts,
        )

        return StructuredEnrichmentResult(
            status=status,
            candidates=candidates,
            alerts=list(dict.fromkeys(alerts)),
            source_catalog=source_catalog,
        )

    @staticmethod
    def _annotate_source_catalog(
        *,
        catalog: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        alerts: list[str],
    ) -> list[dict[str, Any]]:
        live_families = {
            str(candidate.get("source_family") or "").strip()
            for candidate in candidates
            if isinstance(candidate, dict)
        }
        unavailable_by_alert = {
            "san_jose_open_data_ckan": "structured_enrichment_ckan_unavailable",
            "legistar_web_api": "structured_enrichment_legistar_unavailable",
            "california_open_data_ckan": "structured_enrichment_california_ckan_unavailable",
        }
        alert_set = set(alerts)
        annotated: list[dict[str, Any]] = []
        for entry in catalog:
            item = dict(entry)
            family = str(item.get("source_family") or "").strip()
            live_proven = family in live_families
            unavailable_alert = unavailable_by_alert.get(family)
            if live_proven:
                item["runtime_status"] = "integrated"
                item["live_proven"] = True
            elif unavailable_alert and unavailable_alert in alert_set:
                item["runtime_status"] = "cataloged_unavailable"
                item["live_proven"] = False
            else:
                item["runtime_status"] = item.get("runtime_status") or "cataloged"
                item["live_proven"] = False
            if str(item.get("lane_classification") or "").strip() == "secondary_search_derived":
                item["runtime_status"] = "cataloged"
                item["live_proven"] = False
            annotated.append(item)
        return annotated

    def _should_probe_tavily_secondary(
        self,
        *,
        source_family: str,
        search_query: str,
        selected_url: str,
    ) -> bool:
        if not self.tavily_api_key:
            return False
        source_family_key = str(source_family or "").strip().lower()
        if source_family_key not in {"policy_documents", "meeting_minutes", "ordinance_text"}:
            return False
        combined = f"{search_query} {selected_url}".lower()
        return any(
            token in combined
            for token in (
                "fee",
                "fees",
                "rate",
                "rates",
                "impact fee",
                "linkage",
                "nexus",
                "per square foot",
                "sq.ft",
                "sq ft",
                "cost",
            )
        )

    @staticmethod
    def _is_provenance_safe_tavily_url(url: str) -> bool:
        parsed = urlparse(str(url or "").strip())
        host = parsed.netloc.lower()
        if not host:
            return False
        if host.endswith(".gov") and ("sanjose" in host or "sccgov" in host):
            return True
        if host.endswith("sanjose.legistar.com") or host.endswith("sanjoseca.legistar.com"):
            return True
        return False

    @staticmethod
    def _extract_tavily_fee_facts(
        *,
        snippet: str,
        source_url: str,
        source_title: str,
        provider_rank: int,
    ) -> list[dict[str, Any]]:
        text = str(snippet or "").strip()
        normalized = text.lower()
        if not text:
            return []
        if "commercial linkage fee" not in normalized and "impact fee" not in normalized:
            return []
        if (
            "per square foot" not in normalized
            and "per net square foot" not in normalized
            and "sq.ft" not in normalized
            and "sq ft" not in normalized
        ):
            return []

        values = re.findall(r"\$([0-9]+(?:\.[0-9]+)?)", text)
        if not values:
            return []

        seen: set[tuple[str, float]] = set()
        facts: list[dict[str, Any]] = []
        for raw in values:
            amount = float(raw)
            key = (source_url, amount)
            if key in seen:
                continue
            seen.add(key)
            facts.append(
                {
                    "field": "commercial_linkage_fee_rate_usd_per_sqft",
                    "value": amount,
                    "unit": "usd_per_square_foot",
                    "source_url": source_url,
                    "source_excerpt": text[:600],
                    "source_title": str(source_title or "").strip(),
                    "provenance_lane": "structured_secondary_source",
                    "provider_rank": float(provider_rank),
                }
            )
        return facts

    async def _fetch_tavily_secondary_fee_metadata(
        self,
        *,
        client: httpx.AsyncClient,
        source_family: str,
        search_query: str,
        selected_url: str,
    ) -> dict[str, Any] | None:
        if not self.tavily_api_key:
            return None

        endpoint = "https://api.tavily.com/search"
        query_text = (
            search_query.strip()
            or "San Jose commercial linkage fee affordable housing impact fee per square foot rates"
        )
        payload = {
            "api_key": self.tavily_api_key,
            "query": query_text,
            "search_depth": "basic",
            "max_results": 5,
            "include_answer": False,
            "include_images": False,
        }
        try:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            raw_payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None

        if not isinstance(raw_payload, dict):
            return None
        results = raw_payload.get("results")
        if not isinstance(results, list) or not results:
            return None

        facts: list[dict[str, Any]] = []
        linked_refs: list[str] = []
        safe_results = 0
        for idx, row in enumerate(results[:5], start=1):
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "").strip()
            if not self._is_provenance_safe_tavily_url(url):
                continue
            safe_results += 1
            content = str(row.get("content") or "").strip()
            title = str(row.get("title") or "").strip()
            extracted = self._extract_tavily_fee_facts(
                snippet=content,
                source_url=url,
                source_title=title,
                provider_rank=idx,
            )
            if extracted:
                facts.extend(extracted)
                linked_refs.append(url)

        if not facts:
            return None

        primary_url = linked_refs[0] if linked_refs else str(selected_url or "").strip() or endpoint
        return {
            "source_lane": "structured_secondary_source",
            "provider": "tavily_search",
            "source_family": "tavily_secondary_search",
            "access_method": "tavily_search_api",
            "jurisdiction": "san_jose_ca",
            "artifact_url": primary_url,
            "artifact_type": "secondary_search_rate_snippet",
            "source_tier": "tier_c",
            "retrieved_at": _utc_now_iso(),
            "query_text": query_text,
            "excerpt": (
                "Secondary structured Tavily snippet extraction for missing economic fee/rate "
                f"evidence; extracted_facts={len(facts)}, provenance_safe_results={safe_results}."
            ),
            "structured_policy_facts": facts,
            "diagnostic_facts": [
                {"field": "tavily_result_count_scanned", "value": float(len(results[:5])), "unit": "count"},
                {"field": "tavily_result_count_provenance_safe", "value": float(safe_results), "unit": "count"},
                {"field": "tavily_fee_fact_count", "value": float(len(facts)), "unit": "count"},
            ],
            "alerts": [
                "structured_secondary_source_tavily",
                "secondary_search_complementary_lane",
            ],
            "provider_run_id": str(raw_payload.get("query_id") or raw_payload.get("request_id") or "unknown"),
            "linked_artifact_refs": list(dict.fromkeys(linked_refs)),
            "reader_artifact_refs": [],
            "candidate_status": "secondary_search_complement",
            "secondary_search": True,
            "secondary_search_scope": "bounded_max_results_5",
            "secondary_search_parent_source_family": str(source_family or "").strip() or "unknown",
            "true_structured": False,
            "policy_match_key": _policy_match_key_for_url(primary_url),
            "policy_match_confidence": 0.25,
            "reconciliation_status": "secondary_search_derived_not_authoritative",
        }

    @staticmethod
    def _extract_legistar_matter_id(*, selected_url: str) -> int | None:
        raw = str(selected_url or "").strip()
        if not raw:
            return None
        parsed = urlparse(raw)
        query = parse_qs(parsed.query)
        candidate_ids: list[str] = []
        for key in ("ID", "Id", "id"):
            if key in query and query[key]:
                candidate_ids.extend(query[key])
        for value in candidate_ids:
            text = str(value).strip()
            nested_match = re.search(r"(?:matterid|key)=(\d+)", unquote(text), flags=re.IGNORECASE)
            if nested_match:
                return int(nested_match.group(1))
            path = parsed.path.lower()
            if text.isdigit() and any(
                signal in path
                for signal in ("gateway.aspx", "legislationdetail.aspx", "matter.aspx")
            ):
                return int(text)
        for pattern in (r"/Matters/(\d+)", r"\bMatterId=(\d+)"):
            match = re.search(pattern, raw, flags=re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _classify_legistar_attachment_family(
        *,
        attachment_name: str,
        attachment_url: str,
    ) -> str:
        combined = f"{attachment_name} {attachment_url}".strip().lower()
        if not combined:
            return "unknown"
        if "nexus" in combined:
            return "nexus_study"
        if "feasibility" in combined and "study" in combined:
            return "feasibility_study"
        if "fee schedule" in combined:
            return "fee_schedule"
        if (
            "fee study" in combined
            or ("impact fee" in combined and "study" in combined)
            or "rate study" in combined
        ):
            return "fee_study"
        if (
            "staff report" in combined
            or "staff memo" in combined
            or "department report" in combined
        ):
            return "staff_report"
        if "memorandum" in combined or re.search(r"\bmemo\b", combined):
            return "memorandum"
        if "ordinance" in combined:
            return "ordinance"
        if "resolution" in combined:
            return "resolution"
        if "agenda" in combined or "minutes" in combined:
            return "agenda/minutes"
        if "exhibit" in combined or re.search(r"\bexh(?:ibit)?\b", combined):
            return "exhibit"
        return "unknown"

    @staticmethod
    def _is_economic_dataset(
        *,
        dataset: dict[str, Any],
        search_query: str,
        selected_url: str,
    ) -> bool:
        dataset_parts = [
            str(dataset.get("title") or ""),
            str(dataset.get("name") or ""),
            str(dataset.get("notes") or ""),
        ]
        tags = dataset.get("tags")
        if isinstance(tags, list):
            dataset_parts.extend(str(tag.get("name") or "") for tag in tags if isinstance(tag, dict))
        dataset_text = " ".join(dataset_parts).lower()

        economic_match = any(token in dataset_text for token in _ECONOMIC_DATASET_TOKENS)
        query_terms = {
            token
            for token in re.findall(r"[a-z0-9]+", f"{search_query} {selected_url}".lower())
            if len(token) >= 4
        }
        query_match = any(token in dataset_text for token in query_terms) if query_terms else False
        return economic_match or query_match

    @staticmethod
    def _resource_urls(dataset: dict[str, Any]) -> list[str]:
        resources = dataset.get("resources")
        if not isinstance(resources, list):
            return []
        urls: list[str] = []
        for item in resources:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                urls.append(url)
        return urls

    @staticmethod
    def _non_fee_template_metadata(
        facts: list[dict[str, Any]],
    ) -> tuple[list[str], list[str], str, str | None]:
        policy_families = sorted(
            {
                str(fact.get("policy_family") or "").strip()
                for fact in facts
                if str(fact.get("policy_family") or "").strip()
            }
        )
        evidence_uses = sorted(
            {
                str(fact.get("evidence_use") or "").strip()
                for fact in facts
                if str(fact.get("evidence_use") or "").strip()
            }
        )
        relevance_values = [
            str(fact.get("economic_relevance") or "").strip()
            for fact in facts
            if str(fact.get("economic_relevance") or "").strip()
        ]
        relevance_priority = {"direct": 0, "indirect": 1, "contextual": 2, "none": 3, "unknown": 4}
        economic_relevance = sorted(
            relevance_values,
            key=lambda value: relevance_priority.get(value, 99),
        )[0] if relevance_values else "unknown"
        moat_reason = next(
            (
                str(fact.get("moat_value_reason") or "").strip()
                for fact in facts
                if str(fact.get("moat_value_reason") or "").strip()
            ),
            None,
        )
        return policy_families, evidence_uses, economic_relevance, moat_reason

    @staticmethod
    def _is_high_value_attachment_ref(attachment_ref: dict[str, Any]) -> bool:
        source_family = str(attachment_ref.get("source_family") or "").strip().lower()
        if source_family in _HIGH_VALUE_ATTACHMENT_FAMILIES:
            return True
        title = str(attachment_ref.get("title") or "").strip().lower()
        return any(
            token in title
            for token in (
                "ordinance",
                "resolution",
                "memorandum",
                "memo",
                "staff report",
                "nexus",
                "fee study",
                "feasibility study",
                "fee schedule",
            )
        )

    @staticmethod
    def _normalize_attachment_url(*, raw_url: str, fallback_url: str) -> str:
        normalized = str(raw_url or "").strip()
        if not normalized:
            return ""
        if normalized.startswith(("http://", "https://")):
            return normalized
        if normalized.startswith("//"):
            return f"https:{normalized}"
        base = str(fallback_url or "").strip() or "https://sanjoseca.legistar.com/"
        return urljoin(base, normalized)

    @staticmethod
    def _is_verified_san_jose_legistar_context(context_url: str) -> bool:
        parsed = urlparse(str(context_url or "").strip())
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        if host.endswith("sanjose.legistar.com") or host.endswith("sanjoseca.legistar.com"):
            return True
        if host == "webapi.legistar.com" and path.startswith("/v1/sanjose/"):
            return True
        return False

    @staticmethod
    def _is_san_jose_granicus_pdf_attachment(url: str) -> bool:
        parsed = urlparse(str(url or "").strip())
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        if "legistar" not in host or not host.endswith("granicus.com"):
            return False
        if not path.endswith(".pdf"):
            return False
        return path.startswith("/sanjose/attachments/") or path.startswith("/sanjoseca/attachments/")

    @staticmethod
    def _is_official_attachment_url(
        url: str,
        *,
        verified_san_jose_legistar_context: bool = False,
    ) -> bool:
        host = urlparse(str(url or "").strip()).netloc.lower()
        if not host:
            return False
        if "legistar.com" in host and "sanjose" in host:
            return True
        if StructuredSourceEnricher._is_san_jose_granicus_pdf_attachment(url):
            return verified_san_jose_legistar_context
        if host.endswith("sanjoseca.gov"):
            return True
        return False

    @staticmethod
    def _is_pdf_attachment(*, url: str, content_type: str) -> bool:
        lowered_url = str(url or "").strip().lower()
        lowered_type = str(content_type or "").strip().lower()
        return lowered_url.endswith(".pdf") or "application/pdf" in lowered_type

    @staticmethod
    def _is_binary_content_type(content_type: str) -> bool:
        lowered = str(content_type or "").strip().lower()
        if not lowered:
            return False
        return any(signal in lowered for signal in _BINARY_CONTENT_TYPE_SIGNALS)

    @staticmethod
    def _looks_like_binary_payload(body: bytes) -> bool:
        if not body:
            return False
        sample = body[:8192]
        if b"\x00" in sample:
            return True
        printable = sum(
            1 for byte in sample if byte in {9, 10, 13} or 32 <= byte <= 126
        )
        return printable / len(sample) < 0.72

    @staticmethod
    def _classify_pdf_parse_error(exc: Exception, *, phase: str) -> str:
        if exc.__class__.__name__ == "PdfReadError":
            return "unreadable_pdf"
        phase_mapping = {
            "reader_init": "pdf_reader_init_failed",
            "page_iteration": "pdf_page_iteration_failed",
            "page_extract": "pdf_page_extract_failed",
        }
        return phase_mapping.get(phase, "pdf_parse_failed")

    @staticmethod
    def _extract_pdf_text(body: bytes) -> tuple[str | None, str | None]:
        if not body:
            return None, "empty_pdf_payload"
        try:
            from pypdf import PdfReader
        except Exception as exc:  # noqa: BLE001
            _ = exc
            return None, "pdf_dependency_unavailable"
        try:
            reader = PdfReader(BytesIO(body))
        except Exception as exc:  # noqa: BLE001
            return None, StructuredSourceEnricher._classify_pdf_parse_error(
                exc, phase="reader_init"
            )
        try:
            pages = list(reader.pages)
        except Exception as exc:  # noqa: BLE001
            return None, StructuredSourceEnricher._classify_pdf_parse_error(
                exc, phase="page_iteration"
            )
        page_text: list[str] = []
        for page in pages:
            try:
                extracted = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001
                return None, StructuredSourceEnricher._classify_pdf_parse_error(
                    exc, phase="page_extract"
                )
            if extracted.strip():
                page_text.append(extracted)
        return "\n".join(page_text).strip(), None

    @staticmethod
    def _attachment_failure_class(*, status: str, content_ingested: bool) -> str | None:
        if content_ingested:
            return None
        mapping = {
            "skipped_missing_url": "missing_attachment_url",
            "skipped_non_official_attachment": "non_official_attachment",
            "fetch_failed": "attachment_fetch_failed",
            "binary_pdf_unparsed": "binary_pdf_unparsed",
            "pdf_parse_failed": "attachment_pdf_parse_failed",
            "binary_unparsed": "binary_unparsed",
            "empty_text": "attachment_text_empty",
        }
        return mapping.get(status, "attachment_ingestion_failed")

    @staticmethod
    def _extract_attachment_excerpt(text: str) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            return ""
        economic_signal = re.search(r"\$\s*[0-9]+", cleaned)
        if economic_signal is None:
            economic_signal = re.search(
                r"(fee\s+per\s+sq\.?\s*ft|geographic\s+subarea\s+non-residential\s+use)",
                cleaned,
                re.IGNORECASE,
            )
        if economic_signal is None:
            return cleaned[:800]
        start = max(0, economic_signal.start() - 420)
        return cleaned[start : start + 1800].strip()

    @staticmethod
    def _extract_attachment_economic_rows(
        *,
        text: str,
        source_url: str,
        source_family: str,
        source_title: str | None,
        attachment_id: str | None,
        content_hash: str | None,
    ) -> list[dict[str, Any]]:
        lowered = text.lower()
        if not re.search(r"(fee|rate|commercial\s+linkage|\bclf\b)", lowered):
            return []
        if not re.search(r"(per\s+square\s+foot|per\s+sq\.?\s*ft|sq\.?\s*ft)", lowered):
            return []

        land_use_pattern = re.compile(
            r"(non-residential\s+use|downtown|rest\s+of\s+city|office|retail|hotel|"
            r"industrial|warehouse|residential\s+care)",
            re.IGNORECASE,
        )
        land_use_extractors = (
            ("residential_care", re.compile(r"\bresidential\s+care\b", re.IGNORECASE)),
            ("warehouse", re.compile(r"\bwarehouse\b", re.IGNORECASE)),
            ("industrial", re.compile(r"\bindustrial\b", re.IGNORECASE)),
            ("office", re.compile(r"\boffice\b", re.IGNORECASE)),
            ("retail", re.compile(r"\bretail\b", re.IGNORECASE)),
            ("hotel", re.compile(r"\bhotel\b", re.IGNORECASE)),
            ("non_residential_use", re.compile(r"\bnon-residential\s+use\b", re.IGNORECASE)),
        )
        fee_signal_pattern = re.compile(
            r"(commercial\s+linkage|linkage\s+fee|\bclf\b|impact\s+fee|\bfee\b|\brate\b)",
            re.IGNORECASE,
        )
        unit_pattern = re.compile(
            r"(per\s+square\s+foot|per\s+sq\.?\s*ft|/\s*(?:sq\.?\s*ft|sf)\b)",
            re.IGNORECASE,
        )
        direct_rate_pattern = re.compile(
            r"^\$\s*[0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?\s*"
            r"(?:per\s+(?:square\s+foot|sq\.?\s*ft)|/\s*(?:sq\.?\s*ft|sf)\b)",
            re.IGNORECASE,
        )
        fee_action_pattern = re.compile(
            r"(fee|rate|pay|charge|assessment|recommended\s+fee\s+level)",
            re.IGNORECASE,
        )
        non_fee_cost_assumption_pattern = re.compile(
            r"(cost\s+of\s+development|development\s+cost|construction\s+cost|"
            r"market\s+rent|monthly\s+rent|\brents?\b|assuming\s+\$)",
            re.IGNORECASE,
        )

        segments: list[str] = []
        for raw_line in re.split(r"[\r\n]+", text):
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in re.split(r"(?<=[.;])\s+", line) if part.strip()]
            if len(parts) <= 1 and len(line) <= 260:
                segments.append(line)
                continue
            for part in parts:
                if len(part) <= 260:
                    segments.append(part)
                    continue
                subparts = [subpart.strip() for subpart in re.split(r"(?<=,)\s+", part) if subpart.strip()]
                segments.extend(subparts or [part])

        facts: list[dict[str, Any]] = []
        seen_values: set[float] = set()
        value_pattern = re.compile(
            r"\$\s*(?P<value>[0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)(?![0-9]|\.[0-9])"
        )
        for segment in segments:
            if "$" not in segment:
                continue
            segment_lower = segment.lower()
            if "rent" in segment_lower and "fee" not in segment_lower:
                continue
            has_fee_signal = bool(fee_signal_pattern.search(segment))
            has_land_use = bool(land_use_pattern.search(segment))
            has_unit_signal = bool(unit_pattern.search(segment))
            if not has_unit_signal:
                continue
            if not has_fee_signal and not has_land_use:
                continue

            matches = list(value_pattern.finditer(segment))
            if not matches:
                continue
            table_row_candidate = has_land_use and has_unit_signal and len(segment) <= 240
            table_like = "|" in segment or bool(re.search(r"\s{2,}", segment))

            for match in matches:
                raw = match.group("value")
                local_after_value = segment[match.start() : min(len(segment), match.end() + 48)]
                local_around_value = segment[
                    max(0, match.start() - 120) : min(len(segment), match.end() + 80)
                ]
                has_direct_rate_cue = bool(direct_rate_pattern.search(local_after_value))
                is_table_row_rate = table_row_candidate and len(matches) == 1
                if not has_direct_rate_cue and not is_table_row_rate:
                    continue
                if has_direct_rate_cue and not is_table_row_rate:
                    has_fee_action_near_value = bool(fee_action_pattern.search(local_around_value))
                    has_non_fee_assumption_near_value = bool(
                        non_fee_cost_assumption_pattern.search(local_around_value)
                    )
                    if has_non_fee_assumption_near_value and not has_fee_action_near_value:
                        continue
                value = float(raw.replace(",", ""))
                if value > 100:
                    continue
                if value in seen_values:
                    continue
                seen_values.add(value)
                source_locator = "attachment_probe:table_row" if table_like else "attachment_probe:line_segment"
                locator_quality = "attachment_probe_table_row" if table_like else "attachment_probe_line_rate"
                land_use = "unknown"
                raw_land_use_label = None
                land_use_context = segment[max(0, match.start() - 120) : min(len(segment), match.end() + 80)]
                for candidate, pattern in land_use_extractors:
                    land_use_match = pattern.search(land_use_context)
                    if land_use_match is not None:
                        land_use = candidate
                        raw_land_use_label = land_use_match.group(0)
                        break
                facts.append(
                    {
                        "field": "commercial_linkage_fee_rate_usd_per_sqft",
                        "value": value,
                        "normalized_value": value,
                        "unit": "usd_per_square_foot",
                        "land_use": land_use,
                        "raw_land_use_label": raw_land_use_label,
                        "source_url": source_url,
                        "source_excerpt": segment[:420],
                        "source_locator": source_locator,
                        "locator_quality": locator_quality,
                        "provenance_lane": "structured_attachment_probe",
                        "source_family": source_family,
                        "source_hierarchy_status": "fiscal_or_reg_impact_analysis",
                        "source_title": source_title,
                        "attachment_id": attachment_id,
                        "content_hash": content_hash,
                        "source_ref": (
                            f"legistar::attachment::{attachment_id}"
                            if attachment_id
                            else source_url
                        ),
                        "confidence": 0.78 if has_direct_rate_cue else 0.74,
                    }
                )
        return facts

    async def _probe_legistar_attachment_contents(
        self,
        *,
        client: httpx.AsyncClient,
        attachment_refs: list[dict[str, Any]],
        attachment_context_url: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        probes: list[dict[str, Any]] = []
        structured_facts: list[dict[str, Any]] = []
        verified_san_jose_legistar_context = self._is_verified_san_jose_legistar_context(
            attachment_context_url
        )
        probe_candidates = [
            ref for ref in attachment_refs if isinstance(ref, dict) and self._is_high_value_attachment_ref(ref)
        ][:6]
        for ref in probe_candidates:
            attachment_id = str(ref.get("attachment_id") or "").strip() or None
            title = str(ref.get("title") or "").strip() or None
            url = self._normalize_attachment_url(
                raw_url=str(ref.get("url") or "").strip(),
                fallback_url=attachment_context_url,
            )
            source_family = str(ref.get("source_family") or "unknown").strip() or "unknown"
            if not url.startswith(("http://", "https://")):
                status = "skipped_missing_url"
                failure_class = self._attachment_failure_class(
                    status=status,
                    content_ingested=False,
                )
                probes.append(
                    {
                        "attachment_id": attachment_id,
                        "title": title,
                        "source_title": title,
                        "url": url or None,
                        "source_url": url or None,
                        "source_family": source_family,
                        "status": status,
                        "read_status": "not_read",
                        "failure_class": failure_class,
                        "content_ingested": False,
                        "excerpt": "",
                        "content_excerpt": "",
                        "content_hash": None,
                        "economic_row_count": 0,
                    }
                )
                continue
            if not self._is_official_attachment_url(
                url,
                verified_san_jose_legistar_context=verified_san_jose_legistar_context,
            ):
                status = "skipped_non_official_attachment"
                failure_class = self._attachment_failure_class(
                    status=status,
                    content_ingested=False,
                )
                probes.append(
                    {
                        "attachment_id": attachment_id,
                        "title": title,
                        "source_title": title,
                        "url": url,
                        "source_url": url,
                        "source_family": source_family,
                        "status": status,
                        "read_status": "not_read",
                        "failure_class": failure_class,
                        "content_ingested": False,
                        "excerpt": "",
                        "content_excerpt": "",
                        "content_hash": None,
                        "economic_row_count": 0,
                    }
                )
                continue

            try:
                response = await client.get(url)
                response.raise_for_status()
                content_type = str(response.headers.get("content-type") or "").lower()
                body = response.content[:450000]
            except Exception as exc:  # noqa: BLE001
                status = "fetch_failed"
                failure_class = self._attachment_failure_class(
                    status=status,
                    content_ingested=False,
                )
                probes.append(
                    {
                        "attachment_id": attachment_id,
                        "title": title,
                        "source_title": title,
                        "url": url,
                        "source_url": url,
                        "source_family": source_family,
                        "status": status,
                        "read_status": "fetch_failed",
                        "failure_class": failure_class,
                        "error": str(exc)[:180],
                        "content_ingested": False,
                        "excerpt": "",
                        "content_excerpt": "",
                        "content_hash": None,
                        "economic_row_count": 0,
                    }
                )
                continue

            content_hash = hashlib.sha256(body).hexdigest() if body else None
            if self._is_pdf_attachment(url=url, content_type=content_type):
                pdf_text, pdf_error = self._extract_pdf_text(body)
                if pdf_error is not None:
                    status = "pdf_parse_failed"
                    failure_class = self._attachment_failure_class(
                        status=status,
                        content_ingested=False,
                    )
                    probes.append(
                        {
                            "attachment_id": attachment_id,
                            "title": title,
                            "source_title": title,
                            "url": url,
                            "source_url": url,
                            "source_family": source_family,
                            "status": status,
                            "read_status": "read_failed",
                            "failure_class": failure_class,
                            "error": str(pdf_error)[:180],
                            "content_ingested": False,
                            "excerpt": "",
                            "content_excerpt": "",
                            "content_hash": content_hash,
                            "economic_row_count": 0,
                        }
                    )
                    continue
                text = pdf_text or ""
                excerpt = self._extract_attachment_excerpt(text)
                content_ingested = bool(excerpt)
                status = "ingested_excerpt" if content_ingested else "empty_text"
                failure_class = self._attachment_failure_class(
                    status=status,
                    content_ingested=content_ingested,
                )
                economics = self._extract_attachment_economic_rows(
                    text=text,
                    source_url=url,
                    source_family=source_family,
                    source_title=title,
                    attachment_id=attachment_id,
                    content_hash=content_hash,
                )
                structured_facts.extend(economics)
                probes.append(
                    {
                        "attachment_id": attachment_id,
                        "title": title,
                        "source_title": title,
                        "url": url,
                        "source_url": url,
                        "source_family": source_family,
                        "status": status,
                        "read_status": "read_text" if content_ingested else "read_empty_text",
                        "failure_class": failure_class,
                        "content_ingested": content_ingested,
                        "excerpt": excerpt,
                        "content_excerpt": excerpt,
                        "content_hash": content_hash,
                        "economic_row_count": len(economics),
                    }
                )
                continue
            if self._is_binary_content_type(content_type) or self._looks_like_binary_payload(body):
                status = "binary_unparsed"
                failure_class = self._attachment_failure_class(
                    status=status,
                    content_ingested=False,
                )
                probes.append(
                    {
                        "attachment_id": attachment_id,
                        "title": title,
                        "source_title": title,
                        "url": url,
                        "source_url": url,
                        "source_family": source_family,
                        "status": status,
                        "read_status": "binary_unparsed",
                        "failure_class": failure_class,
                        "content_ingested": False,
                        "excerpt": "",
                        "content_excerpt": "",
                        "content_hash": content_hash,
                        "economic_row_count": 0,
                    }
                )
                continue

            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                text = body.decode("latin-1", errors="ignore")

            excerpt = self._extract_attachment_excerpt(text)
            content_ingested = bool(excerpt)
            status = "ingested_excerpt" if content_ingested else "empty_text"
            failure_class = self._attachment_failure_class(
                status=status,
                content_ingested=content_ingested,
            )
            economics = self._extract_attachment_economic_rows(
                text=text,
                source_url=url,
                source_family=source_family,
                source_title=title,
                attachment_id=attachment_id,
                content_hash=content_hash,
            )
            structured_facts.extend(economics)
            probes.append(
                {
                    "attachment_id": attachment_id,
                    "title": title,
                    "source_title": title,
                    "url": url,
                    "source_url": url,
                    "source_family": source_family,
                    "status": status,
                    "read_status": "read_text" if content_ingested else "read_empty_text",
                    "failure_class": failure_class,
                    "content_ingested": content_ingested,
                    "excerpt": excerpt,
                    "content_excerpt": excerpt,
                    "content_hash": content_hash,
                    "economic_row_count": len(economics),
                }
            )
        return probes, structured_facts

    async def _fetch_legistar_matter_metadata(
        self,
        *,
        client: httpx.AsyncClient,
        selected_url: str,
        search_query: str,
        selected_candidate_context: str = "",
    ) -> dict[str, Any] | None:
        matter_id = self._extract_legistar_matter_id(selected_url=selected_url)
        if not matter_id:
            matter_match = await self._search_legistar_matter_by_context(
                client=client,
                selected_url=selected_url,
                search_query=search_query,
                selected_candidate_context=selected_candidate_context,
            )
            if not matter_match:
                return None
            resolved_id = matter_match.get("MatterId")
            if not isinstance(resolved_id, int):
                return None
            matter_id = resolved_id

        matter_endpoint = f"https://webapi.legistar.com/v1/sanjose/Matters/{matter_id}"
        attachments_endpoint = f"https://webapi.legistar.com/v1/sanjose/Matters/{matter_id}/Attachments"

        try:
            matter_response = await client.get(matter_endpoint)
            matter_response.raise_for_status()
            matter_payload = matter_response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not isinstance(matter_payload, dict):
            return None

        attachments_payload: list[dict[str, Any]] = []
        try:
            attachments_response = await client.get(attachments_endpoint)
            attachments_response.raise_for_status()
            raw_attachments = attachments_response.json()
            if isinstance(raw_attachments, list):
                attachments_payload = [item for item in raw_attachments if isinstance(item, dict)]
        except (httpx.HTTPError, ValueError):
            attachments_payload = []

        matter_url = str(matter_payload.get("MatterInSiteURL") or matter_endpoint)
        attachment_context_url = matter_url if matter_url.startswith(("http://", "https://")) else selected_url
        matter_title = str(matter_payload.get("MatterTitle") or "").strip()
        file_refs: list[str] = []
        related_attachment_refs: list[dict[str, Any]] = []
        seen_attachment_refs: set[tuple[str, str, str]] = set()
        for attachment in attachments_payload:
            attachment_name = str(attachment.get("MatterAttachmentName") or "").strip()
            attachment_id_value = attachment.get("MatterAttachmentId")
            attachment_id = (
                str(attachment_id_value).strip()
                if isinstance(attachment_id_value, (int, str))
                else ""
            )
            file_url = self._normalize_attachment_url(
                raw_url=str(attachment.get("MatterAttachmentHyperlink") or "").strip(),
                fallback_url=attachment_context_url,
            )
            if file_url.startswith("http://") or file_url.startswith("https://"):
                file_refs.append(file_url)
            if not attachment_id and not attachment_name and not file_url:
                continue
            dedupe_key = (attachment_id, attachment_name.lower(), file_url)
            if dedupe_key in seen_attachment_refs:
                continue
            seen_attachment_refs.add(dedupe_key)
            related_attachment_refs.append(
                {
                    "attachment_id": attachment_id or None,
                    "title": attachment_name or None,
                    "url": file_url or None,
                    "source_family": self._classify_legistar_attachment_family(
                        attachment_name=attachment_name,
                        attachment_url=file_url,
                    ),
                }
            )

        attachment_family_counts: dict[str, int] = {}
        for attachment_ref in related_attachment_refs:
            family = str(attachment_ref.get("source_family") or "unknown")
            attachment_family_counts[family] = attachment_family_counts.get(family, 0) + 1

        attachment_content_probes, attachment_probe_facts = await self._probe_legistar_attachment_contents(
            client=client,
            attachment_refs=related_attachment_refs,
            attachment_context_url=attachment_context_url,
        )
        structured_policy_facts = [
            {"field": "matter_attachment_count", "value": float(len(file_refs)), "unit": "count"},
            {
                "field": "matter_attachment_url_count",
                "value": float(len(file_refs)),
                "unit": "count",
            },
            *attachment_probe_facts,
        ]

        return {
            "source_lane": "structured",
            "provider": "legistar_web_api",
            "source_family": "legistar_web_api",
            "access_method": "public_api_json",
            "jurisdiction": "san_jose_ca",
            "artifact_url": matter_url if matter_url.startswith("http") else matter_endpoint,
            "artifact_type": "matter_metadata",
            "source_tier": "tier_b",
            "retrieved_at": _utc_now_iso(),
            "query_text": search_query.strip() or "san jose matter metadata",
            "excerpt": (
                "Structured Legistar matter metadata fetched from San Jose Web API; "
                f"MatterTitle='{matter_title or 'unknown'}', attachments={len(file_refs)}, "
                f"classified_attachment_refs={len(related_attachment_refs)}."
            ),
            "structured_policy_facts": structured_policy_facts,
            "provider_run_id": str(matter_id),
            "linked_artifact_refs": file_refs,
            "related_attachment_refs": related_attachment_refs,
            "attachment_content_probes": attachment_content_probes,
            "reader_artifact_refs": [],
            "true_structured": True,
            "policy_match_key": _policy_match_key_for_url(selected_url or matter_url),
            "policy_match_confidence": 0.95,
            "reconciliation_status": "pending_primary_reconciliation",
            "lineage_metadata": {
                "jurisdiction": "san_jose_ca",
                "matter_id": str(matter_id),
                "event_date": None,
                "event_body_id": None,
                "source_identity": "legistar_web_api",
                "related_attachment_refs": related_attachment_refs,
                "attachment_family_counts": attachment_family_counts,
                "attachment_content_probe_count": len(attachment_content_probes),
                "attachment_content_ingested_count": sum(
                    1 for probe in attachment_content_probes if bool(probe.get("content_ingested"))
                ),
                "attachment_economic_row_count": sum(
                    int(probe.get("economic_row_count") or 0) for probe in attachment_content_probes
                ),
            },
            "diagnostic_facts": [
                {"field": "matter_id", "value": float(matter_id), "unit": "count"},
                {
                    "field": "matter_attachment_probe_count",
                    "value": float(len(attachment_content_probes)),
                    "unit": "count",
                },
                {
                    "field": "matter_attachment_content_ingested_count",
                    "value": float(
                        sum(
                            1 for probe in attachment_content_probes if bool(probe.get("content_ingested"))
                        )
                    ),
                    "unit": "count",
                },
                {
                    "field": "matter_attachment_economic_row_count",
                    "value": float(
                        sum(int(probe.get("economic_row_count") or 0) for probe in attachment_content_probes)
                    ),
                    "unit": "count",
                },
            ],
        }

    @staticmethod
    def _extract_context_dates(*, context_text: str) -> list[str]:
        hints: set[str] = set()
        for match in re.finditer(r"\b(20[0-9]{2})-(0[1-9]|1[0-2])-([0-2][0-9]|3[0-1])\b", context_text):
            hints.add(match.group(0))
        for match in re.finditer(r"\b(0?[1-9]|1[0-2])/([0-2]?[0-9]|3[0-1])/(20[0-9]{2})\b", context_text):
            hints.add(f"{match.group(3)}-{int(match.group(1)):02d}-{int(match.group(2)):02d}")
        for match in re.finditer(
            r"\b("
            r"January|February|March|April|May|June|July|August|September|October|November|December"
            r")\s+([0-9]{1,2}),\s*(20[0-9]{2})\b",
            context_text,
            flags=re.IGNORECASE,
        ):
            month = _MONTH_NUMBER_BY_NAME.get(match.group(1).lower())
            if not month:
                continue
            day = f"{int(match.group(2)):02d}"
            hints.add(f"{match.group(3)}-{month}-{day}")
        return sorted(hints)

    @staticmethod
    def _extract_context_file_tokens(*, context_text: str) -> set[str]:
        return {token.upper() for token in re.findall(r"\b[0-9]{2}-[0-9]{3,5}\b", context_text)}

    @staticmethod
    def _matter_context_tokens(*, context_text: str) -> set[str]:
        tokens = {
            token
            for token in re.findall(r"[a-z0-9#]+", context_text.lower())
            if len(token) >= 4 and token not in _MATTER_CONTEXT_STOPWORDS
        }
        if "clf" in context_text.lower():
            tokens.add("clf")
        return tokens

    @classmethod
    def _score_matter_candidate(
        cls,
        *,
        matter: dict[str, Any],
        context_tokens: set[str],
        file_tokens: set[str],
        date_hints: set[str],
    ) -> int:
        title = str(matter.get("MatterTitle") or "")
        matter_file = str(matter.get("MatterFile") or "").strip().upper()
        text = f"{title} {matter_file}".lower()
        score = 0

        if "commercial linkage impact fee" in text:
            score += 12
        if "commercial linkage" in text:
            score += 8
        if "impact fee" in text:
            score += 5
        if "deferred" in text:
            score -= 8

        for token in context_tokens:
            if token in text:
                score += 2

        if matter_file and matter_file in file_tokens:
            score += 10

        agenda_date = str(matter.get("MatterAgendaDate") or "").strip()
        for hint in date_hints:
            if hint and hint in agenda_date:
                score += 7
                break

        return score

    async def _search_legistar_matter_by_context(
        self,
        *,
        client: httpx.AsyncClient,
        selected_url: str,
        search_query: str,
        selected_candidate_context: str,
    ) -> dict[str, Any] | None:
        _ = selected_url
        endpoint = "https://webapi.legistar.com/v1/sanjose/Matters"
        context_text = " ".join(
            part.strip()
            for part in (search_query, selected_candidate_context)
            if str(part or "").strip()
        )
        if not context_text:
            return None

        date_hints = self._extract_context_dates(context_text=context_text)
        file_tokens = self._extract_context_file_tokens(context_text=context_text)
        context_tokens = self._matter_context_tokens(context_text=context_text)

        query_params: list[dict[str, str]] = []
        for date_hint in date_hints[:2]:
            query_params.append(
                {
                    "$filter": f"MatterAgendaDate eq datetime'{date_hint}T00:00:00'",
                    "$top": "25",
                }
            )
        normalized_context = context_text.lower()
        if "commercial" in normalized_context and "linkage" in normalized_context:
            query_params.append(
                {
                    "$filter": "substringof('Commercial Linkage',MatterTitle)",
                    "$top": "50",
                }
            )
        if "impact fee" in normalized_context:
            query_params.append(
                {
                    "$filter": "substringof('Impact Fee',MatterTitle)",
                    "$top": "50",
                }
            )
        query_params.append({"$top": "50", "$orderby": "MatterAgendaDate desc"})

        matches: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        for params in query_params:
            try:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                continue
            if not isinstance(payload, list):
                continue
            for item in payload:
                if not isinstance(item, dict):
                    continue
                matter_id = item.get("MatterId")
                if not isinstance(matter_id, int) or matter_id in seen_ids:
                    continue
                seen_ids.add(matter_id)
                matches.append(item)

        if not matches:
            return None

        ranked = sorted(
            matches,
            key=lambda item: self._score_matter_candidate(
                matter=item,
                context_tokens=context_tokens,
                file_tokens=file_tokens,
                date_hints=set(date_hints),
            ),
            reverse=True,
        )
        best = ranked[0]
        best_score = self._score_matter_candidate(
            matter=best,
            context_tokens=context_tokens,
            file_tokens=file_tokens,
            date_hints=set(date_hints),
        )
        return best if best_score > 0 else None

    async def _fetch_legistar_event_metadata(
        self, *, client: httpx.AsyncClient
    ) -> dict[str, Any] | None:
        endpoint = "https://webapi.legistar.com/v1/sanjose/Events?$top=1&$orderby=EventDate desc"
        try:
            response = await client.get(endpoint)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not isinstance(payload, list) or not payload:
            return None

        event = payload[0] if isinstance(payload[0], dict) else {}
        event_id = event.get("EventId")
        event_body_id = event.get("EventBodyId")
        event_date = str(event.get("EventDate") or "")
        event_url = str(event.get("EventInSiteURL") or endpoint)
        if not event_id:
            return None

        facts: list[dict[str, Any]] = [
            {"field": "event_attachment_hint_count", "value": 0.0, "unit": "count"},
        ]
        diagnostic_facts: list[dict[str, Any]] = [
            {"field": "event_id", "value": float(event_id), "unit": "count"},
        ]
        if isinstance(event_body_id, int):
            diagnostic_facts.append(
                {"field": "event_body_id", "value": float(event_body_id), "unit": "count"}
            )

        return {
            "source_lane": "structured",
            "provider": "legistar_web_api",
            "source_family": "legistar_web_api",
            "access_method": "public_api_json",
            "jurisdiction": "san_jose_ca",
            "artifact_url": event_url,
            "artifact_type": "meeting_metadata",
            "source_tier": "tier_b",
            "retrieved_at": _utc_now_iso(),
            "query_text": "latest san jose legistar event metadata",
            "excerpt": (
                "Structured Legistar event metadata fetched from San Jose Web API; "
                f"EventId={event_id}, EventDate={event_date or 'unknown'}."
            ),
            "structured_policy_facts": facts,
            "diagnostic_facts": diagnostic_facts,
            "provider_run_id": str(event_id),
            "true_structured": True,
            "policy_match_key": _policy_match_key_for_url(event_url),
            "policy_match_confidence": 0.6,
            "reconciliation_status": "latest_event_fallback_unreconciled",
            "lineage_metadata": {
                "jurisdiction": "san_jose_ca",
                "matter_id": None,
                "event_date": event_date or None,
                "event_body_id": str(event_body_id) if isinstance(event_body_id, int) else None,
                "source_identity": "legistar_web_api",
            },
        }

    async def _fetch_san_jose_ckan_metadata(
        self,
        *,
        client: httpx.AsyncClient,
        search_query: str,
        selected_url: str,
    ) -> dict[str, Any] | None:
        safe_query = search_query.strip() or "housing"
        endpoint = (
            "https://data.sanjoseca.gov/api/3/action/package_search"
            f"?q={quote_plus(safe_query)}&rows=5"
        )
        try:
            response = await client.get(endpoint)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not isinstance(payload, dict) or payload.get("success") is not True:
            return None

        result = payload.get("result")
        if not isinstance(result, dict):
            return None
        total_count = result.get("count")
        rows = result.get("results")
        if not isinstance(total_count, int) or not isinstance(rows, list):
            return None

        row_dicts = [row for row in rows if isinstance(row, dict)]
        relevant_rows = [
            row
            for row in row_dicts
            if self._is_economic_dataset(
                dataset=row,
                search_query=search_query,
                selected_url=selected_url,
            )
        ]
        with_resource_urls = [
            row
            for row in relevant_rows
            if self._resource_urls(row)
        ]
        if not with_resource_urls:
            return None

        top_dataset = with_resource_urls[0]
        top_dataset_urls = self._resource_urls(top_dataset)
        top_dataset_url = top_dataset_urls[0]
        resource_count = len(top_dataset_urls)
        retrieved_at = _utc_now_iso()
        template_context = " ".join(
            [
                safe_query,
                str(top_dataset.get("title") or ""),
                str(top_dataset.get("notes") or ""),
                " ".join(str(row.get("title") or "") for row in relevant_rows[:3]),
            ]
        ).strip()
        non_fee_facts = extract_non_fee_policy_facts(
            text=template_context,
            source_url=top_dataset_url,
            source_family="san_jose_open_data_ckan",
            jurisdiction="san_jose_ca",
            retrieved_at=retrieved_at,
            source_locator_prefix="structured_template:san_jose_open_data_ckan",
            geography="san_jose_ca",
        )
        policy_families, evidence_uses, economic_relevance, moat_reason = self._non_fee_template_metadata(
            non_fee_facts
        )
        facts: list[dict[str, Any]] = [
            {"field": "relevant_dataset_count", "value": float(len(relevant_rows)), "unit": "count"},
            {
                "field": "relevant_dataset_with_resource_url_count",
                "value": float(len(with_resource_urls)),
                "unit": "count",
            },
        ]
        facts.append({"field": "top_dataset_resource_count", "value": float(resource_count), "unit": "count"})
        facts.extend(non_fee_facts)

        return {
            "source_lane": "structured",
            "provider": "san_jose_open_data_ckan",
            "source_family": "san_jose_open_data_ckan",
            "access_method": "ckan_api_json",
            "jurisdiction": "san_jose_ca",
            "artifact_url": top_dataset_url if top_dataset_url.startswith("http") else endpoint,
            "artifact_type": "open_data_catalog_metadata",
            "source_tier": "tier_b",
            "retrieved_at": retrieved_at,
            "query_text": safe_query,
            "excerpt": (
                "Structured CKAN metadata from San Jose Open Data; "
                f"query='{safe_query}', relevant_datasets={len(relevant_rows)}, "
                f"relevant_with_resource_urls={len(with_resource_urls)}, "
                f"non_fee_template_facts={len(non_fee_facts)}."
            ),
            "structured_policy_facts": facts,
            "diagnostic_facts": [
                {"field": "dataset_match_count_raw", "value": float(total_count), "unit": "count"}
            ],
            "provider_run_id": str(total_count),
            "linked_artifact_refs": top_dataset_urls,
            "true_structured": True,
            "policy_match_key": _policy_match_key_for_url(selected_url),
            "policy_match_confidence": 0.45,
            "reconciliation_status": "contextual_metadata_linked_to_policy_query",
            "policy_families": policy_families,
            "policy_family": policy_families[0] if policy_families else None,
            "evidence_uses": evidence_uses,
            "evidence_use": evidence_uses[0] if evidence_uses else None,
            "economic_relevance": economic_relevance,
            "moat_value_reason": moat_reason,
            "lineage_metadata": {
                "jurisdiction": "san_jose_ca",
                "matter_id": None,
                "event_date": None,
                "event_body_id": None,
                "source_identity": "san_jose_open_data_ckan",
            },
        }

    async def _fetch_california_ckan_metadata(
        self,
        *,
        client: httpx.AsyncClient,
        jurisdiction: str,
        search_query: str,
        selected_url: str,
        selected_candidate_context: str,
    ) -> dict[str, Any] | None:
        safe_query = search_query.strip() or "zoning policy"
        endpoint = (
            "https://data.ca.gov/api/3/action/package_search"
            f"?q={quote_plus(safe_query)}&rows=5"
        )
        try:
            response = await client.get(endpoint)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not isinstance(payload, dict) or payload.get("success") is not True:
            return None
        result = payload.get("result")
        if not isinstance(result, dict):
            return None
        total_count = result.get("count")
        rows = result.get("results")
        if not isinstance(total_count, int) or not isinstance(rows, list):
            return None

        row_dicts = [row for row in rows if isinstance(row, dict)]
        relevant_rows = [
            row
            for row in row_dicts
            if self._is_economic_dataset(
                dataset=row,
                search_query=f"{search_query} {selected_candidate_context}",
                selected_url=selected_url,
            )
        ]
        with_resource_urls = [row for row in relevant_rows if self._resource_urls(row)]
        if not with_resource_urls:
            return None

        top_dataset = with_resource_urls[0]
        top_dataset_urls = self._resource_urls(top_dataset)
        top_dataset_url = top_dataset_urls[0]
        retrieved_at = _utc_now_iso()
        template_context = " ".join(
            [
                safe_query,
                selected_candidate_context,
                str(top_dataset.get("title") or ""),
                str(top_dataset.get("notes") or ""),
                " ".join(str(row.get("title") or "") for row in relevant_rows[:3]),
            ]
        ).strip()
        non_fee_facts = extract_non_fee_policy_facts(
            text=template_context,
            source_url=top_dataset_url,
            source_family="california_open_data_ckan",
            jurisdiction=jurisdiction,
            retrieved_at=retrieved_at,
            source_locator_prefix="structured_template:california_open_data_ckan",
            geography="california_state",
        )
        policy_families, evidence_uses, economic_relevance, moat_reason = self._non_fee_template_metadata(
            non_fee_facts
        )

        facts: list[dict[str, Any]] = [
            {
                "field": "relevant_dataset_count",
                "value": float(len(relevant_rows)),
                "unit": "count",
            },
            {
                "field": "relevant_dataset_with_resource_url_count",
                "value": float(len(with_resource_urls)),
                "unit": "count",
            },
            {
                "field": "top_dataset_resource_count",
                "value": float(len(top_dataset_urls)),
                "unit": "count",
            },
        ]
        facts.extend(non_fee_facts)

        return {
            "source_lane": "structured",
            "provider": "california_open_data_ckan",
            "source_family": "california_open_data_ckan",
            "access_method": "ckan_api_json",
            "jurisdiction": jurisdiction,
            "artifact_url": top_dataset_url if top_dataset_url.startswith("http") else endpoint,
            "artifact_type": "open_data_catalog_metadata",
            "source_tier": "tier_b",
            "retrieved_at": retrieved_at,
            "query_text": safe_query,
            "excerpt": (
                "Structured CKAN metadata from California Open Data; "
                f"query='{safe_query}', relevant_datasets={len(relevant_rows)}, "
                f"relevant_with_resource_urls={len(with_resource_urls)}, "
                f"non_fee_template_facts={len(non_fee_facts)}."
            ),
            "structured_policy_facts": facts,
            "diagnostic_facts": [
                {"field": "dataset_match_count_raw", "value": float(total_count), "unit": "count"}
            ],
            "provider_run_id": str(total_count),
            "linked_artifact_refs": top_dataset_urls,
            "true_structured": True,
            "policy_match_key": _policy_match_key_for_url(selected_url or top_dataset_url),
            "policy_match_confidence": 0.4,
            "reconciliation_status": "contextual_metadata_linked_to_policy_query",
            "policy_families": policy_families,
            "policy_family": policy_families[0] if policy_families else None,
            "evidence_uses": evidence_uses,
            "evidence_use": evidence_uses[0] if evidence_uses else None,
            "economic_relevance": economic_relevance,
            "moat_value_reason": moat_reason,
            "lineage_metadata": {
                "jurisdiction": jurisdiction,
                "matter_id": None,
                "event_date": None,
                "event_body_id": None,
                "source_identity": "california_open_data_ckan",
            },
        }
