from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from uuid import UUID
import json

class RawScrape(BaseModel):
    id: str
    source_id: UUID
    url: str
    data: Dict[str, Any] | str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    content_type: str = "text/html"
    processed: bool = False
    document_id: Optional[UUID] = None
    storage_uri: Optional[str] = None
    content_hash: Optional[str] = None

    @field_validator('data', 'metadata', mode='before')
    def parse_json_strings(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # Let it fail validation downstream if it's not a dict after failing to parse
                return v
        return v
    
    class Config:
        extra = 'allow' # Allow other fields from the DB
        # Pydantic v2 should handle UUID from str automatically, but being explicit can help
        # with some database drivers. If UUIDs from strings are not parsing, add:
        # from_attributes = True 
