from fastapi import APIRouter, Depends, HTTPException
from typing import List
from services.glass_box import GlassBoxService, AgentStep

router = APIRouter(prefix="/admin", tags=["admin"])

def get_glass_box_service():
    # In a real app, this path might come from config
    return GlassBoxService(trace_dir=".traces")

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
