"""API Router for Auto-Discovery."""

from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from pydantic import BaseModel
from services.auto_discovery_service import AutoDiscoveryService
from llm_common import WebSearchClient
import os

router = APIRouter(prefix="/discovery", tags=["discovery"])


class DiscoveryRequest(BaseModel):
    jurisdiction_name: str
    jurisdiction_type: str = "city"


def get_web_search_client() -> WebSearchClient:
    return WebSearchClient(
        api_key=os.environ.get("ZAI_API_KEY", "mock-key"),
    )


def get_discovery_service(
    search_client: WebSearchClient = Depends(get_web_search_client),
) -> AutoDiscoveryService:
    return AutoDiscoveryService(search_client)


@router.post("/run", response_model=List[Dict[str, Any]])
async def run_discovery(
    request: DiscoveryRequest,
    service: AutoDiscoveryService = Depends(get_discovery_service),
):
    """
    Run auto-discovery for a given jurisdiction to find potential sources.
    """
    return await service.discover_sources(
        request.jurisdiction_name, request.jurisdiction_type
    )
