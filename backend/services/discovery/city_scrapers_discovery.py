from typing import List
import subprocess
import json
import os
import logging
from datetime import datetime
from llm_common.core.models import WebSearchResult

logger = logging.getLogger(__name__)

class CityScrapersDiscoveryService:
    """
    Discovery service that wraps City Scrapers (Spiders) to find meeting content.
    """
    
    def __init__(self):
        # Path to scraper project
        self.project_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "affordabot_scraper"
        )

    async def find_meeting_content(self, agency: str = "sanjose") -> List[WebSearchResult]:
        """
        Run the spider for the given agency and return discovery results (Agendas/Minutes URLs).
        """
        spider_name = f"{agency}_meetings"
        output_file = f"/tmp/{spider_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        
        # We run scrapy as a subprocess because it uses Twisted and doesn't play well 
        # with the existing asyncio loop of the FastAPI app if run in-process without care.
        # Alternatively we could use Crochet, but subprocess is safer for isolation.
        
        cmd = [
            "poetry", "run", "scrapy", "crawl", spider_name,
            "-O", output_file,
            "-s", "LOG_LEVEL=ERROR" # Reduce noise
        ]
        
        logger.info(f"Running spider: {' '.join(cmd)}")
        
        try:
            # Execute scraper
            process = subprocess.Popen(
                cmd,
                cwd=self.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Spider failed: {stderr.decode()}")
                return []
            
            # Parse results
            results = []
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    data = json.load(f)
                    
                for item in data:
                    # Extract Agenda
                    if "Agenda" in item and isinstance(item["Agenda"], dict):
                        url = item["Agenda"].get("url")
                        if url and "not available" not in url.lower():
                            results.append(WebSearchResult(
                                title=f"Agenda: {item.get('Name', {}).get('label', 'Meeting')} - {item.get('Meeting Date')}",
                                url=url,
                                content=f"Meeting Date: {item.get('Meeting Date')} Time: {item.get('Meeting Time')}",
                                published_date=None,
                                snippet=f"Agenda for meeting on {item.get('Meeting Date')}",
                                domain=url.split('/')[2] if url else "sanjose.legistar.com"
                            ))
                            
                    # Extract Minutes
                    if "Minutes" in item and isinstance(item["Minutes"], dict):
                        url = item["Minutes"].get("url")
                        if url and "not available" not in url.lower():
                             results.append(WebSearchResult(
                                title=f"Minutes: {item.get('Name', {}).get('label', 'Meeting')} - {item.get('Meeting Date')}",
                                url=url,
                                content=f"Meeting Date: {item.get('Meeting Date')} Time: {item.get('Meeting Time')}",
                                published_date=None,
                                snippet=f"Minutes for meeting on {item.get('Meeting Date')}",
                                domain=url.split('/')[2] if url else "sanjose.legistar.com"
                            ))
                            
                # Cleanup
                os.remove(output_file)
                
            return results
            
        except Exception as e:
            logger.error(f"Error running city scraper: {e}")
            return []
