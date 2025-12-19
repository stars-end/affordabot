"""Service for managing sources."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from db.postgres_client import PostgresDB

class SourceCreate(BaseModel):
    jurisdiction_id: str
    url: str
    type: str # 'meeting', 'legislation', etc.
    source_method: str = "scrape"
    handler: Optional[str] = None

class SourceUpdate(BaseModel):
    url: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    source_method: Optional[str] = None
    handler: Optional[str] = None

class SourceService:
    def __init__(self, db: PostgresDB):
        self.db = db

    async def get_sources(self, jurisdiction_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List sources, optionally filtered by jurisdiction."""
        return await self.db.get_sources(jurisdiction_id)

    async def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Get a single source by ID."""
        return await self.db.get_source(source_id)

    async def create_source(self, source: SourceCreate) -> Dict[str, Any]:
        """Create a new source."""
        data = source.model_dump(exclude_none=True)
        return await self.db.create_source(data)

    async def update_source(self, source_id: str, source: SourceUpdate) -> Dict[str, Any]:
        """Update an existing source."""
        data = source.model_dump(exclude_none=True)
        if not data:
            return await self.get_source(source_id)
        return await self.db.update_source(source_id, data)

    async def delete_source(self, source_id: str) -> None:
        """Delete a source."""
        await self.db.delete_source(source_id)
