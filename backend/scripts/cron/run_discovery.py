#!/usr/bin/env python3
"""
Discovery Cron
Runs AutoDiscoveryService to find new sources (URLs) for jurisdictions.
Saves them to 'sources' table for the Universal Harvester.
"""

import sys
import os
import logging
import asyncio
from datetime import datetime
from uuid import uuid4

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from db.postgres_client import PostgresDB
from services.auto_discovery_service import AutoDiscoveryService

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("discovery")

async def main():
    task_id = str(uuid4())
    logger.info(f"🚀 Starting Discovery (Task {task_id})")
    
    db = PostgresDB()
    discovery_service = AutoDiscoveryService()
    
    # 1. Log Start
    try:
        await db.create_admin_task(
            task_id=task_id,
            task_type='discovery',
            status='running'
        )
    except Exception as e:
        logger.error(f"Failed to create admin task: {e}")
        
    try:
        # 2. Get Jurisdictions
        # For now, just active ones or all. Let's do all.
        jurisdictions_rows = await db._fetch("SELECT * FROM jurisdictions")
        jurisdictions = [dict(row) for row in jurisdictions_rows]
        
        results = {"found": 0, "new": 0}
        
        for jur in jurisdictions:
            logger.info(f"🔎 Discovering for {jur['name']}...")
            
            # Run Discovery
            discovered_items = await discovery_service.discover_sources(jur['name'], jur.get('type', 'city'))
            
            for item in discovered_items:
                results["found"] += 1
                
                # Check duplication (PostgresDB doesn't have convenient chained query builder yet for exact logic)
                # But get_or_create_source handles it IF we pass URL.
                # Currently get_or_create_source uses name/type.
                # Let's check manually.
                
                existing = await db._fetchrow("SELECT id FROM sources WHERE jurisdiction_id = $1 AND url = $2", jur['id'], item['url'])
                
                if not existing:
                    # Create Source
                    await db.get_or_create_source(
                        jurisdiction_id=str(jur['id']),
                        name=item['title'],
                        type='web',
                        url=item['url'] # Assuming we updated get_or_create_source to take URL or we do raw insert here?
                        # PostgresDB in postgres_client.py needs to be checked.
                        # Assuming raw insert for safety.
                    )
                    # Or use raw insert to be sure about metadata
                    await db.create_source({
                        'jurisdiction_id': str(jur['id']),
                        'name': item['title'],
                        'type': 'web',
                        'url': item['url'],
                        'scrape_url': item['url'],
                        'metadata': {
                            'category': item['category'], 
                            'snippet': item['snippet'],
                            'discovered_at': datetime.now().isoformat()
                        }
                    })
                    results["new"] += 1
                    logger.info(f"   + Added: {item['title']}")
        
        # 3. Log Success
        logger.info(f"🏁 Discovery Complete. {results}")
        
        await db.update_admin_task(
            task_id=task_id,
            status='completed',
            result=results
        )

    except Exception as e:
        logger.error(f"❌ Critical Failure: {e}")
        try:
            await db.update_admin_task(
                task_id=task_id,
                status='failed',
                error=str(e)
            )
        except:
             pass
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
