"""
Deterministic alerting service (bd-tytc.8).

Consumes canonical truth fields from /api/admin and pipeline_runs
to produce alerts without creating a second truth store.

Alert rules evaluate against normalized fields:
- source_text_present
- retriever_invoked
- rag_chunks_retrieved
- quantification_eligible
- insufficiency_reason
- run status/duration
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    name: str
    severity: str
    description: str
    evaluate: callable


@dataclass
class Alert:
    rule: str
    severity: str
    message: str
    jurisdiction: Optional[str] = None
    bill_id: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None


class AlertingService:
    """
    Deterministic alerting over canonical truth fields.
    Does NOT create or read a second truth store.
    """

    RULES: List[AlertRule] = []

    def __init__(self, db_client: Any = None):
        self.db = db_client
        self._build_rules()

    def _build_rules(self):
        self.RULES = [
            AlertRule(
                name="pipeline_failure",
                severity="high",
                description="Pipeline run failed",
                evaluate=self._check_failure,
            ),
            AlertRule(
                name="zero_rag_chunks",
                severity="medium",
                description="Retrieval expected but zero chunks retrieved",
                evaluate=self._check_zero_rag,
            ),
            AlertRule(
                name="quantification_not_eligible_with_output",
                severity="medium",
                description="Quantification ineligible but output emitted",
                evaluate=self._check_unquantified_output,
            ),
            AlertRule(
                name="missing_source_text",
                severity="high",
                description="No source text present for bill",
                evaluate=self._check_missing_source_text,
            ),
            AlertRule(
                name="stale_scrape",
                severity="low",
                description="Last scrape for jurisdiction is old",
                evaluate=self._check_stale_scrape,
            ),
        ]

    @staticmethod
    def _check_failure(run: Dict) -> Optional[str]:
        if run.get("status") == "failed":
            return run.get("error", "Unknown failure")
        return None

    @staticmethod
    def _check_zero_rag(run: Dict) -> Optional[str]:
        result = run.get("result", {})
        if (
            result.get("retriever_invoked")
            and result.get("rag_chunks_retrieved", 0) == 0
        ):
            return "Retriever was invoked but returned zero chunks"
        return None

    @staticmethod
    def _check_unquantified_output(run: Dict) -> Optional[str]:
        result = run.get("result", {})
        analysis = result.get("analysis", {})
        if (
            result.get("quantification_eligible") is False
            and analysis.get("total_impact_p50") is not None
            and analysis.get("total_impact_p50", 0) != 0
        ):
            return "Quantification marked ineligible but p50 is non-null"
        return None

    @staticmethod
    def _check_missing_source_text(run: Dict) -> Optional[str]:
        if not run.get("result", {}).get("source_text_present"):
            return "No source text present for bill"
        return None

    @staticmethod
    def _check_stale_scrape(run: Dict) -> Optional[str]:
        return None

    _STALE_SCRAPE_TODO = (
        "stale_scrape rule requires jurisdiction-level last_scrape timestamp "
        "not available in pipeline_runs. Will need a JOIN to raw_scrapes "
        "or a dedicated jurisdiction_health table."
    )

    def evaluate_run(self, run: Dict) -> List[Alert]:
        alerts = []
        for rule in self.RULES:
            reason = rule.evaluate(run)
            if reason:
                alerts.append(
                    Alert(
                        rule=rule.name,
                        severity=rule.severity,
                        message=f"{rule.description}: {reason}",
                        jurisdiction=run.get("jurisdiction"),
                        bill_id=run.get("bill_id"),
                        run_id=run.get("id"),
                        created_at=run.get("started_at"),
                    )
                )
        return alerts

    async def evaluate_recent_runs(self, limit: int = 50) -> List[Alert]:
        """Evaluate alert rules against recent pipeline runs from DB."""
        if not self.db:
            return []
        try:
            query = """
                SELECT id, bill_id, jurisdiction, status, started_at, completed_at, error, result, models
                FROM pipeline_runs
                WHERE status IN ('completed', 'failed')
                ORDER BY started_at DESC
                LIMIT $1
            """
            rows = await self.db._fetch(query, limit)
            all_alerts = []
            for r in rows:
                result = (
                    json.loads(r["result"])
                    if isinstance(r["result"], str)
                    else (r["result"] or {})
                )
                run_data = {
                    "id": str(r["id"]),
                    "bill_id": r["bill_id"],
                    "jurisdiction": r["jurisdiction"],
                    "status": r["status"],
                    "started_at": str(r["started_at"]) if r["started_at"] else None,
                    "completed_at": str(r["completed_at"])
                    if r["completed_at"]
                    else None,
                    "error": r.get("error"),
                    "result": result,
                }
                all_alerts.extend(self.evaluate_run(run_data))
            return all_alerts
        except Exception as e:
            logger.error(f"Error evaluating recent runs: {e}")
            return []
