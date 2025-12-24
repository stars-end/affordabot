"""API Router for Sources."""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from services.source_service import SourceService, SourceCreate, SourceUpdate
from db.postgres_client import PostgresDB

router = APIRouter(prefix="/sources", tags=["sources"])

# Simple dependency for DB connection
def get_db() -> PostgresDB:
    return PostgresDB()

def get_source_service(db: PostgresDB = Depends(get_db)) -> SourceService:
    return SourceService(db)

@router.get("/", response_model=List[dict])
async def list_sources(
    jurisdiction_id: Optional[str] = None,
    service: SourceService = Depends(get_source_service)
):
    return await service.get_sources(jurisdiction_id)

@router.post("/", response_model=dict)
async def create_source(
    source: SourceCreate,
    service: SourceService = Depends(get_source_service)
):
    return await service.create_source(source)

@router.get("/{source_id}", response_model=dict)
async def get_source(
    source_id: str,
    service: SourceService = Depends(get_source_service)
):
    source = await service.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source

@router.patch("/{source_id}", response_model=dict)
async def update_source(
    source_id: str,
    source: SourceUpdate,
    service: SourceService = Depends(get_source_service)
):
    return await service.update_source(source_id, source)

@router.delete("/{source_id}")
async def delete_source(
    source_id: str,
    service: SourceService = Depends(get_source_service)
):
    await service.delete_source(source_id)
    return {"status": "success"}
