"""Shared contract constants for Windmill/domain boundary commands."""

from __future__ import annotations

from typing import Literal

CONTRACT_VERSION = "2026-04-13.windmill-domain.v1"

CommandName = Literal[
    "search_materialize",
    "freshness_gate",
    "read_fetch",
    "index",
    "analyze",
    "summarize_run",
]

StatusName = Literal[
    "succeeded",
    "succeeded_with_alerts",
    "skipped",
    "blocked",
    "failed_retryable",
    "failed_terminal",
]

RetryClass = Literal[
    "none",
    "transport",
    "rate_limited",
    "transient_storage",
    "provider_unavailable",
    "contract_violation",
    "insufficient_evidence",
    "operator_required",
]
