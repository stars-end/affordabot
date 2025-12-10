import os
import logging
import json
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger("postgres_db")

class PostgresDB:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        # Handle transaction pooler url compatibility if needed (asyncpg usually needs strict formatting)
        # But generic postgres:// should work.
        if not self.database_url:
            logger.warning("DATABASE_URL not set. Database operations will fail.")
        
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Explicitly connect/create pool. Helpers will auto-connect if needed."""
        if not self.pool and self.database_url:
            try:
                # Railway internal network doesn't support SSL upgrade
                # Only use SSL for external connections (Supabase pooler, etc.)
                use_ssl = 'railway.internal' not in self.database_url
                
                if use_ssl:
                    self.pool = await asyncpg.create_pool(self.database_url, ssl='require')
                    logger.info("Connected to DB with SSL")
                else:
                    self.pool = await asyncpg.create_pool(self.database_url)
                    logger.info("Connected to DB without SSL (Railway internal network)")
            except Exception as e:
                logger.error(f"Failed to connect to DB: {e}")
                raise

    async def close(self):
        if self.pool:
            await self.pool.close()

    def is_connected(self) -> bool:
        return self.pool is not None and not self.pool._closed

    async def _execute(self, query: str, *args) -> str:
        if not self.pool:
            await self.connect()
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def _fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        if not self.pool:
            await self.connect()
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def _fetch(self, query: str, *args) -> List[asyncpg.Record]:
        if not self.pool:
            await self.connect()
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def get_or_create_jurisdiction(self, name: str, type: str) -> Optional[str]:
        """Get jurisdiction ID, creating if it doesn't exist."""
        try:
            # Check if exists
            row = await self._fetchrow("SELECT id FROM jurisdictions WHERE name = $1", name)
            if row:
                return str(row['id'])
            
            # Create new
            row = await self._fetchrow(
                "INSERT INTO jurisdictions (name, type) VALUES ($1, $2) RETURNING id",
                name, type
            )
            return str(row['id']) if row else None
        except Exception as e:
            logger.error(f"Error in get_or_create_jurisdiction: {e}")
            return None

    async def store_legislation(self, jurisdiction_id: str, bill_data: Dict[str, Any]) -> Optional[str]:
        """Store legislation in database."""
        try:
            # Check existing
            row = await self._fetchrow(
                "SELECT id FROM legislation WHERE jurisdiction_id = $1 AND bill_number = $2",
                jurisdiction_id, bill_data["bill_number"]
            )
            
            if row:
                # Update
                update_query = """
                    UPDATE legislation 
                    SET title = $1, text = $2, status = $3, updated_at = $4
                    WHERE id = $5
                    RETURNING id
                """
                await self._execute(
                    update_query,
                    bill_data["title"], bill_data["text"], bill_data["status"], datetime.now(),
                    row['id']
                )
                return str(row['id'])
            
            # Insert
            insert_query = """
                INSERT INTO legislation 
                (jurisdiction_id, bill_number, title, text, introduced_date, status, raw_html, analysis_status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """
            row = await self._fetchrow(
                insert_query,
                jurisdiction_id, 
                bill_data["bill_number"],
                bill_data["title"],
                bill_data["text"],
                bill_data.get("introduced_date"),
                bill_data["status"],
                bill_data.get("raw_html"),
                "pending"
            )
            return str(row['id']) if row else None

        except Exception as e:
            logger.error(f"Error in store_legislation: {e}")
            return None

    async def store_impacts(self, legislation_id: str, impacts: List[Dict[str, Any]]) -> bool:
        """Store impact analysis results."""
        if not self.pool:
            await self.connect()
            
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Delete existing
                    await conn.execute("DELETE FROM impacts WHERE legislation_id = $1", legislation_id)
                    
                    # Insert new
                    if impacts:
                        # Prepare batch insert or loop
                        insert_sql = """
                            INSERT INTO impacts 
                            (legislation_id, impact_number, relevant_clause, description, evidence, 
                             chain_of_causality, confidence_factor, p10, p25, p50, p75, p90)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        """
                        for impact in impacts:
                            # evidence list handling: Postgres array or JSONB? 
                            # Usually Supabase handles list -> JSONB or Array automatically.
                            # Assuming JSONB for flexible schema or text[]
                            # Let's try to json dump if it's JSONB, or list if it's array.
                            # Without schema knowledge, safest is typically JSON string or list if using asyncpg with known types.
                            # Given Supabase defaults, likely JSONB or TEXT[].
                            # Using json.dumps for evidence if complex. 
                            evidence = json.dumps(impact.get("evidence", [])) 
                            
                            await conn.execute(insert_sql,
                                legislation_id,
                                impact["impact_number"],
                                impact["relevant_clause"],
                                impact["impact_description"],
                                evidence, # Passing as JSON string
                                impact["chain_of_causality"],
                                impact["confidence_factor"],
                                impact["p10"], impact["p25"], impact["p50"], impact["p75"], impact["p90"]
                            )
                    
                    # Update status
                    await conn.execute(
                        "UPDATE legislation SET analysis_status = 'completed' WHERE id = $1",
                        legislation_id
                    )
            return True
        except Exception as e:
            logger.error(f"Error in store_impacts: {e}")
            return False

    async def get_or_create_source(self, jurisdiction_id: str, name: str, type: str) -> Optional[str]:
        """Get source ID, creating if it doesn't exist."""
        try:
            row = await self._fetchrow(
                "SELECT id FROM sources WHERE jurisdiction_id = $1 AND name = $2",
                jurisdiction_id, name
            )
            if row:
                return str(row['id'])
                
            row = await self._fetchrow(
                "INSERT INTO sources (jurisdiction_id, name, type) VALUES ($1, $2, $3) RETURNING id",
                jurisdiction_id, name, type
            )
            return str(row['id']) if row else None
        except Exception as e:
            logger.error(f"Error in get_or_create_source: {e}")
            return None

    # Admin Task Methods
    async def create_admin_task(self, task_id: str, task_type: str, jurisdiction: str, status: str = "queued", config: Dict = None) -> bool:
        try:
            await self._execute(
                """
                INSERT INTO admin_tasks (id, task_type, jurisdiction, status, config, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                task_id, task_type, jurisdiction, status, json.dumps(config) if config else None, datetime.now()
            )
            return True
        except Exception as e:
            logger.error(f"Error creating admin task: {e}")
            return False

    async def update_admin_task(self, task_id: str, status: str, result: Dict = None, error: str = None) -> bool:
        try:
            fields = ["status = $1", "completed_at = $2"]
            args = [status, datetime.now()]
            
            if result:
                fields.append("result = $" + str(len(args) + 1))
                args.append(json.dumps(result))
            if error:
                fields.append("error_message = $" + str(len(args) + 1))
                args.append(error)
            
            args.append(task_id) # Last arg is ID
            
            query = f"UPDATE admin_tasks SET {', '.join(fields)} WHERE id = ${len(args)}"
            await self._execute(query, *args)
            return True
        except Exception as e:
            logger.error(f"Error updating admin task: {e}")
            return False

    # Scrape History Methods
    async def log_scrape_history(self, entry: Dict[str, Any]) -> bool:
        try:
            await self._execute(
                """
                INSERT INTO scrape_history 
                (jurisdiction, bills_found, bills_new, status, task_id, error_message, notes)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                entry["jurisdiction"],
                entry.get("bills_found", 0),
                entry.get("bills_new", 0),
                entry["status"],
                entry.get("task_id"),
                entry.get("error_message"),
                entry.get("notes")
            )
            return True
        except Exception as e:
            logger.error(f"Error logging scrape history: {e}")
            return False
            
    # RAG Support (Raw Scrapes) - needed for RAG Port but defining now for daily_scrape port
    async def create_raw_scrape(self, scrape_record: Dict[str, Any]) -> Optional[str]:
        try:
            row = await self._fetchrow(
                """
                INSERT INTO raw_scrapes 
                (source_id, content_hash, content_type, data, url, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                scrape_record["source_id"],
                scrape_record["content_hash"],
                scrape_record["content_type"],
                json.dumps(scrape_record["data"]),
                scrape_record["url"],
                json.dumps(scrape_record["metadata"])
            )
            return str(row['id']) if row else None
        except Exception as e:
            logger.error(f"Error creating raw scrape: {e}")
            return None
