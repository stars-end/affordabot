import os
import json
import hashlib
import psycopg2
from datetime import datetime

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

        # Serialize item to JSON
        data_json = json.dumps(item, sort_keys=True)
        
        # Calculate hash
        content_hash = hashlib.sha256(data_json.encode("utf-8")).hexdigest()
        
        try:
            with self.conn.cursor() as cur:
                # Insert raw_scrape
                # raw_scrapes schema: source_id, content_hash, content_type, data, url(optional), metadata(optional)
                # Ensure data is JSON compatible for JSONB column
                
                # We need to check if 'url' is in item?
                url = item.get('url') # Scrapy items usually have url
                
                cur.execute(
                    """
                    INSERT INTO raw_scrapes (source_id, content_hash, content_type, data, url)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (source_id, content_hash, "application/json", data_json, url)
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
