"""Service for managing sources."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from supabase import Client
from pydantic import BaseModel

class SourceCreate(BaseModel):
    jurisdiction_id: str
    url: str
    type: str
    source_method: str = "scrape"
    handler: Optional[str] = None

class SourceUpdate(BaseModel):
    url: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    source_method: Optional[str] = None
    handler: Optional[str] = None

class SourceService:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.table = "sources"

    async def get_sources(self, jurisdiction_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List sources, optionally filtered by jurisdiction."""
        query = self.supabase.table(self.table).select("*")
        if jurisdiction_id:
            query = query.eq("jurisdiction_id", jurisdiction_id)
        
        result = query.execute()
        return result.data

    async def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Get a single source by ID."""
        result = self.supabase.table(self.table).select("*").eq("id", source_id).single().execute()
        return result.data

    async def create_source(self, source: SourceCreate) -> Dict[str, Any]:
        """Create a new source."""
        data = source.dict(exclude_none=True)
        # Ensure ID is generated if not provided (though Supabase usually handles it, explicit is safe)
        # Actually, let Supabase/Postgres handle UUID generation if default is set, 
        # or generate here. The schema has default gen_random_uuid().
        
        result = self.supabase.table(self.table).insert(data).execute()
        return result.data[0]

    async def update_source(self, source_id: str, source: SourceUpdate) -> Dict[str, Any]:
        """Update an existing source."""
        data = source.dict(exclude_none=True)
        if not data:
            return await self.get_source(source_id)
            
        result = self.supabase.table(self.table).update(data).eq("id", source_id).execute()
        return result.data[0]

    async def delete_source(self, source_id: str) -> None:
        """Delete a source."""
        self.supabase.table(self.table).delete().eq("id", source_id).execute()
