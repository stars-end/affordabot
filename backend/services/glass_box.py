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

class GlassBoxService:
    """
    Service to retrieve agent execution traces ('Glass Box' observability).
    Reads the JSON artifacts produced by ToolContextManager.
    """
    def __init__(self, trace_dir: str = ".traces"):
        self.trace_dir = Path(trace_dir)

    async def get_traces_for_query(self, query_id: str) -> List[AgentStep]:
        """
        Retrieve all steps for a specific query execution.
        """
        query_path = self.trace_dir / query_id
        if not query_path.exists():
            return []

        steps = []
        try:
            # Glob all JSONs and sort by timestamp
            files = sorted(query_path.glob("*.json"))
            for f in files:
                try:
                    with open(f, "r") as fd:
                        data = json.load(fd)
                        steps.append(AgentStep(**data))
                except Exception as e:
                    logger.warning(f"Failed to parse trace {f}: {e}")
            
            # Sort by timestamp just in case glob isn't perfect time-order
            steps.sort(key=lambda x: x.timestamp)
            return steps
            
        except Exception as e:
            logger.error(f"Error reading traces for {query_id}: {e}")
            return []

    async def list_queries(self) -> List[str]:
        """List all available query IDs."""
        if not self.trace_dir.exists():
            return []
        return [p.name for p in self.trace_dir.iterdir() if p.is_dir()]
