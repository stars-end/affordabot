import os
from supabase import create_client, Client
from typing import Optional, List, Dict, Any
from datetime import datetime

class SupabaseDB:
    def __init__(self, client: Optional[Client] = None):
        if client:
            self.client = client
            return

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not url or not key:
            print("WARNING: Supabase credentials not set. Database operations will fail.")
            self.client: Optional[Client] = None
        else:
            self.client = create_client(url, key)
    
    async def get_or_create_jurisdiction(self, name: str, type: str) -> Optional[str]:
        """Get jurisdiction ID, creating if it doesn't exist."""
        if not self.client:
            return None
        
        # Check if exists
        result = self.client.table("jurisdictions").select("id").eq("name", name).execute()
        
        if result.data:
            return result.data[0]["id"]
        
        # Create new
        result = self.client.table("jurisdictions").insert({
            "name": name,
            "type": type
        }).execute()
        
        return result.data[0]["id"] if result.data else None
    
    async def store_legislation(self, jurisdiction_id: str, bill_data: Dict[str, Any]) -> Optional[str]:
        """Store legislation in database."""
        if not self.client:
            return None
        
        # Serialize date objects if present
        if "introduced_date" in bill_data and hasattr(bill_data["introduced_date"], "isoformat"):
            bill_data["introduced_date"] = bill_data["introduced_date"].isoformat()
        
        # Check if exists
        existing = self.client.table("legislation").select("id").eq(
            "jurisdiction_id", jurisdiction_id
        ).eq("bill_number", bill_data["bill_number"]).execute()
        
        if existing.data:
            # Update existing
            self.client.table("legislation").update({
                "title": bill_data["title"],
                "text": bill_data["text"],
                "status": bill_data["status"],
                "updated_at": datetime.now().isoformat()
            }).eq("id", existing.data[0]["id"]).execute()
            return existing.data[0]["id"]
        
        # Insert new
        result = self.client.table("legislation").insert({
            "jurisdiction_id": jurisdiction_id,
            "bill_number": bill_data["bill_number"],
            "title": bill_data["title"],
            "text": bill_data["text"],
            "introduced_date": bill_data.get("introduced_date"),
            "status": bill_data["status"],
            "raw_html": bill_data.get("raw_html"),
            "analysis_status": "pending"
        }).execute()
        
        return result.data[0]["id"] if result.data else None
    
    async def store_impacts(self, legislation_id: str, impacts: List[Dict[str, Any]]) -> bool:
        """Store impact analysis results."""
        if not self.client:
            return False
        
        # Delete existing impacts for this legislation
        self.client.table("impacts").delete().eq("legislation_id", legislation_id).execute()
        
        # Insert new impacts
        impact_records = []
        for impact in impacts:
            impact_records.append({
                "legislation_id": legislation_id,
                "impact_number": impact["impact_number"],
                "relevant_clause": impact["relevant_clause"],
                "description": impact["impact_description"],
                "evidence": impact.get("evidence", []),
                "chain_of_causality": impact["chain_of_causality"],
                "confidence_factor": impact["confidence_factor"],
                "p10": impact["p10"],
                "p25": impact["p25"],
                "p50": impact["p50"],
                "p75": impact["p75"],
                "p90": impact["p90"]
            })
        
        if impact_records:
            self.client.table("impacts").insert(impact_records).execute()
        
        # Update legislation analysis status
        self.client.table("legislation").update({
            "analysis_status": "completed"
        }).eq("id", legislation_id).execute()
        
        return True
    
    async def create_pipeline_run(self, bill_id: str, jurisdiction: str, models: Dict[str, str]) -> Optional[str]:
        """Create a new pipeline run record."""
        if not self.client:
            return None

        result = self.client.table("pipeline_runs").insert({
            "bill_id": bill_id,
            "jurisdiction": jurisdiction,
            "models": models,
            "started_at": datetime.now().isoformat()
        }).execute()

        return result.data[0]["id"] if result.data else None

    async def complete_pipeline_run(self, run_id: str, result: Dict[str, Any]) -> bool:
        """Mark pipeline run as complete."""
        if not self.client:
            return False

        self.client.table("pipeline_runs").update({
            "status": "completed",
            "result": result,
            "completed_at": datetime.now().isoformat()
        }).eq("id", run_id).execute()

        return True

    async def fail_pipeline_run(self, run_id: str, error: str) -> bool:
        """Mark pipeline run as failed."""
        if not self.client:
            return False

        self.client.table("pipeline_runs").update({
            "status": "failed",
            "error": error,
            "completed_at": datetime.now().isoformat()
        }).eq("id", run_id).execute()

        return True

    async def get_or_create_source(self, jurisdiction_id: str, name: str, type: str, url: Optional[str] = None) -> Optional[str]:
        """Get source ID, creating if it doesn't exist."""
        if not self.client:
            return None
            
        # Check if exists
        result = self.client.table("sources").select("id").eq("jurisdiction_id", jurisdiction_id).eq("name", name).execute()
        
        if result.data:
            return result.data[0]["id"]
            
        # Create new
        result = self.client.table("sources").insert({
            "jurisdiction_id": jurisdiction_id,
            "name": name,
            "type": type,
            "url": url
        }).execute()
        
        return result.data[0]["id"] if result.data else None

    async def get_legislation_by_jurisdiction(self, jurisdiction_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent legislation for a jurisdiction with impacts."""
        if not self.client:
            return []
        
        # Get jurisdiction ID
        jur_result = self.client.table("jurisdictions").select("id").eq("name", jurisdiction_name).execute()
        if not jur_result.data:
            return []
        
        jurisdiction_id = jur_result.data[0]["id"]
        
        # Get legislation with impacts
        result = self.client.table("legislation").select(
            "*, impacts(*)"
        ).eq("jurisdiction_id", jurisdiction_id).order(
            "created_at", desc=True
        ).limit(limit).execute()
        
        return result.data if result.data else []
