import os
import json
import hashlib
import psycopg2
from datetime import datetime

from scripts.substrate.metadata_contract import build_substrate_raw_metadata


def infer_source_type(spider_name: str) -> str:
    name = (spider_name or "").lower()
    if "municode" in name or "code" in name:
        return "code"
    return "meetings"


class RawScrapePipeline:
    def open_spider(self, spider):
        db_url = os.environ.get("DATABASE_URL")
        # Handle Railway internal vs external URL if needed, but standard URL usually works for psycopg2
        if not db_url:
            spider.logger.error("Missing DATABASE_URL")
            self.conn = None
            return
            
        try:
            self.conn = psycopg2.connect(db_url)
            spider.logger.info("Connected to Postgres via psycopg2")
        except Exception as e:
            spider.logger.error(f"Failed to connect to DB: {e}")
            self.conn = None

    def close_spider(self, spider):
        if self.conn:
            self.conn.close()

    def process_item(self, item, spider):
        if not self.conn:
            return item

        # Get source_id from spider arguments
        source_id = getattr(spider, "source_id", None)
        if not source_id:
            spider.logger.warning("No source_id provided. Skipping DB save.")
            return item

        item_dict = dict(item)
        # Serialize item to JSON for deterministic hash generation
        data_json = json.dumps(item_dict, sort_keys=True)
        
        # Calculate hash
        content_hash = hashlib.sha256(data_json.encode("utf-8")).hexdigest()
        
        try:
            with self.conn.cursor() as cur:
                url = item_dict.get("url")
                if not url:
                    start_urls = getattr(spider, "start_urls", None) or []
                    url = start_urls[0] if start_urls else ""
                content_type = item_dict.get("content_type")
                if not content_type:
                    content_type = (
                        "text/plain"
                        if ("content" in item_dict or "text" in item_dict)
                        else "application/json"
                    )
                source_type = infer_source_type(getattr(spider, "name", ""))
                metadata = build_substrate_raw_metadata(
                    canonical_url=url,
                    source_type=source_type,
                    response_content_type=content_type,
                    capture_method="cron_rag_spiders",
                    title=item_dict.get("title"),
                    extra_metadata={
                        "spider_name": getattr(spider, "name", ""),
                        "source_name": getattr(spider, "name", ""),
                        "scraped_at": item_dict.get("scraped_at"),
                    },
                )
                
                cur.execute(
                    """
                    INSERT INTO raw_scrapes (source_id, content_hash, content_type, data, url, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        source_id,
                        content_hash,
                        content_type,
                        data_json,
                        url,
                        json.dumps(metadata),
                    ),
                )
                
                # Update source last_scraped_at
                cur.execute(
                    """
                    UPDATE sources SET last_scraped_at = %s WHERE id = %s
                    """,
                    (datetime.utcnow(), source_id)
                )
            
            self.conn.commit()
            spider.logger.info(f"Saved item to raw_scrapes (hash: {content_hash[:8]})")
            
        except Exception as e:
            spider.logger.error(f"Failed to save item: {e}")
            self.conn.rollback()

        return item
