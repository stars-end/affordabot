from typing import Any, List, Optional, Dict
from pydantic import BaseModel, Field

class ToolResult(BaseModel):
    """
    Standardized envelope for tool execution results.
    Follows Dexter pattern for consistent LLM consumption.
    """
    success: bool = Field(..., description="Whether the tool execution succeeded")
    content: str = Field(..., description="Main textual output/result")
    artifacts: List[Dict[str, Any]] = Field(default_factory=list, description="Structured data or file references")
    error_message: Optional[str] = Field(None, description="Error details if success is False")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution metadata (duration, cost, etc)")

    @classmethod
    def ok(cls, content: str, artifacts: List[Dict] = None, **kwargs):
        return cls(success=True, content=content, artifacts=artifacts or [], metadata=kwargs)

    @classmethod
    def fail(cls, error: str, **kwargs):
        return cls(success=False, content="", error_message=error, metadata=kwargs)
