from fastapi import APIRouter, Depends, Request
from typing import List
from services.glass_box import GlassBoxService, AgentStep, PipelineStep

router = APIRouter(prefix="/admin", tags=["admin"])

def get_glass_box_service(request: Request):
    # Retrieve DB from app state if initialized in main.py
    db = getattr(request.app.state, "db", None)
    return GlassBoxService(db_client=db, trace_dir=".traces")

@router.get("/traces/{query_id}", response_model=List[AgentStep])
async def get_agent_traces(
    query_id: str,
    service: GlassBoxService = Depends(get_glass_box_service)
):
    """Get full execution trace for a specific agent session."""
    return await service.get_traces_for_query(query_id)

@router.get("/traces", response_model=List[str])
async def list_agent_sessions(
    service: GlassBoxService = Depends(get_glass_box_service)
):
    """List all recorded agent sessions."""
    return await service.list_queries()

@router.get("/runs/{run_id}/steps", response_model=List[PipelineStep])
async def get_run_steps(
    run_id: str,
    service: GlassBoxService = Depends(get_glass_box_service)
):
    """
    Get granular execution steps for a pipeline run.
    """
    return await service.get_pipeline_steps(run_id)
