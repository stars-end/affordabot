import os
import json
import hashlib
from datetime import datetime
from supabase import create_client, Client

class RawScrapePipeline:
    def open_spider(self, spider):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            spider.logger.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
            self.supabase = None
            return
        self.supabase: Client = create_client(url, key)

    def process_item(self, item, spider):
        if not self.supabase:
            return item

        # Get source_id from spider arguments
        source_id = getattr(spider, "source_id", None)
        if not source_id:
            spider.logger.warning("No source_id provided. Skipping DB save.")
            return item

        # Serialize item to JSON
        data_json = json.dumps(item, sort_keys=True)
        
        # Calculate hash
        content_hash = hashlib.sha256(data_json.encode("utf-8")).hexdigest()
        
        # Prepare record
        record = {
            "source_id": source_id,
            "content_hash": content_hash,
            "content_type": "application/json",
            "data": item
        }

        try:
            # Check for duplicates (optional, but good for idempotency)
            # For now, we just insert. The raw_scrapes table doesn't enforce unique hash per source yet,
            # but we might want to dedupe later.
            
            self.supabase.table("raw_scrapes").insert(record).execute()
            
            # Update source last_scraped_at
            self.supabase.table("sources").update({"last_scraped_at": datetime.utcnow().isoformat()}).eq("id", source_id).execute()
            
            spider.logger.info(f"Saved item to raw_scrapes (hash: {content_hash[:8]})")
        except Exception as e:
            spider.logger.error(f"Failed to save item: {e}")

        return item
