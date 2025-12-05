"""API Router for Auto-Discovery."""

from fastapi import APIRouter, Depends
from typing import List
from pydantic import BaseModel
from services.auto_discovery_service import AutoDiscoveryService
from llm_common import WebSearchClient
from supabase import create_client
import os

router = APIRouter(prefix="/discovery", tags=["discovery"])

class DiscoveryRequest(BaseModel):
    jurisdiction_name: str
    jurisdiction_type: str = "city"

def get_web_search_client() -> WebSearchClient:
    # Assuming WebSearchClient takes api_key and supabase_client
    # We need ZAI_API_KEY env var
    supabase = create_client(
        os.environ['SUPABASE_URL'],
        os.environ['SUPABASE_SERVICE_ROLE_KEY']
    )
    return WebSearchClient(
        api_key=os.environ.get('ZAI_API_KEY', 'mock-key'), # Fallback for dev if not set
        supabase_client=supabase
    )

def get_discovery_service(search_client: WebSearchClient = Depends(get_web_search_client)) -> AutoDiscoveryService:
    return AutoDiscoveryService(search_client)

@router.post("/run", response_model=List[dict])
async def run_discovery(
    request: DiscoveryRequest,
    service: AutoDiscoveryService = Depends(get_discovery_service)
):
    return await service.discover_sources(request.jurisdiction_name, request.jurisdiction_type)
