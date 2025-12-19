import logging
import json
import datetime
import os
from pathlib import Path
from typing import Optional, Any, Dict
from db.postgres_client import PostgresDB

logger = logging.getLogger(__name__)

# Artifact directory for file logs
ARTIFACT_DIR = "/home/fengning/.gemini/antigravity/brain/9112de99-6087-4677-88e8-ddcb9dc376f2"

class AuditLogger:
    """
    Unified logging service for E2E audit traceability.
    Writes step data to:
    1. Terminal (Structured logs)
    2. JSON Artifacts (Machine readable)
    3. Database (pipeline_steps table for Admin UI)
    """

    def __init__(self, run_id: str, db_client: Optional[PostgresDB] = None):
        self.run_id = run_id
        self.db = db_client
        self.steps = []
        
        # Ensure artifact dir exists
        os.makedirs(ARTIFACT_DIR, exist_ok=True)
        self.log_file = Path(ARTIFACT_DIR) / f"audit_{run_id}.json"

    async def log_step(
        self, 
        step_number: int, 
        step_name: str, 
        status: str, 
        input_context: Dict[str, Any] = {}, 
        output_result: Dict[str, Any] = {},
        model_info: Dict[str, Any] = {},
        duration_ms: int = 0
    ):
        """Log a pipeline step to all outputs."""
        # 1. Structure Data
        step = {
            "run_id": self.run_id,
            "step_number": step_number,
            "step_name": step_name,
            "status": status,
            "input_context": input_context,
            "output_result": output_result,
            "model_info": model_info,
            "duration_ms": duration_ms,
            "timestamp": datetime.datetime.now().isoformat()
        }
        self.steps.append(step)

        # 2. Terminal Log
        self._log_to_terminal(step_num=step_number, name=step_name, status=status, data=step)

        # 3. File Artifact Log
        self._log_to_file()

        # 4. DB Write (Async)
        if self.db:
            await self._write_to_db(step)

    def _log_to_terminal(self, step_num: int, name: str, status: str, data: Dict[str, Any]):
        prefix = f"[AUDIT-STEP-{step_num}]"
        logger.info(f"{prefix} {name} - Status: {status}")
        
        # Log concise summary of input/output
        if data.get("model_info"):
            logger.info(f"{prefix} Model: {data['model_info'].get('model', 'unknown')}")
        
        # Don't dump massive JSON to terminal, just key details
        if status == "failed":
            logger.error(f"{prefix} FAILED: {data.get('output_result')}")

    def _log_to_file(self):
        try:
            with open(self.log_file, "w") as f:
                json.dump(self.steps, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to write audit artifact: {e}")

    async def _write_to_db(self, step: Dict[str, Any]):
        if not self.db:
            return
            
        try:
            query = """
                INSERT INTO pipeline_steps 
                (run_id, step_number, step_name, status, input_context, output_result, model_config, duration_ms)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (run_id, step_number) DO UPDATE SET
                    status = EXCLUDED.status,
                    output_result = EXCLUDED.output_result,
                    duration_ms = EXCLUDED.duration_ms,
                    model_config = EXCLUDED.model_config
            """
            
            # Serialize JSON fields
            input_json = json.dumps(step['input_context'], default=str)
            output_json = json.dumps(step['output_result'], default=str)
            model_json = json.dumps(step['model_info'], default=str)
            
            await self.db._execute(
                query, 
                self.run_id, 
                step['step_number'], 
                step['step_name'], 
                step['status'], 
                input_json, 
                output_json, 
                model_json, 
                step['duration_ms']
            )
        except Exception as e:
            logger.error(f"Failed to write step {step['step_name']} to DB: {e}")
