import os
import json
import hashlib
import psycopg2
from datetime import datetime, timezone

from services.substrate_promotion import (
    apply_promotion_decision,
    evaluate_rules,
    seed_capture_promotion_metadata,
)


DOCUMENT_TYPE_MEETING = "meeting"
DOCUMENT_TYPE_MUNICIPAL_CODE = "municipal_code"
CAPTURE_METHOD_SPIDER = "scrapy_spider"
CONTENT_CLASS_JSON = "json_text"


class RawScrapePipeline:
    def open_spider(self, spider):
        db_url = os.environ.get("DATABASE_URL")
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

    def _utc_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _build_substrate_metadata(
        self,
        *,
        canonical_url: str,
        document_type: str,
        spider_name: str,
        source_id: str,
    ) -> dict:
        """Build framework-complete substrate metadata for spider captures."""
        base_metadata = {
            "canonical_url": canonical_url,
            "document_type": document_type,
            "source_type": "meetings"
            if document_type == DOCUMENT_TYPE_MEETING
            else "code",
            "content_class": CONTENT_CLASS_JSON,
            "trust_tier": "official_partner",
            "capture_method": CAPTURE_METHOD_SPIDER,
            "substrate_version": "scheduled-v1",
            "spider_name": spider_name,
            "source_id": source_id,
            "captured_at": self._utc_iso(),
            "ingestion_truth": {
                "stage": "raw_captured",
                "raw_captured": True,
                "blob_stored": False,
                "storage_uri_present": False,
                "parsed": False,
                "chunked": False,
                "embedded": False,
                "vector_upserted": False,
                "retrievable": False,
                "ingest_attempted": False,
                "last_updated_at": self._utc_iso(),
            },
        }
        seeded = seed_capture_promotion_metadata(
            metadata=base_metadata,
            canonical_url=canonical_url,
            trust_tier=base_metadata["trust_tier"],
        )
        return apply_promotion_decision(
            metadata=seeded,
            decision=evaluate_rules(seeded),
            canonical_url=canonical_url,
        )

    def process_item(self, item, spider):
        if not self.conn:
            return item

        source_id = getattr(spider, "source_id", None)
        if not source_id:
            spider.logger.warning("No source_id provided. Skipping DB save.")
            return item

        data_json = json.dumps(item, sort_keys=True)
        content_hash = hashlib.sha256(data_json.encode("utf-8")).hexdigest()

        try:
            with self.conn.cursor() as cur:
                url = item.get("url")

                document_type = DOCUMENT_TYPE_MEETING
                if "municode" in spider.name.lower():
                    document_type = DOCUMENT_TYPE_MUNICIPAL_CODE

                metadata = self._build_substrate_metadata(
                    canonical_url=url or f"spider://{spider.name}",
                    document_type=document_type,
                    spider_name=spider.name,
                    source_id=source_id,
                )

                cur.execute(
                    """
                    INSERT INTO raw_scrapes (source_id, content_hash, content_type, data, url, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        source_id,
                        content_hash,
                        "application/json",
                        data_json,
                        url,
                        json.dumps(metadata),
                    ),
                )

                cur.execute(
                    """
                    UPDATE sources SET last_scraped_at = %s WHERE id = %s
                    """,
                    (datetime.now(timezone.utc), source_id),
                )

            self.conn.commit()
            spider.logger.info(
                f"Saved item to raw_scrapes with substrate metadata (hash: {content_hash[:8]})"
            )

        except Exception as e:
            spider.logger.error(f"Failed to save item: {e}")
            self.conn.rollback()

        return item
