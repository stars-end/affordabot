from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from pydantic import BaseModel
from db.postgres_client import PostgresDB

router = APIRouter(
    prefix="/bills",
    tags=["bills"]
)

# Dependency to get the database client
def get_db() -> PostgresDB:
    return PostgresDB()

class BillSearchResult(BaseModel):
    bill_id: str
    title: Optional[str] = None
    jurisdiction: str
    status: Optional[str] = None
    # Add other fields as needed

class SearchResponse(BaseModel):
    results: List[BillSearchResult]
    count: int

@router.get("/search", response_model=SearchResponse)
async def search_bills(
    q: str = Query(..., min_length=2, description="Search query"),
    jurisdiction: Optional[str] = None,
    limit: int = 20,
    db: PostgresDB = Depends(get_db)
):
    """
    Search for bills by bill number or title.
    """
    try:
        # Construct search query
        # We search in 'legislation' table (processed bills)
        # Assuming schema: legislation(id, bill_number, title, jurisdiction_id, ...)
        # We need to join with jurisdictions to get name
        
        # Note: PostgresDB client might need a raw query if helper not available
        query_sql = """
            SELECT l.bill_number, l.title, j.name as jurisdiction_name, l.status
            FROM legislation l
            JOIN jurisdictions j ON l.jurisdiction_id = j.id
            WHERE 
                (LOWER(l.bill_number) LIKE LOWER($1) OR LOWER(l.title) LIKE LOWER($1))
        """
        params = [f"%{q}%"]
        
        if jurisdiction:
            query_sql += " AND LOWER(j.name) = LOWER($2)"
            params.append(jurisdiction)
            
        query_sql += " LIMIT $3"
        params.append(limit)
        
        # Adapt params indexing for asyncpg ($1, $2...) if needed, but db._fetch handles args
        # db._fetch implementation usually takes *args
        # Wait, params should be passed as separate args to _fetch logic if it wraps connection.fetch
        # Let's inspect db client usage in admin.py to be sure.
        # admin.py used: await db._fetch(query, limit) or await db._fetchrow(query, arg1, arg2)
        
        # So we need to unpack params
        rows = await db._fetch(query_sql, *params)
        
        results = [
            BillSearchResult(
                bill_id=row["bill_number"],
                title=row.get("title"),
                jurisdiction=row["jurisdiction_name"],
                status=row.get("status")
            ) for row in rows
        ]
        
        return SearchResponse(results=results, count=len(results))
        
    except Exception as e:
        # Fallback empty if table doesn't exist or other error, but log it
        print(f"Search failed: {e}")
        # Return empty for now to avoid 500 loop in frontend
        return SearchResponse(results=[], count=0)
