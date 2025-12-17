import os
import logging
import json
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger("postgres_db")

class PostgresDB:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL_PUBLIC") or os.getenv("DATABASE_URL")
        # Handle transaction pooler url compatibility if needed (asyncpg usually needs strict formatting)
        # But generic postgres:// should work.
        if not self.database_url:
            logger.warning("DATABASE_URL not set. Database operations will fail.")
        
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Explicitly connect/create pool. Helpers will auto-connect if needed."""
        if not self.database_url:
            logger.error("Cannot connect: DATABASE_URL is not set.")
            raise ValueError("DATABASE_URL is not set")

        if not self.pool:
            try:
                # Railway internal network and TCP Proxy don't support SSL upgrade
                # Only use SSL for true external connections (Supabase, etc.)
                use_ssl = 'railway.internal' not in self.database_url and 'proxy.rlwy.net' not in self.database_url
                
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

    async def get_jurisdiction_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get jurisdiction config by name."""
        try:
            row = await self._fetchrow("SELECT * FROM jurisdictions WHERE name = $1", name)
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error in get_jurisdiction_by_name: {e}")
            return None

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

    async def create_legislation(self, jurisdiction_id: str, bill_data: Dict[str, Any]) -> Optional[str]:
        """Alias for store_legislation."""
        return await self.store_legislation(jurisdiction_id, bill_data)

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

    async def create_pipeline_run(self, bill_id: str, jurisdiction: str, models: Dict[str, str]) -> Optional[str]:
        """Create a new pipeline run record."""
        try:
            row = await self._fetchrow(
                """
                INSERT INTO pipeline_runs (bill_id, jurisdiction, models, started_at)
                VALUES ($1, $2, $3, NOW())
                RETURNING id
                """,
                bill_id, jurisdiction, json.dumps(models)
            )
            return str(row['id']) if row else None
        except Exception as e:
            logger.error(f"Error creating pipeline run: {e}")
            return None

    async def complete_pipeline_run(self, run_id: str, result: Dict[str, Any]) -> bool:
        """Mark pipeline run as complete."""
        try:
            await self._execute(
                """
                UPDATE pipeline_runs
                SET status = 'completed', result = $1, completed_at = NOW()
                WHERE id = $2
                """,
                json.dumps(result), run_id
            )
            return True
        except Exception as e:
            logger.error(f"Error completing pipeline run: {e}")
            return False

    async def fail_pipeline_run(self, run_id: str, error: str) -> bool:
        """Mark pipeline run as failed."""
        try:
            await self._execute(
                """
                UPDATE pipeline_runs
                SET status = 'failed', error = $1, completed_at = NOW()
                WHERE id = $2
                """,
                error, run_id
            )
            return True
        except Exception as e:
            logger.error(f"Error failing pipeline run: {e}")
            return False

    async def get_or_create_source(self, jurisdiction_id: str, name: str, type: str, url: str = None) -> Optional[str]:
        """Get source ID, creating if it doesn't exist."""
        try:
            # Check by URL if provided (stronger match), otherwise Name
            if url:
             row = await self._fetchrow("SELECT id FROM sources WHERE url = $1", url)
             if row:
                 return str(row['id'])

            row = await self._fetchrow(
                "SELECT id FROM sources WHERE jurisdiction_id = $1 AND name = $2",
                jurisdiction_id, name
            )
            if row:
                return str(row['id'])
                
            row = await self._fetchrow(
                "INSERT INTO sources (jurisdiction_id, name, type, url) VALUES ($1, $2, $3, $4) RETURNING id",
                jurisdiction_id, name, type, url
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

    async def create_scrape_history(self, **kwargs) -> bool:
        """Wrapper for log_scrape_history using kwargs."""
        return await self.log_scrape_history(kwargs)
            
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

    async def get_admin_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get admin task by ID."""
        try:
            row = await self._fetchrow("SELECT * FROM admin_tasks WHERE id = $1", task_id)
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching admin task: {e}")
            return None

    # Model Config Methods
    async def get_model_configs(self) -> List[Dict[str, Any]]:
        """Get all model configurations."""
        try:
            rows = await self._fetch("SELECT * FROM model_configs ORDER BY priority")
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching model configs: {e}")
            return []

    async def update_model_config(self, provider: str, model_name: str, use_case: str, priority: int, enabled: bool) -> bool:
        """Upsert model configuration."""
        try:
            query = """
                INSERT INTO model_configs (provider, model_name, use_case, priority, enabled, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (provider, model_name, use_case) 
                DO UPDATE SET 
                    priority = EXCLUDED.priority,
                    enabled = EXCLUDED.enabled,
                    updated_at = NOW()
            """
            await self._execute(query, provider, model_name, use_case, priority, enabled)
            return True
        except Exception as e:
            logger.error(f"Error updating model config: {e}")
            return False

    # System Prompt Methods
    async def get_system_prompt(self, prompt_type: str) -> Optional[Dict[str, Any]]:
        """Get active system prompt for type."""
        try:
            row = await self._fetchrow(
                "SELECT * FROM system_prompts WHERE prompt_type = $1 AND is_active = true",
                prompt_type
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching system prompt: {e}")
            return None

    async def update_system_prompt(self, prompt_type: str, system_prompt: str, description: str = None, user_id: str = "admin") -> Optional[int]:
        """Update system prompt (create new version). Returns new version number."""
        try:
            # Get next version
            ver_row = await self._fetchrow(
                "SELECT version FROM system_prompts WHERE prompt_type = $1 ORDER BY version DESC LIMIT 1",
                prompt_type
            )
            next_version = (ver_row['version'] + 1) if ver_row else 1
            
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Deactivate current
                    await conn.execute(
                        "UPDATE system_prompts SET is_active = false WHERE prompt_type = $1 AND is_active = true",
                        prompt_type
                    )
                    
                    # Insert new
                    await conn.execute(
                        """
                        INSERT INTO system_prompts 
                        (prompt_type, version, system_prompt, description, is_active, activated_at, created_at, created_by)
                        VALUES ($1, $2, $3, $4, true, NOW(), NOW(), $5)
                        """,
                        prompt_type, next_version, system_prompt, description or f"Version {next_version}", user_id
                    )
            return next_version
        except Exception as e:
            logger.error(f"Error updating system prompt: {e}")
            return None

    # Analysis History Methods
    async def get_analysis_history(self, jurisdiction: str = None, bill_id: str = None, step: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get analysis history with filters."""
        try:
            query = "SELECT * FROM analysis_history"
            conditions = []
            params = []
            
            if jurisdiction:
                conditions.append(f"jurisdiction = ${len(params)+1}")
                params.append(jurisdiction)
            if bill_id:
                conditions.append(f"bill_id = ${len(params)+1}")
                params.append(bill_id)
            if step:
                conditions.append(f"step = ${len(params)+1}")
                params.append(step)
                
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            query += f" ORDER BY created_at DESC LIMIT ${len(params)+1}"
            params.append(limit)
            
            rows = await self._fetch(query, *params)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching analysis history: {e}")
            return []

    # Template Review Methods
    async def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Get pending template reviews."""
        try:
            # Assuming table 'template_reviews' exists; if not it might fail, but this is migration.
            rows = await self._fetch("SELECT * FROM template_reviews WHERE status = 'pending'")
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching pending reviews: {e}")
            return []

    async def update_review_status(self, review_id: str, status: str) -> bool:
        """Update review status."""
        try:
            await self._execute("UPDATE template_reviews SET status = $1 WHERE id = $2", status, review_id)
            return True
        except Exception as e:
            logger.error(f"Error updating review status: {e}")
            return False

    async def get_legislation_by_jurisdiction(self, jurisdiction_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent legislation for a jurisdiction with impacts."""
        try:
            # Get jurisdiction ID
            jur_row = await self._fetchrow("SELECT id FROM jurisdictions WHERE name = $1", jurisdiction_name)
            if not jur_row:
                return []
            jurisdiction_id = jur_row['id']

            # Get legislation
            legislation_rows = await self._fetch(
                """
                SELECT * FROM legislation
                WHERE jurisdiction_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                jurisdiction_id, limit
            )

            results = []
            for leg in legislation_rows:
                leg_dict = dict(leg)
                # Fetch impacts
                impact_rows = await self._fetch(
                    "SELECT * FROM impacts WHERE legislation_id = $1 ORDER BY impact_number",
                    leg['id']
                )

                impacts = []
                for imp in impact_rows:
                    imp_dict = dict(imp)
                    # Parse evidence if it's a string (JSON)
                    if isinstance(imp_dict.get('evidence'), str):
                        try:
                            imp_dict['evidence'] = json.loads(imp_dict['evidence'])
                        except json.JSONDecodeError:
                            pass
                    impacts.append(imp_dict)

                leg_dict['impacts'] = impacts
                results.append(leg_dict)

            return results
        except Exception as e:
            logger.error(f"Error in get_legislation_by_jurisdiction: {e}")
            return []

    async def get_bill(self, jurisdiction_name: str, bill_number: str) -> Optional[Dict[str, Any]]:
        """Get specific bill with impacts."""
        try:
            # Get jurisdiction ID
            jur_row = await self._fetchrow("SELECT id, name, type FROM jurisdictions WHERE name = $1", jurisdiction_name)
            if not jur_row:
                return None
            jurisdiction_id = jur_row['id']

            # Get legislation
            leg_row = await self._fetchrow(
                """
                SELECT * FROM legislation
                WHERE jurisdiction_id = $1 AND bill_number = $2
                """,
                jurisdiction_id, bill_number
            )

            if not leg_row:
                return None

            leg_dict = dict(leg_row)
            leg_dict['jurisdiction'] = jur_row['name']

            # Fetch impacts
            impact_rows = await self._fetch(
                "SELECT * FROM impacts WHERE legislation_id = $1 ORDER BY impact_number",
                leg_dict['id']
            )

            impacts = []
            for imp in impact_rows:
                imp_dict = dict(imp)
                # Parse evidence if it's a string (JSON)
                if isinstance(imp_dict.get('evidence'), str):
                    try:
                        imp_dict['evidence'] = json.loads(imp_dict['evidence'])
                    except json.JSONDecodeError:
                        pass
                impacts.append(imp_dict)

            leg_dict['impacts'] = impacts
            return leg_dict

        except Exception as e:
            logger.error(f"Error in get_bill: {e}")
            return None
