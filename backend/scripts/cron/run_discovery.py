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

from db.supabase_client import SupabaseDB
from services.auto_discovery_service import AutoDiscoveryService

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("discovery")

async def main():
    task_id = str(uuid4())
    logger.info(f"🚀 Starting Discovery (Task {task_id})")
    
    db = SupabaseDB()
    discovery_service = AutoDiscoveryService()
    
    # 1. Log Start
    if db.client:
        db.client.table('admin_tasks').insert({
            'id': task_id,
            'task_type': 'discovery',
            'status': 'running',
            'created_at': datetime.now().isoformat()
        }).execute()
        
    try:
        # 2. Get Jurisdictions
        # For now, just active ones or all. Let's do all.
        jurisdictions = db.client.table('jurisdictions').select('*').execute().data
        
        results = {"found": 0, "new": 0}
        
        for jur in jurisdictions:
            logger.info(f"🔎 Discovering for {jur['name']}...")
            
            # Run Discovery
            discovered_items = await discovery_service.discover_sources(jur['name'], jur.get('type', 'city'))
            
            for item in discovered_items:
                results["found"] += 1
                
                # Check duplication
                # Note: We match on URL to avoid re-adding
                existing = db.client.table('sources').select('id').eq('jurisdiction_id', jur['id']).eq('url', item['url']).execute()
                
                if not existing.data:
                    # Create Source
                    db.client.table('sources').insert({
                        'jurisdiction_id': jur['id'],
                        'name': item['title'],
                        'type': 'web', # Default to web for harvester
                        'url': item['url'],
                        'scrape_url': item['url'],
                        'metadata': {
                            'category': item['category'], 
                            'snippet': item['snippet'],
                            'discovered_at': datetime.now().isoformat()
                        }
                    }).execute()
                    results["new"] += 1
                    logger.info(f"   + Added: {item['title']}")
        
        # 3. Log Success
        logger.info(f"🏁 Discovery Complete. {results}")
        
        if db.client:
            db.client.table('admin_tasks').update({
                'status': 'completed',
                'completed_at': datetime.now().isoformat(),
                'result': results
            }).eq('id', task_id).execute()

    except Exception as e:
        logger.error(f"❌ Critical Failure: {e}")
        if db.client:
            db.client.table('admin_tasks').update({
                'status': 'failed',
                'completed_at': datetime.now().isoformat(),
                'error_message': str(e)
            }).eq('id', task_id).execute()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
