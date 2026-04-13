"""Typed request/response models for pipeline domain commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.pipeline.domain.constants import CONTRACT_VERSION, CommandName, RetryClass, StatusName


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class WindmillMetadata:
    run_id: str
    job_id: str
    workspace: str = "affordabot"
    flow_path: str = "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"


@dataclass(frozen=True)
class CommandEnvelope:
    command: CommandName
    jurisdiction_id: str
    source_family: str
    idempotency_key: str
    windmill: WindmillMetadata
    contract_version: str = CONTRACT_VERSION

    def validate(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(
                f"contract_version mismatch: expected {CONTRACT_VERSION}, got {self.contract_version}"
            )
        if not self.jurisdiction_id.strip():
            raise ValueError("jurisdiction_id is required")
        if not self.source_family.strip():
            raise ValueError("source_family is required")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key is required")


@dataclass
class CommandResponse:
    command: CommandName
    status: StatusName
    decision_reason: str
    retry_class: RetryClass
    alerts: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    refs: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "command": self.command,
            "status": self.status,
            "decision_reason": self.decision_reason,
            "retry_class": self.retry_class,
            "alerts": self.alerts,
            "counts": self.counts,
            "refs": self.refs,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class FreshnessPolicy:
    fresh_hours: int
    stale_usable_ceiling_hours: int
    fail_closed_ceiling_hours: int

