"""Domain command service for Windmill/orchestrator integration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from services.pipeline.domain.constants import CONTRACT_VERSION
from services.pipeline.domain.identity import build_v2_canonical_document_key
from services.pipeline.domain.in_memory import InMemoryDomainState, stable_json_hash
from services.pipeline.domain.models import CommandEnvelope, CommandResponse, FreshnessPolicy
from services.pipeline.domain.ports import (
    Analyzer,
    ArtifactStore,
    ReaderProvider,
    SearchProvider,
    SearchResultItem,
    VectorStore,
)

MEETING_ARTIFACT_URL_SIGNALS = (
    "legistar.com",
    "granicus.com",
    "agendaviewer",
    "meetingdetail",
    "view.ashx",
    "gateway.aspx",
    "/agenda",
    "/minutes",
    ".pdf",
)

HIGH_VALUE_URL_SIGNALS = (
    "legistar.com/gateway.aspx",
    "legistar.com/meetingdetail.aspx",
    ".pdf",
    "view.ashx",
)

LOW_VALUE_AGENDA_HEADER_URL_SIGNALS = (
    "granicus.com/agendaviewer",
    "agendaviewer.php",
    "/your-government/agendas-minutes",
    "/city-council/council-agendas-minutes",
    "/city-council/council-agendas",
    "calendar.aspx",
    "departmentdetail.aspx",
    "/resource-library/council-memos",
    "/resource-library/",
)

LOW_VALUE_PORTAL_PREFETCH_SKIP_URL_SIGNALS = (
    "/your-government/agendas-minutes",
    "/city-council/council-agendas-minutes",
    "/city-council/council-agendas",
    "calendar.aspx",
    "departmentdetail.aspx",
    "/resource-library/council-memos",
)

LOW_VALUE_FALLBACK_URL_SIGNALS = (
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "dailymotion.com",
)

LOW_VALUE_FALLBACK_TEXT_SIGNALS = (
    "youtube",
    "video",
    "transcript",
    "podcast",
    "watch",
)

LOW_VALUE_PORTAL_URL_PENALTY = 10
ECONOMIC_LOW_VALUE_PORTAL_EXTRA_PENALTY = 6
ECONOMIC_PROCEDURAL_PAGE_PENALTY = 20
ECONOMIC_SIGNAL_BOOST = 8
ECONOMIC_NUMERIC_SIGNAL_BOOST = 6
ECONOMIC_OFFICIAL_SOURCE_BOOST = 4
ECONOMIC_EXTERNAL_SOURCE_PENALTY = 10

CONCRETE_ARTIFACT_URL_SIGNALS = (
    "meetingdetail.aspx?id=",
    "meetingdetail.aspx?legid=",
    "gateway.aspx?id=",
    "agendaviewer.php?clip_id=",
    "/agendacenter/viewfile/minutes/",
    "/agendacenter/viewfile/agenda/",
)

MEETING_ARTIFACT_TEXT_SIGNALS = (
    "agenda",
    "minutes",
    "meeting",
    "council",
    "hearing",
    "ordinance",
    "resolution",
    "public comment",
    "housing",
)

TEXT_ACTION_SIGNALS = (
    "ordinance no.",
    "approved",
    "adopted",
    "voted",
    "motion",
    "resolution",
    "compliance",
    "incentive",
    "rent",
    "affordability",
    "multifamily",
)

HEADER_LOGISTICS_MARKERS = (
    "location:",
    "council chambers",
    "interpretation is available",
    "webinar",
    "webcast",
    "teleconference",
    "dial-in",
    "amended agenda",
    "meeting starts at",
)

GENERIC_NAVIGATION_PENALTIES = (
    "home",
    "homepage",
    "resource library",
    "resources",
    "departments",
    "services",
    "city hall",
    "about us",
)

NAVIGATION_MARKERS = (
    "home",
    "contact",
    "sitemap",
    "menu",
    "navigation",
    "skip to content",
    "privacy",
    "accessibility",
    "subscribe",
    "sign up",
    "alerts",
    "departments",
)

SUBSTANTIVE_MARKERS = (
    "meeting",
    "minutes",
    "agenda",
    "council",
    "ordinance",
    "resolution",
    "vote",
    "hearing",
    "public comment",
    "housing",
    "budget",
    "policy",
)

ACTION_MARKERS = (
    "approved",
    "adopted",
    "motion",
    "vote",
    "voted",
    "resolution",
    "ordinance",
    "staff report",
    "recommendation",
    "recommended",
    "public hearing",
    "agenda item",
    "item 8",
    "item 10",
    "directed staff",
    "memorandum",
)

ANALYSIS_ACTION_SIGNALS = (
    "housing",
    "ordinance",
    "approved",
    "adopted",
    "resolution",
    "incentive",
    "affordability",
    "rent",
    "multifamily",
    "agenda item",
    "item ",
    "public hearing",
    "compliance",
    "mobilehome",
    "tenant",
    "zoning",
)

ANALYSIS_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "made",
    "of",
    "on",
    "or",
    "the",
    "these",
    "this",
    "to",
    "was",
    "were",
    "what",
    "which",
    "with",
}

ECONOMIC_QUERY_INTENT_SIGNALS = (
    "fee",
    "fees",
    "rate",
    "rates",
    "per square foot",
    "per sq ft",
    "commercial linkage",
    "impact fee",
    "affordable housing impact fee",
    "cost",
    "fiscal",
    "economic",
)

ECONOMIC_VALUE_TEXT_SIGNALS = (
    "commercial linkage fee",
    "affordable housing impact fee",
    "impact fee",
    "fee schedule",
    "fees and rates",
    "per square foot",
    "per sq ft",
    "rate schedule",
    "nexus",
)

ECONOMIC_VALUE_URL_SIGNALS = (
    "/fees",
    "/fee",
    "/rates",
    "/rate",
    "impact-fee",
    "linkage-fee",
    "fee-schedule",
    "rate-schedule",
    "nexus",
    "staff-report",
    "resolution-",
)

ECONOMIC_PROCEDURAL_URL_SIGNALS = (
    "gateway.aspx",
    "meetingdetail.aspx?id=",
    "legislationdetail.aspx?id=",
    "calendar.aspx",
    "/agendas-minutes",
)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _stable_chunk_id(
    *,
    canonical_document_key: str,
    content_hash: str,
    chunk_index: int,
    chunk_text: str,
) -> str:
    chunk_text_hash = _hash_text(chunk_text)
    material = (
        f"{CONTRACT_VERSION}|{canonical_document_key}|{content_hash}|{chunk_index}|{chunk_text_hash}"
    )
    return f"chunk_{_hash_text(material)}"


def _split_chunks(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    return lines


def assess_reader_substance(text: str) -> tuple[bool, dict[str, Any]]:
    normalized_lines = [line.strip().lower() for line in text.splitlines() if line.strip()]
    joined = " ".join(normalized_lines)
    word_count = len(re.findall(r"[a-z0-9$%.-]+", joined))
    nav_line_hits = sum(
        1 for line in normalized_lines if any(marker in line for marker in NAVIGATION_MARKERS)
    )
    nav_marker_hits = sum(1 for marker in NAVIGATION_MARKERS if marker in joined)
    substantive_hits = sum(1 for marker in SUBSTANTIVE_MARKERS if marker in joined)
    action_hits = sum(1 for marker in ACTION_MARKERS if marker in joined)
    logistics_marker_hits = sum(1 for marker in HEADER_LOGISTICS_MARKERS if marker in joined)
    markdown_image_count = joined.count("![image")
    bullet_line_count = sum(1 for line in normalized_lines if line.startswith("- "))
    line_count = len(normalized_lines)

    reason = "ok"
    is_substantive = True
    if not normalized_lines or word_count == 0:
        reason = "empty_reader_output"
        is_substantive = False
    elif nav_line_hits >= max(2, line_count // 2) and substantive_hits == 0:
        reason = "navigation_heavy"
        is_substantive = False
    elif nav_marker_hits >= 6 and substantive_hits <= 1:
        reason = "navigation_heavy"
        is_substantive = False
    elif markdown_image_count >= 8 and action_hits <= 1:
        reason = "navigation_heavy"
        is_substantive = False
    elif nav_marker_hits >= 8 and bullet_line_count >= 20 and action_hits <= 2:
        reason = "navigation_heavy"
        is_substantive = False
    elif (
        markdown_image_count >= 12
        and bullet_line_count >= 80
        and nav_marker_hits >= 4
        and bullet_line_count >= max(120, int(line_count * 0.6))
    ):
        reason = "navigation_heavy"
        is_substantive = False
    elif logistics_marker_hits >= 2 and action_hits <= 1 and substantive_hits <= 5:
        reason = "agenda_header_logistics_only"
        is_substantive = False
    elif logistics_marker_hits >= 1 and action_hits == 0 and word_count < 160:
        reason = "agenda_header_logistics_only"
        is_substantive = False
    elif word_count < 6:
        reason = "content_too_short"
        is_substantive = False
    elif line_count <= 2 and word_count < 24 and action_hits == 0:
        reason = "content_too_short"
        is_substantive = False
    elif word_count < 25 and substantive_hits == 0:
        reason = "low_substantive_signal"
        is_substantive = False

    details = {
        "reason": reason,
        "word_count": word_count,
        "line_count": line_count,
        "navigation_line_hits": nav_line_hits,
        "navigation_marker_hits": nav_marker_hits,
        "substantive_marker_hits": substantive_hits,
        "action_marker_hits": action_hits,
        "logistics_marker_hits": logistics_marker_hits,
        "markdown_image_count": markdown_image_count,
        "bullet_line_count": bullet_line_count,
    }
    return is_substantive, details


def rank_reader_candidates(
    candidates: list[SearchResultItem],
    *,
    max_candidates: int | None = None,
    query_context: str | None = None,
) -> list[dict[str, Any]]:
    economic_query = _is_economic_analysis_query(query_context)
    ranked: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        url = candidate.url.strip()
        title = candidate.title.strip()
        snippet = candidate.snippet.strip()
        lowered_url = url.lower()
        lowered_text = f"{title} {snippet}".lower()
        combined_text = f"{lowered_url} {lowered_text}"
        score = 0
        reasons: list[str] = []

        for signal in MEETING_ARTIFACT_URL_SIGNALS:
            if signal in lowered_url:
                score += 5 if signal in {"legistar.com", "granicus.com", ".pdf"} else 3
                reasons.append(f"url_signal:{signal}")
        for signal in HIGH_VALUE_URL_SIGNALS:
            if signal in lowered_url:
                score += 6 if signal == ".pdf" else 5
                reasons.append(f"url_high_value:{signal}")
        for signal in CONCRETE_ARTIFACT_URL_SIGNALS:
            if signal in lowered_url:
                score += 7 if signal == ".pdf" else 6
                reasons.append(f"url_concrete_artifact:{signal}")
        if _is_concrete_artifact_url(url):
            score += 8
            reasons.append("url_concrete_artifact:parsed")
        for signal in LOW_VALUE_AGENDA_HEADER_URL_SIGNALS:
            if signal in lowered_url:
                score -= LOW_VALUE_PORTAL_URL_PENALTY
                reasons.append(f"url_penalty:{signal}")
                if economic_query:
                    score -= ECONOMIC_LOW_VALUE_PORTAL_EXTRA_PENALTY
                    reasons.append(f"url_penalty_economic:{signal}")
        for signal in MEETING_ARTIFACT_TEXT_SIGNALS:
            if signal in lowered_text:
                score += 1
                reasons.append(f"text_signal:{signal}")
        for signal in TEXT_ACTION_SIGNALS:
            if signal in lowered_text:
                score += 2
                reasons.append(f"text_action:{signal}")
        for signal in HEADER_LOGISTICS_MARKERS:
            if signal in lowered_text:
                score -= 3
                reasons.append(f"text_penalty:{signal}")
        for penalty in GENERIC_NAVIGATION_PENALTIES:
            if penalty in lowered_text or penalty in lowered_url:
                score -= 2
                reasons.append(f"penalty:{penalty}")

        if economic_query:
            if any(signal in combined_text for signal in ECONOMIC_VALUE_TEXT_SIGNALS):
                score += ECONOMIC_SIGNAL_BOOST
                reasons.append("economic_signal:context")
            if any(signal in lowered_url for signal in ECONOMIC_VALUE_URL_SIGNALS):
                score += ECONOMIC_SIGNAL_BOOST
                reasons.append("economic_signal:url")
            if _is_trusted_public_records_url(url):
                if "sanjoseca.gov" in lowered_url:
                    score += ECONOMIC_OFFICIAL_SOURCE_BOOST
                    reasons.append("economic_signal:official_source")
            else:
                score -= ECONOMIC_EXTERNAL_SOURCE_PENALTY
                reasons.append("economic_penalty:external_source")
            if _has_economic_numeric_signal(combined_text):
                score += ECONOMIC_NUMERIC_SIGNAL_BOOST
                reasons.append("economic_signal:numeric")
            if _is_procedural_page_without_economic_signal(
                lowered_url=lowered_url,
                lowered_text=lowered_text,
            ):
                score -= ECONOMIC_PROCEDURAL_PAGE_PENALTY
                reasons.append("economic_penalty:procedural_without_value_signal")

        ranked.append(
            {
                "input_index": index,
                "url": url,
                "title": title,
                "snippet": snippet,
                "score": score,
                "reasons": reasons,
            }
        )

    ranked.sort(
        key=lambda item: (
            -int(item["score"]),
            int(item["input_index"]),
            str(item["url"]),
        )
    )
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank

    if max_candidates is not None:
        return ranked[: max(0, max_candidates)]
    return ranked


def _is_trusted_public_records_url(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return (
        host.endswith(".gov")
        or host.endswith(".ca.gov")
        or host.endswith(".us")
        or "legistar.com" in host
        or "granicus.com" in host
    )


def prefetch_skip_reason(url: str) -> str | None:
    lowered_url = url.strip().lower()
    for signal in LOW_VALUE_PORTAL_PREFETCH_SKIP_URL_SIGNALS:
        if signal in lowered_url:
            return signal
    return None


def _is_weak_reader_fallback_candidate(candidate: SearchResultItem) -> bool:
    lowered_url = candidate.url.lower().strip()
    lowered_text = f"{candidate.title} {candidate.snippet}".lower()
    if _is_concrete_artifact_url(candidate.url):
        return False
    if any(signal in lowered_url for signal in LOW_VALUE_FALLBACK_URL_SIGNALS):
        return True
    return any(signal in lowered_text for signal in LOW_VALUE_FALLBACK_TEXT_SIGNALS)


def _parsed_query_params(url: str) -> dict[str, list[str]]:
    return {key.lower(): values for key, values in parse_qs(urlsplit(url).query).items()}


def _has_query_key(params: dict[str, list[str]], key: str) -> bool:
    return key in params and any(str(value).strip() for value in params[key])


def _has_query_value(params: dict[str, list[str]], key: str, expected_values: tuple[str, ...]) -> bool:
    if key not in params:
        return False
    allowed = {value.lower() for value in expected_values}
    return any(str(value).strip().lower() in allowed for value in params[key])


def _has_query_suffix(params: dict[str, list[str]], key: str, suffix: str) -> bool:
    if key not in params:
        return False
    target = suffix.lower()
    return any(str(value).strip().lower().endswith(target) for value in params[key])


def _is_concrete_artifact_url(url: str) -> bool:
    lowered_url = url.lower().strip()
    parsed = urlsplit(url)
    path = parsed.path.lower()
    host = parsed.netloc.lower()
    params = _parsed_query_params(url)
    is_official_host = host.endswith(".gov") or host.endswith(".ca.gov") or host.endswith(".us")
    is_legistar_host = "legistar.com" in host
    is_granicus_host = "granicus.com" in host
    is_trusted_public_records_host = is_official_host or is_legistar_host or is_granicus_host

    if lowered_url.endswith(".pdf") or "/pdf/" in lowered_url:
        return is_trusted_public_records_host

    if is_legistar_host and "meetingdetail.aspx" in path and (_has_query_key(params, "id") or _has_query_key(params, "legid")):
        return True

    if is_legistar_host and "view.ashx" in path and _has_query_key(params, "id") and _has_query_value(params, "m", ("a", "m", "f")):
        return True

    if is_legistar_host and "gateway.aspx" in path and _has_query_key(params, "id"):
        if _has_query_suffix(params, "id", ".pdf") or _has_query_value(params, "m", ("a", "m", "f")):
            return True

    if is_granicus_host and "agendaviewer.php" in path and _has_query_key(params, "clip_id"):
        return True

    if is_official_host and "/agendacenter/viewfile/minutes/" in path:
        return True
    if is_official_host and "/agendacenter/viewfile/agenda/" in path:
        return True

    return False


def _tokenize_question_terms(question: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", question.lower())
    deduped: list[str] = []
    for token in tokens:
        if len(token) < 3 or token in ANALYSIS_STOPWORDS:
            continue
        if token not in deduped:
            deduped.append(token)
    return deduped


def _is_economic_analysis_query(query_context: str | None) -> bool:
    if not query_context:
        return False
    lowered = query_context.strip().lower()
    return any(signal in lowered for signal in ECONOMIC_QUERY_INTENT_SIGNALS)


def _has_economic_numeric_signal(text: str) -> bool:
    return bool(
        re.search(
            r"(\$\s*\d+(?:,\d{3})*(?:\.\d+)?)|(\b\d+(?:\.\d+)?\s*(?:%|percent)\b)|(\bper\s+(?:sq\.?\s*ft|square\s+foot|unit|acre)\b)",
            text,
        )
    )


def _is_procedural_page_without_economic_signal(*, lowered_url: str, lowered_text: str) -> bool:
    if any(signal in lowered_url for signal in ECONOMIC_VALUE_URL_SIGNALS):
        return False
    if _has_economic_numeric_signal(lowered_text):
        return False
    return any(signal in lowered_url for signal in ECONOMIC_PROCEDURAL_URL_SIGNALS)


def _normalize_chunk_content(chunk: dict[str, Any]) -> str:
    content = chunk.get("content")
    return str(content) if content is not None else ""


def rank_evidence_chunks(
    *,
    question: str,
    chunks: list[dict[str, Any]],
    max_selected: int = 20,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    question_terms = _tokenize_question_terms(question)
    ranked: list[dict[str, Any]] = []
    for input_index, chunk in enumerate(chunks):
        content = _normalize_chunk_content(chunk)
        lowered = content.lower()
        score = 0
        matched_terms: list[str] = []
        matched_action_signals: list[str] = []

        for term in question_terms:
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                score += 3
                matched_terms.append(term)

        for signal in ANALYSIS_ACTION_SIGNALS:
            if signal in lowered:
                score += 4
                matched_action_signals.append(signal)

        if re.search(r"\b(item|agenda item)\s+\d+(\.\d+)?\b", lowered):
            score += 5
        if re.search(r"\b(ordinance|resolution)\s+no\.?\s*[0-9]+\b", lowered):
            score += 5

        nav_hits = sum(1 for marker in NAVIGATION_MARKERS if marker in lowered)
        if nav_hits >= 3 and len(matched_action_signals) == 0:
            score -= 6

        ranked.append(
            {
                "chunk": chunk,
                "content": content,
                "score": score,
                "input_index": input_index,
                "matched_question_terms": matched_terms,
                "matched_action_signals": matched_action_signals,
                "snippet": re.sub(r"\s+", " ", content.strip())[:200],
            }
        )

    ranked.sort(
        key=lambda item: (
            -int(item["score"]),
            -len(item["matched_action_signals"]),
            -len(item["matched_question_terms"]),
            int(item["chunk"].get("chunk_index", 0)),
            int(item["input_index"]),
            str(item["chunk"].get("chunk_id", "")),
        )
    )
    selected_rows = ranked[: max(0, max_selected)]
    selected_chunks = [dict(item["chunk"]) for item in selected_rows]

    audit: list[dict[str, Any]] = []
    for rank, row in enumerate(selected_rows, start=1):
        audit.append(
            {
                "rank": rank,
                "score": int(row["score"]),
                "chunk_id": row["chunk"].get("chunk_id"),
                "chunk_index": row["chunk"].get("chunk_index"),
                "matched_question_terms": list(row["matched_question_terms"]),
                "matched_action_signals": list(row["matched_action_signals"]),
                "snippet": row["snippet"],
            }
        )

    return selected_chunks, audit


class PipelineDomainCommands:
    """Implements the six coarse commands with deterministic in-memory semantics."""

    def __init__(
        self,
        *,
        state: InMemoryDomainState,
        search_provider: SearchProvider,
        reader_provider: ReaderProvider,
        artifact_store: ArtifactStore,
        vector_store: VectorStore,
        analyzer: Analyzer,
    ) -> None:
        self.state = state
        self.search_provider = search_provider
        self.reader_provider = reader_provider
        self.artifact_store = artifact_store
        self.vector_store = vector_store
        self.analyzer = analyzer

    def _reuse_if_idempotent(self, envelope: CommandEnvelope) -> CommandResponse | None:
        cached = self.state.command_results.get(self._command_result_key(envelope))
        if not cached:
            return None
        response = CommandResponse(**cached)
        response.details = {
            **response.details,
            "idempotent_reuse": True,
        }
        return response

    def _store_result(self, envelope: CommandEnvelope, response: CommandResponse) -> CommandResponse:
        self.state.command_results[self._command_result_key(envelope)] = asdict(response)
        return response

    def _command_result_key(self, envelope: CommandEnvelope) -> str:
        return f"{envelope.command}:{envelope.idempotency_key}"

    def _windmill_refs(self, envelope: CommandEnvelope) -> dict[str, str]:
        return {
            "windmill_run_id": envelope.windmill.run_id,
            "windmill_job_id": envelope.windmill.job_id,
        }

    def search_materialize(
        self, *, envelope: CommandEnvelope, query: str, max_results: int = 10
    ) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        try:
            results = self.search_provider.search(
                query=query,
                jurisdiction_id=envelope.jurisdiction_id,
                source_family=envelope.source_family,
                max_results=max_results,
            )
        except Exception as exc:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="search_materialize",
                    status="failed_retryable",
                    decision_reason="search_transport_error",
                    retry_class="transport",
                    alerts=[f"search_provider_error:{exc}"],
                    refs=self._windmill_refs(envelope),
                ),
            )

        snapshot_hash = stable_json_hash(
            {
                "query": query,
                "jurisdiction_id": envelope.jurisdiction_id,
                "source_family": envelope.source_family,
                "results": [asdict(item) for item in results],
            }
        )
        snapshot_id = f"snapshot_{snapshot_hash[:16]}"
        self.state.search_snapshots[snapshot_id] = {
            "snapshot_id": snapshot_id,
            "query": query,
            "jurisdiction_id": envelope.jurisdiction_id,
            "source_family": envelope.source_family,
            "captured_at": self.state.now.isoformat(),
            "results": [asdict(item) for item in results],
        }

        status = "succeeded" if results else "succeeded_with_alerts"
        decision_reason = "fresh_snapshot_materialized" if results else "search_empty_result"
        alerts = [] if results else ["search_results_empty"]

        return self._store_result(
            envelope,
            CommandResponse(
                command="search_materialize",
                status=status,
                decision_reason=decision_reason,
                retry_class="none",
                alerts=alerts,
                counts={"search_results": len(results)},
                refs={**self._windmill_refs(envelope), "search_snapshot_id": snapshot_id},
                details={"query": query},
            ),
        )

    def freshness_gate(
        self,
        *,
        envelope: CommandEnvelope,
        snapshot_id: str,
        policy: FreshnessPolicy,
        latest_success_at: datetime | None,
    ) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        snapshot = self.state.search_snapshots.get(snapshot_id)
        if not snapshot:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="freshness_gate",
                    status="failed_terminal",
                    decision_reason="missing_snapshot",
                    retry_class="contract_violation",
                    refs=self._windmill_refs(envelope),
                ),
            )

        captured_at = datetime.fromisoformat(snapshot["captured_at"])
        snapshot_age_hours = int((_as_utc(self.state.now) - _as_utc(captured_at)).total_seconds() / 3600)
        result_count = len(snapshot["results"])

        fallback_age_hours = None
        if latest_success_at:
            fallback_age_hours = int(
                (_as_utc(self.state.now) - _as_utc(latest_success_at)).total_seconds() / 3600
            )

        freshness_status = "fresh"
        alerts: list[str] = []
        status = "succeeded"

        if result_count == 0:
            if fallback_age_hours is not None and fallback_age_hours <= policy.stale_usable_ceiling_hours:
                freshness_status = "empty_but_usable"
                status = "succeeded_with_alerts"
                alerts.append("source_search_failed_using_last_success")
            else:
                freshness_status = "empty_blocked"
                status = "blocked"
                alerts.append("empty_search_results_fail_closed")
        elif snapshot_age_hours <= policy.fresh_hours:
            freshness_status = "fresh"
        elif snapshot_age_hours <= policy.stale_usable_ceiling_hours:
            freshness_status = "stale_but_usable"
            status = "succeeded_with_alerts"
            alerts.append("source_search_failed_using_last_success")
        else:
            freshness_status = "stale_blocked"
            status = "blocked"
            alerts.append("stale_search_results_fail_closed")

        retry_class = "none" if status != "blocked" else "operator_required"
        return self._store_result(
            envelope,
            CommandResponse(
                command="freshness_gate",
                status=status,
                decision_reason=freshness_status,
                retry_class=retry_class,
                alerts=alerts,
                counts={"search_results": result_count},
                refs={**self._windmill_refs(envelope), "search_snapshot_id": snapshot_id},
                details={
                    "freshness_status": freshness_status,
                    "fresh_hours": policy.fresh_hours,
                    "stale_usable_ceiling_hours": policy.stale_usable_ceiling_hours,
                    "fail_closed_ceiling_hours": policy.fail_closed_ceiling_hours,
                    "snapshot_age_hours": snapshot_age_hours,
                    "fallback_age_hours": fallback_age_hours,
                },
            ),
        )

    def read_fetch(
        self, *, envelope: CommandEnvelope, snapshot_id: str, max_reads: int = 5
    ) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        snapshot = self.state.search_snapshots.get(snapshot_id)
        if not snapshot:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="read_fetch",
                    status="failed_terminal",
                    decision_reason="missing_snapshot",
                    retry_class="contract_violation",
                    refs=self._windmill_refs(envelope),
                ),
            )

        search_items: list[SearchResultItem] = [
            SearchResultItem(
                url=item["url"],
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
            )
            for item in snapshot["results"]
        ]
        ranked_candidates = rank_reader_candidates(
            search_items,
            query_context=str(snapshot.get("query", "")),
        )
        selected = ranked_candidates[: max(0, max_reads)]
        if not selected:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="read_fetch",
                    status="blocked",
                    decision_reason="no_candidate_urls",
                    retry_class="insufficient_evidence",
                    refs=self._windmill_refs(envelope),
                ),
            )

        raw_scrape_ids: list[str] = []
        artifact_refs: list[str] = []
        quality_alerts: list[str] = []
        reader_quality_failures: list[dict[str, Any]] = []
        reader_provider_errors: list[dict[str, Any]] = []
        candidate_audit: list[dict[str, Any]] = []

        for candidate_entry in selected:
            candidate = SearchResultItem(
                url=str(candidate_entry["url"]),
                title=str(candidate_entry["title"]),
                snippet=str(candidate_entry["snippet"]),
            )
            official_artifact_provider_error_seen = any(
                bool(item.get("candidate_is_official_artifact")) for item in reader_provider_errors
            )
            skip_reason = prefetch_skip_reason(candidate.url)
            if skip_reason:
                quality_alerts.append("reader_prefetch_skipped_low_value_portal")
                reader_quality_failures.append(
                    {
                        "url": candidate.url,
                        "rank": candidate_entry["rank"],
                        "score": candidate_entry["score"],
                        "reason": "prefetch_skipped_low_value_portal",
                        "quality_details": {"skip_signal": skip_reason},
                    }
                )
                candidate_audit.append(
                    {
                        "url": candidate.url,
                        "rank": candidate_entry["rank"],
                        "score": candidate_entry["score"],
                        "outcome": "reader_prefetch_skipped_low_value_portal",
                        "reason": skip_reason,
                    }
                )
                continue
            if (
                envelope.source_family == "meeting_minutes"
                and official_artifact_provider_error_seen
                and _is_weak_reader_fallback_candidate(candidate)
            ):
                quality_alerts.append("reader_fallback_blocked_after_official_reader_errors")
                reader_quality_failures.append(
                    {
                        "url": candidate.url,
                        "rank": candidate_entry["rank"],
                        "score": candidate_entry["score"],
                        "reason": "fallback_blocked_after_official_reader_errors",
                        "quality_details": {
                            "source_family": envelope.source_family,
                            "official_artifact_provider_error_seen": True,
                        },
                    }
                )
                candidate_audit.append(
                    {
                        "url": candidate.url,
                        "rank": candidate_entry["rank"],
                        "score": candidate_entry["score"],
                        "outcome": "reader_fallback_blocked_after_official_reader_errors",
                    }
                )
                continue
            try:
                doc = self.reader_provider.fetch(url=candidate.url)
            except Exception as exc:
                err = str(exc)
                candidate_is_official_artifact = _is_concrete_artifact_url(candidate.url)
                reader_provider_errors.append(
                    {
                        "url": candidate.url,
                        "rank": candidate_entry["rank"],
                        "score": candidate_entry["score"],
                        "error": err,
                        "candidate_is_official_artifact": candidate_is_official_artifact,
                    }
                )
                candidate_audit.append(
                    {
                        "url": candidate.url,
                        "rank": candidate_entry["rank"],
                        "score": candidate_entry["score"],
                        "outcome": "reader_provider_error",
                        "error": err,
                        "candidate_is_official_artifact": candidate_is_official_artifact,
                    }
                )
                continue

            is_substantive, quality_details = assess_reader_substance(doc.text)
            if not is_substantive:
                reason = str(quality_details["reason"])
                quality_alerts.append(f"reader_output_insufficient_substance:{reason}")
                reader_quality_failures.append(
                    {
                        "url": candidate.url,
                        "rank": candidate_entry["rank"],
                        "score": candidate_entry["score"],
                        "reason": reason,
                        "quality_details": quality_details,
                    }
                )
                candidate_audit.append(
                    {
                        "url": candidate.url,
                        "rank": candidate_entry["rank"],
                        "score": candidate_entry["score"],
                        "outcome": "reader_output_insufficient_substance",
                        "reason": reason,
                    }
                )
                continue

            canonical_key = build_v2_canonical_document_key(
                jurisdiction_id=envelope.jurisdiction_id,
                source_family=envelope.source_family,
                url=doc.url,
                metadata={"document_type": doc.document_type, "title": doc.title},
                data={"published_date": doc.published_date},
            )
            content_hash = _hash_text(doc.text)
            scrape_id = f"raw_{_hash_text(f'{canonical_key}|{content_hash}')[:16]}"
            existing = self.state.raw_scrapes.get(scrape_id)
            if existing:
                existing["seen_count"] += 1
                existing["last_seen_at"] = self.state.now.isoformat()
                raw_scrape_ids.append(scrape_id)
                artifact_refs.append(existing["artifact_ref"])
                candidate_audit.append(
                    {
                        "url": candidate.url,
                        "rank": candidate_entry["rank"],
                        "score": candidate_entry["score"],
                        "outcome": "reused_existing_raw_scrape",
                        "raw_scrape_id": scrape_id,
                    }
                )
                continue

            try:
                artifact = self.artifact_store.put(
                    contract_version=CONTRACT_VERSION,
                    jurisdiction_id=envelope.jurisdiction_id,
                    source_family=envelope.source_family,
                    artifact_kind="reader_output",
                    body=doc.text,
                    media_type=doc.media_type,
                )
            except Exception as exc:
                return self._store_result(
                    envelope,
                    CommandResponse(
                        command="read_fetch",
                        status="failed_terminal",
                        decision_reason="reader_artifact_write_failed",
                        retry_class="transient_storage",
                        alerts=[f"artifact_store_error:{exc}"],
                        refs=self._windmill_refs(envelope),
                    ),
                )

            self.state.raw_scrapes[scrape_id] = {
                "raw_scrape_id": scrape_id,
                "canonical_document_key": canonical_key,
                "content_hash": content_hash,
                "artifact_ref": artifact.artifact_ref,
                "jurisdiction_id": envelope.jurisdiction_id,
                "source_family": envelope.source_family,
                "seen_count": 1,
                "last_seen_at": self.state.now.isoformat(),
                "title": doc.title,
                "text": doc.text,
            }
            raw_scrape_ids.append(scrape_id)
            artifact_refs.append(artifact.artifact_ref)
            candidate_audit.append(
                {
                    "url": candidate.url,
                    "rank": candidate_entry["rank"],
                    "score": candidate_entry["score"],
                    "outcome": "materialized_raw_scrape",
                    "raw_scrape_id": scrape_id,
                }
            )

        if not raw_scrape_ids:
            provider_alerts = [f"reader_error:{item['error']}" for item in reader_provider_errors]
            alerts = list(dict.fromkeys(provider_alerts + quality_alerts))
            if reader_provider_errors:
                return self._store_result(
                    envelope,
                    CommandResponse(
                        command="read_fetch",
                        status="failed_retryable",
                        decision_reason="reader_provider_error",
                        retry_class="provider_unavailable",
                        alerts=alerts,
                        refs=self._windmill_refs(envelope),
                        details={
                            "candidate_audit": candidate_audit,
                            "ranked_candidates": selected,
                            "reader_provider_errors": reader_provider_errors,
                            "reader_quality_failures": reader_quality_failures,
                        },
                    ),
                )
            return self._store_result(
                envelope,
                CommandResponse(
                    command="read_fetch",
                    status="blocked",
                    decision_reason="reader_output_insufficient_substance",
                    retry_class="insufficient_evidence",
                    alerts=alerts or ["reader_output_insufficient_substance"],
                    refs=self._windmill_refs(envelope),
                    details={
                        "candidate_audit": candidate_audit,
                        "ranked_candidates": selected,
                        "reader_quality_failures": reader_quality_failures,
                    },
                ),
            )

        provider_alerts = [f"reader_error:{item['error']}" for item in reader_provider_errors]
        alerts = list(dict.fromkeys(quality_alerts + provider_alerts))
        status = "succeeded_with_alerts" if alerts else "succeeded"
        decision_reason = (
            "raw_scrapes_materialized_with_reader_alerts"
            if alerts
            else "raw_scrapes_materialized"
        )
        return self._store_result(
            envelope,
            CommandResponse(
                command="read_fetch",
                status=status,
                decision_reason=decision_reason,
                retry_class="none",
                alerts=alerts,
                counts={"raw_scrapes": len(raw_scrape_ids), "artifacts": len(artifact_refs)},
                refs={
                    **self._windmill_refs(envelope),
                    "raw_scrape_ids": raw_scrape_ids,
                    "artifact_refs": artifact_refs,
                },
                details={
                    "candidate_audit": candidate_audit,
                    "ranked_candidates": selected,
                    "reader_provider_errors": reader_provider_errors,
                    "reader_quality_failures": reader_quality_failures,
                },
            ),
        )

    def index(self, *, envelope: CommandEnvelope, raw_scrape_ids: list[str]) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        rows = [self.state.raw_scrapes.get(raw_id) for raw_id in raw_scrape_ids]
        valid_rows = [row for row in rows if row]
        if not valid_rows:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="index",
                    status="blocked",
                    decision_reason="no_raw_scrapes",
                    retry_class="insufficient_evidence",
                    refs=self._windmill_refs(envelope),
                ),
            )

        chunks: list[dict[str, Any]] = []
        for row in valid_rows:
            for idx, chunk_text in enumerate(_split_chunks(row["text"])):
                chunk_id = _stable_chunk_id(
                    canonical_document_key=row["canonical_document_key"],
                    content_hash=row["content_hash"],
                    chunk_index=idx,
                    chunk_text=chunk_text,
                )
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "raw_scrape_id": row["raw_scrape_id"],
                        "canonical_document_key": row["canonical_document_key"],
                        "artifact_ref": row["artifact_ref"],
                        "jurisdiction_id": row["jurisdiction_id"],
                        "source_family": row["source_family"],
                        "contract_version": CONTRACT_VERSION,
                        "chunk_index": idx,
                        "text": chunk_text,
                    }
                )

        try:
            upserted = self.vector_store.upsert_chunks(chunks)
        except Exception as exc:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="index",
                    status="failed_retryable",
                    decision_reason="vector_write_failed",
                    retry_class="transient_storage",
                    alerts=[f"vector_store_error:{exc}"],
                    refs=self._windmill_refs(envelope),
                ),
            )

        return self._store_result(
            envelope,
            CommandResponse(
                command="index",
                status="succeeded",
                decision_reason="chunks_indexed",
                retry_class="none",
                counts={"chunks": upserted},
                refs={**self._windmill_refs(envelope), "raw_scrape_ids": raw_scrape_ids},
            ),
        )

    def analyze(
        self,
        *,
        envelope: CommandEnvelope,
        question: str,
        jurisdiction_id: str,
        source_family: str,
    ) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        evidence = [
            chunk
            for chunk in self.state.chunks.values()
            if chunk["jurisdiction_id"] == jurisdiction_id and chunk["source_family"] == source_family
        ]
        selected_evidence, evidence_audit = rank_evidence_chunks(question=question, chunks=evidence)
        if not selected_evidence:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="analyze",
                    status="blocked",
                    decision_reason="no_evidence_chunks",
                    retry_class="insufficient_evidence",
                    refs=self._windmill_refs(envelope),
                    counts={"evidence_chunks": 0},
                ),
            )

        try:
            payload = self.analyzer.analyze(question=question, evidence_chunks=selected_evidence)
        except Exception as exc:
            return self._store_result(
                envelope,
                CommandResponse(
                    command="analyze",
                    status="failed_terminal",
                    decision_reason="analysis_failed",
                    retry_class="contract_violation",
                    alerts=[f"analysis_error:{exc}"],
                    refs=self._windmill_refs(envelope),
                ),
            )

        analysis_id = f"analysis_{_hash_text(stable_json_hash(payload))[:16]}"
        self.state.analyses[analysis_id] = {
            "analysis_id": analysis_id,
            "question": question,
            "jurisdiction_id": jurisdiction_id,
            "source_family": source_family,
            "payload": payload,
            "contract_version": CONTRACT_VERSION,
        }
        self.state.previous_success_by_scope[f"{jurisdiction_id}|{source_family}"] = self.state.now
        return self._store_result(
            envelope,
            CommandResponse(
                command="analyze",
                status="succeeded",
                decision_reason="analysis_completed",
                retry_class="none",
                counts={"analyses": 1, "evidence_chunks": len(selected_evidence)},
                refs={**self._windmill_refs(envelope), "analysis_id": analysis_id},
                details={
                    "sufficiency_state": payload.get("sufficiency_state"),
                    "evidence_selection": {
                        "candidate_chunk_count": len(evidence),
                        "selected_chunk_count": len(selected_evidence),
                        "selected_chunks": evidence_audit,
                    },
                },
            ),
        )

    def summarize_run(
        self,
        *,
        envelope: CommandEnvelope,
        command_responses: list[CommandResponse],
    ) -> CommandResponse:
        envelope.validate()
        reused = self._reuse_if_idempotent(envelope)
        if reused:
            return reused

        counts: dict[str, int] = {}
        refs: dict[str, Any] = self._windmill_refs(envelope)
        alerts: list[str] = []
        statuses: list[str] = []
        step_map: dict[str, str] = {}
        for result in command_responses:
            statuses.append(result.status)
            alerts.extend(result.alerts)
            for key, value in result.counts.items():
                counts[key] = counts.get(key, 0) + value
            step_map[result.command] = result.status
            refs.update({f"{result.command}_reason": result.decision_reason})
            refs.update({f"{result.command}_retry_class": result.retry_class})

        summary_status = "succeeded"
        if any(status == "failed_terminal" for status in statuses):
            summary_status = "failed_terminal"
        elif any(status == "failed_retryable" for status in statuses):
            summary_status = "failed_retryable"
        elif any(status == "blocked" for status in statuses):
            summary_status = "blocked"
        elif any(status == "succeeded_with_alerts" for status in statuses):
            summary_status = "succeeded_with_alerts"

        run_id = f"run_{envelope.windmill.run_id}"
        self.state.run_summaries[run_id] = {
            "run_id": run_id,
            "summary_status": summary_status,
            "step_statuses": step_map,
            "counts": counts,
            "alerts": list(dict.fromkeys(alerts)),
        }
        return self._store_result(
            envelope,
            CommandResponse(
                command="summarize_run",
                status=summary_status,
                decision_reason="run_summary_materialized",
                retry_class="none" if summary_status.startswith("succeeded") else "operator_required",
                alerts=list(dict.fromkeys(alerts)),
                counts=counts,
                refs=refs | {"run_id": run_id},
                details={"step_statuses": step_map},
            ),
        )

    def full_refresh(
        self,
        *,
        query: str,
        question: str,
        search_envelope: CommandEnvelope,
        freshness_envelope: CommandEnvelope,
        read_envelope: CommandEnvelope,
        index_envelope: CommandEnvelope,
        analyze_envelope: CommandEnvelope,
        summarize_envelope: CommandEnvelope,
        policy: FreshnessPolicy,
    ) -> list[CommandResponse]:
        search_result = self.search_materialize(envelope=search_envelope, query=query)
        snapshot_id = str(search_result.refs.get("search_snapshot_id", ""))
        latest_success = self.state.previous_success_by_scope.get(
            f"{search_envelope.jurisdiction_id}|{search_envelope.source_family}"
        )
        freshness_result = self.freshness_gate(
            envelope=freshness_envelope,
            snapshot_id=snapshot_id,
            policy=policy,
            latest_success_at=latest_success,
        )
        responses = [search_result, freshness_result]
        freshness_state = freshness_result.decision_reason

        if freshness_state in {"stale_blocked", "empty_blocked"}:
            responses.append(self.summarize_run(envelope=summarize_envelope, command_responses=responses))
            return responses

        read_result = self.read_fetch(envelope=read_envelope, snapshot_id=snapshot_id)
        responses.append(read_result)
        if read_result.status not in {"succeeded", "succeeded_with_alerts", "skipped"}:
            responses.append(self.summarize_run(envelope=summarize_envelope, command_responses=responses))
            return responses

        index_result = self.index(
            envelope=index_envelope,
            raw_scrape_ids=list(read_result.refs.get("raw_scrape_ids", [])),
        )
        responses.append(index_result)

        analyze_result = self.analyze(
            envelope=analyze_envelope,
            question=question,
            jurisdiction_id=search_envelope.jurisdiction_id,
            source_family=search_envelope.source_family,
        )
        responses.append(analyze_result)
        responses.append(self.summarize_run(envelope=summarize_envelope, command_responses=responses))
        return responses
