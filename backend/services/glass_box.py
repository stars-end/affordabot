import logging
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AgentStep(BaseModel):
    tool: str
    args: Dict[str, Any]
    result: Any
    task_id: str
    query_id: str
    timestamp: int


class PipelineStep(BaseModel):
    id: str
    run_id: str
    step_number: int
    step_name: str
    status: str
    input_context: Optional[Dict[str, Any]] = None
    output_result: Optional[Dict[str, Any]] = None
    model_info: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    created_at: Any = None


class GlassBoxService:
    """
    Service to retrieve agent execution traces ('Glass Box' observability).
    Supports both file-based traces (legacy) and DB-backed traces (pipeline_runs).
    """

    def __init__(self, db_client: Any = None, trace_dir: str = ".traces"):
        self.db = db_client
        self.trace_dir = Path(trace_dir)

    @staticmethod
    def _json_or_value(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

    @staticmethod
    def _serialize_run_head(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "bill_id": row.get("bill_id"),
            "jurisdiction": row.get("jurisdiction"),
            "status": row.get("status"),
            "started_at": str(row["started_at"]) if row.get("started_at") else None,
            "completed_at": str(row["completed_at"]) if row.get("completed_at") else None,
            "error": row.get("error"),
            "trigger_source": row.get("trigger_source", "manual"),
        }

    async def get_pipeline_run_heads(self, query_key: str) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Resolve canonical run heads for a bill/jurisdiction/run key:
        - latest_run (most recent by started_at)
        - latest_completed_run
        - latest_failed_run
        - exact_run (if query_key is a run id)
        """
        if not self.db:
            return {
                "latest_run": None,
                "latest_completed_run": None,
                "latest_failed_run": None,
                "exact_run": None,
            }

        query = """
            SELECT id, bill_id, jurisdiction, status, started_at, completed_at, error, trigger_source
            FROM pipeline_runs
            WHERE bill_id = $1 OR id::text = $1 OR jurisdiction = $1
            ORDER BY started_at DESC
            LIMIT 100
        """
        rows = await self.db._fetch(query, query_key)

        latest_run = rows[0] if rows else None
        latest_completed_run = next(
            (r for r in rows if r.get("status") == "completed"), None
        )
        latest_failed_run = next((r for r in rows if r.get("status") == "failed"), None)
        exact_run = next((r for r in rows if str(r.get("id")) == query_key), None)

        return {
            "latest_run": self._serialize_run_head(latest_run),
            "latest_completed_run": self._serialize_run_head(latest_completed_run),
            "latest_failed_run": self._serialize_run_head(latest_failed_run),
            "exact_run": self._serialize_run_head(exact_run),
        }

    async def get_pipeline_steps(self, run_id: str) -> List[PipelineStep]:
        """
        Retrieve granular pipeline steps from the pipeline_steps table.
        """
        if not self.db:
            return []

        try:
            heads = await self.get_pipeline_run_heads(run_id)
            target_run = (
                heads.get("exact_run")
                or heads.get("latest_completed_run")
                or heads.get("latest_run")
            )
            if not target_run:
                return []

            query = """
                SELECT *
                FROM pipeline_steps
                WHERE run_id = $1
                ORDER BY step_number ASC
            """
            rows = await self.db._fetch(query, target_run["id"])

            steps = []
            for r in rows:
                steps.append(
                    PipelineStep(
                        id=str(r["id"]),
                        run_id=str(r["run_id"]),
                        step_number=r["step_number"],
                        step_name=r["step_name"],
                        status=r["status"],
                        input_context=self._json_or_value(r["input_context"]),
                        output_result=self._json_or_value(r["output_result"]),
                        model_info=self._json_or_value(r["model_config"]),
                        duration_ms=r["duration_ms"],
                        created_at=r["created_at"],
                    )
                )
            return steps
        except Exception as e:
            logger.error(f"Error fetching pipeline steps for {run_id}: {e}")
            return []

    async def get_traces_for_query(self, query_id: str) -> List[AgentStep]:
        """
        Retrieve all steps for a specific query execution (bill_id or run_id).
        """
        steps = []

        # 1. Try DB first (pipeline_runs)
        if self.db:
            try:
                heads = await self.get_pipeline_run_heads(query_id)
                target_run = (
                    heads.get("exact_run")
                    or heads.get("latest_completed_run")
                    or heads.get("latest_run")
                )
                run = None
                if target_run:
                    run = await self.db._fetchrow(
                        "SELECT * FROM pipeline_runs WHERE id::text = $1",
                        target_run["id"],
                    )

                if run and run["result"]:
                    data = self._json_or_value(run["result"])
                    # Map pipeline steps (research, generate, review) to AgentStep

                    # Note: Using started_at as base timestamp
                    base_ts = (
                        int(run["started_at"].timestamp()) if run["started_at"] else 0
                    )

                    # 1. Research
                    if "research" in data:
                        steps.append(
                            AgentStep(
                                tool="ResearchAgent",
                                args={"bill_id": run["bill_id"]},
                                result=data["research"],
                                task_id="research",
                                query_id=query_id,
                                timestamp=base_ts + 1,
                            )
                        )

                    # 2. Analysis/Generate
                    if "analysis" in data:  # mapped from 'generate' step
                        steps.append(
                            AgentStep(
                                tool="LegislationAnalyzer",
                                args={"model": run["models"]},
                                result=data["analysis"],
                                task_id="generate",
                                query_id=query_id,
                                timestamp=base_ts + 2,
                            )
                        )

                    # 3. Review
                    if "review" in data:
                        steps.append(
                            AgentStep(
                                tool="PolicyReviewer",
                                args={},
                                result=data["review"],
                                task_id="review",
                                query_id=query_id,
                                timestamp=base_ts + 3,
                            )
                        )

                if steps:
                    return steps
            except Exception as e:
                logger.error(f"Error reading DB traces for {query_id}: {e}")

        # 2. Fallback to Files (Legacy)
        query_path = self.trace_dir / query_id
        if not query_path.exists():
            return steps

        try:
            files = sorted(query_path.glob("*.json"))
            for f in files:
                try:
                    with open(f, "r") as fd:
                        file_data = json.load(fd)
                        steps.append(AgentStep(**file_data))
                except Exception as e:
                    logger.warning(f"Failed to parse trace {f}: {e}")

            steps.sort(key=lambda x: x.timestamp)
            return steps

        except Exception as e:
            logger.error(f"Error reading file traces for {query_id}: {e}")
            return steps

    async def list_queries(self) -> List[str]:
        """List all available query IDs (bill_ids from DB + local folders)."""
        queries = set()

        # 1. DB Queries
        if self.db:
            try:
                rows = await self.db._fetch(
                    "SELECT DISTINCT bill_id FROM pipeline_runs ORDER BY bill_id"
                )
                for r in rows:
                    queries.add(r["bill_id"])
            except Exception as e:
                logger.error(f"Error listing DB queries: {e}")

        # 2. File Queries
        if self.trace_dir.exists():
            for p in self.trace_dir.iterdir():
                if p.is_dir():
                    queries.add(p.name)

        return sorted(list(queries))

    async def list_pipeline_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent pipeline runs."""
        if not self.db:
            return []

        try:
            query = """
                SELECT id, bill_id, jurisdiction, status, started_at, completed_at, error,
                       trigger_source
                FROM pipeline_runs 
                ORDER BY started_at DESC 
                LIMIT $1
            """
            rows = await self.db._fetch(query, limit)

            heads_by_key: Dict[Any, Dict[str, Optional[str]]] = {}
            for r in rows:
                key = (r.get("bill_id"), r.get("jurisdiction"))
                if key not in heads_by_key:
                    heads_by_key[key] = {
                        "latest_run_id": None,
                        "latest_completed_run_id": None,
                        "latest_failed_run_id": None,
                    }
                heads = heads_by_key[key]
                run_id = str(r["id"])
                if heads["latest_run_id"] is None:
                    heads["latest_run_id"] = run_id
                if r.get("status") == "completed" and heads["latest_completed_run_id"] is None:
                    heads["latest_completed_run_id"] = run_id
                if r.get("status") == "failed" and heads["latest_failed_run_id"] is None:
                    heads["latest_failed_run_id"] = run_id

            runs: List[Dict[str, Any]] = []
            for r in rows:
                run_id = str(r["id"])
                key = (r.get("bill_id"), r.get("jurisdiction"))
                heads = heads_by_key[key]
                runs.append(
                    {
                        "id": run_id,
                        "bill_id": r["bill_id"],
                        "jurisdiction": r["jurisdiction"],
                        "status": r["status"],
                        "started_at": str(r["started_at"]) if r["started_at"] else None,
                        "completed_at": str(r["completed_at"])
                        if r["completed_at"]
                        else None,
                        "error": r["error"],
                        "trigger_source": r.get("trigger_source", "manual"),
                        "is_latest_run": run_id == heads["latest_run_id"],
                        "is_latest_completed_run": run_id
                        == heads["latest_completed_run_id"],
                        "is_latest_failed_run": run_id == heads["latest_failed_run_id"],
                    }
                )
            return runs
        except Exception as e:
            logger.error(f"Error listing pipeline runs: {e}")
            return []

    async def get_pipeline_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific pipeline run with truth fields."""
        if not self.db:
            return None

        try:
            query = """
                SELECT id, bill_id, jurisdiction, status, started_at, completed_at, error, models, result,
                       trigger_source
                FROM pipeline_runs 
                WHERE id::text = $1
            """
            r = await self.db._fetchrow(query, run_id)
            if not r:
                return None

            result = (
                json.loads(r["result"])
                if isinstance(r["result"], str)
                else r["result"] or {}
            )
            analysis = result.get("analysis", {})

            return {
                "id": str(r["id"]),
                "bill_id": r["bill_id"],
                "jurisdiction": r["jurisdiction"],
                "status": r["status"],
                "started_at": str(r["started_at"]) if r["started_at"] else None,
                "completed_at": str(r["completed_at"]) if r["completed_at"] else None,
                "error": r["error"],
                "models": json.loads(r["models"])
                if isinstance(r["models"], str)
                else r["models"],
                "result": result,
                "sufficiency_breakdown": result.get("sufficiency_breakdown"),
                "source_text_present": result.get("source_text_present"),
                "retriever_invoked": result.get("retriever_invoked"),
                "rag_chunks_retrieved": result.get("rag_chunks_retrieved", 0),
                "validated_evidence_count": result.get("validated_evidence_count", 0),
                "quantification_eligible": result.get("quantification_eligible"),
                "insufficiency_reason": result.get("insufficiency_reason"),
                "model_used": result.get("model_used"),
                "analysis_sufficiency_state": analysis.get("sufficiency_state"),
                "analysis_quantification_eligible": analysis.get(
                    "quantification_eligible"
                ),
                "trigger_source": r.get("trigger_source", "manual"),
            }
        except Exception as e:
            logger.error(f"Error getting pipeline run {run_id}: {e}")
            return None
