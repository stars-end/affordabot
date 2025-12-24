"""
SSE Chat endpoint for PolicyAgent streaming.

This router provides Server-Sent Events streaming for
the PolicyAgent to enable real-time Deep Chat UI updates.
"""

import json
import logging
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str
    jurisdiction: Optional[str] = "San Jose"
    session_id: Optional[str] = None


class ChatMessage(BaseModel):
    """Response message format."""
    type: str  # "thinking", "tool_call", "tool_result", "text", "sources", "error"
    data: dict


async def get_policy_agent():
    """Dependency to get PolicyAgent instance."""
    # Import here to avoid circular imports
    try:
        from pathlib import Path
        from llm_common.agents import ToolContextManager, ToolRegistry
        from llm_common.providers.zai_client import ZaiClient
        from agents.policy_agent import PolicyAgent
        from agents.tools.zai_search import ZaiSearchTool
        from agents.tools.scraper import ScraperTool
        from agents.tools.retriever import RetrieverTool
        
        # Initialize LLM client (using Z.ai)
        llm_client = ZaiClient()
        
        # Initialize tool registry
        registry = ToolRegistry()
        registry.register(ZaiSearchTool(llm_client))
        registry.register(ScraperTool())
        registry.register(RetrieverTool())
        
        # Initialize context manager
        context_dir = Path("/tmp/affordabot_context")
        context_manager = ToolContextManager(context_dir)
        
        return PolicyAgent(
            llm_client=llm_client,
            tool_registry=registry,
            context_manager=context_manager,
        )
    except Exception as e:
        logger.error(f"Failed to initialize PolicyAgent: {e}")
        raise HTTPException(status_code=500, detail=f"Agent initialization failed: {e}")


async def stream_events(agent, message: str, jurisdiction: str) -> AsyncGenerator[str, None]:
    """
    Generator that yields SSE-formatted events from PolicyAgent.
    """
    try:
        async for event in agent.analyze_stream(message, jurisdiction):
            # Format as SSE event
            event_data = {
                "type": event.type,
                "data": event.data,
            }
            if event.task_id:
                event_data["task_id"] = event.task_id
            if event.tool_name:
                event_data["tool_name"] = event.tool_name
            
            yield f"data: {json.dumps(event_data)}\n\n"
        
        # Send done event
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
    except Exception as e:
        logger.error(f"Stream error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"


@router.post("/chat")
async def chat_stream(
    request: ChatRequest,
    agent: PolicyAgent = Depends(get_policy_agent),
):
    """
    Stream policy analysis response via SSE.
    
    Request body:
    - message: The policy question to analyze
    - jurisdiction: Target jurisdiction (default: San Jose)
    - session_id: Optional session for context continuity
    
    Response: Server-Sent Events stream with event types:
    - thinking: Agent reasoning
    - tool_call: Tool invocation
    - tool_result: Tool output
    - text: Answer text
    - sources: Citation URLs
    - done: Stream complete
    - error: Error occurred
    """
    logger.info(f"Chat request: {request.message[:50]}...")
    
    return StreamingResponse(
        stream_events(agent, request.message, request.jurisdiction),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/chat/health")
async def chat_health():
    """Health check for chat endpoint."""
    return {"status": "healthy", "endpoint": "/api/chat"}
