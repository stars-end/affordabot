from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Dict, Any
from uuid import UUID
import json

class RawScrape(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra='allow')
    
    id: UUID | str
    source_id: UUID | str
    url: str
    data: Dict[str, Any] | str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    content_type: str = "text/html"
    processed: Optional[bool] = False
    document_id: Optional[UUID | str] = None
    storage_uri: Optional[str] = None
    content_hash: Optional[str] = None

    @field_validator('data', 'metadata', mode='before')
    @classmethod
    def parse_json_strings(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v
