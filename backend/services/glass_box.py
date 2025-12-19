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

    async def get_pipeline_steps(self, run_id: str) -> List[PipelineStep]:
        """
        Retrieve granular pipeline steps from the pipeline_steps table.
        """
        if not self.db:
            return []
            
        try:
            query = """
                SELECT * FROM pipeline_steps 
                WHERE run_id = (
                    SELECT id FROM pipeline_runs 
                    WHERE bill_id = $1 OR id::text = $1 
                    ORDER BY started_at DESC LIMIT 1
                )
                ORDER BY step_number ASC
            """
            rows = await self.db._fetch(query, run_id)
            
            steps = []
            for r in rows:
                steps.append(PipelineStep(
                    id=str(r['id']),
                    run_id=str(r['run_id']),
                    step_number=r['step_number'],
                    step_name=r['step_name'],
                    status=r['status'],
                    input_context=json.loads(r['input_context']) if isinstance(r['input_context'], str) else r['input_context'],
                    output_result=json.loads(r['output_result']) if isinstance(r['output_result'], str) else r['output_result'],
                    model_info=json.loads(r['model_config']) if isinstance(r['model_config'], str) else r['model_config'],
                    duration_ms=r['duration_ms'],
                    created_at=r['created_at']
                ))
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
                # We search by bill_id (which is used as query_id in UI)
                query = "SELECT * FROM pipeline_runs WHERE bill_id = $1 OR id::text = $1 ORDER BY started_at DESC LIMIT 1"
                run = await self.db._fetchrow(query, query_id)
                
                if run and run['result']:
                    data = json.loads(run['result']) if isinstance(run['result'], str) else run['result']
                    # Map pipeline steps (research, generate, review) to AgentStep
                    
                    # Note: Using started_at as base timestamp
                    base_ts = int(run['started_at'].timestamp()) if run['started_at'] else 0
                    
                    # 1. Research
                    if 'research' in data:
                        steps.append(AgentStep(
                            tool="ResearchAgent",
                            args={"bill_id": run['bill_id']},
                            result=data['research'],
                            task_id="research",
                            query_id=query_id,
                            timestamp=base_ts + 1
                        ))
                    
                    # 2. Analysis/Generate
                    if 'analysis' in data: # mapped from 'generate' step
                        steps.append(AgentStep(
                            tool="LegislationAnalyzer",
                            args={"model": run['models']},
                            result=data['analysis'],
                            task_id="generate",
                            query_id=query_id,
                            timestamp=base_ts + 2
                        ))
                        
                    # 3. Review
                    if 'review' in data:
                        steps.append(AgentStep(
                            tool="PolicyReviewer",
                            args={},
                            result=data['review'],
                            task_id="review",
                            query_id=query_id,
                            timestamp=base_ts + 3
                        ))
                
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
                rows = await self.db._fetch("SELECT DISTINCT bill_id FROM pipeline_runs ORDER BY bill_id")
                for r in rows:
                    queries.add(r['bill_id'])
            except Exception as e:
                logger.error(f"Error listing DB queries: {e}")
                
        # 2. File Queries
        if self.trace_dir.exists():
            for p in self.trace_dir.iterdir():
                if p.is_dir():
                    queries.add(p.name)
                    
        return sorted(list(queries))
