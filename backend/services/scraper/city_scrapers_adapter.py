import os
import json
import logging
import subprocess
import shutil
from typing import List
from datetime import datetime
from uuid import uuid4
from .base import BaseScraper, ScrapedBill

logger = logging.getLogger(__name__)

class CityScrapersAdapter(BaseScraper):
    """
    Adapter to run a CityScrapers (Scrapy) spider and adapt the output to ScrapedBill format.
    """
    def __init__(self, jurisdiction_name: str, spider_name: str, project_dir: str = None):
        super().__init__(jurisdiction_name)
        self.spider_name = spider_name
        
        # Default project dir relative to backend
        if not project_dir:
            self.project_dir = os.path.abspath(os.path.join(
                os.path.dirname(__file__), # backend/services/scraper
                "../../../affordabot_scraper" # root/affordabot_scraper
            ))
        else:
            self.project_dir = project_dir

    async def scrape(self) -> List[ScrapedBill]:
        """
        Run the spider and return results as ScrapedBills.
        """
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        output_file = f"/tmp/{self.spider_name}_{timestamp}.json"
        
        # Ensure poetry is available or use full path?
        # Assuming we run this from an env where 'poetry' is in PATH
        cmd = [
            "poetry", "run", "scrapy", "crawl", self.spider_name,
            "-O", output_file,
            "-s", "LOG_LEVEL=ERROR"
        ]
        
        # We need to run this command inside the affordabot_scraper directory, 
        # BUT we need the python environment.
        # Ideally: 'poetry run' handles the venv.
        # But 'affordabot_scraper' is a separate folder without pyproject.toml?
        # No, 'backend/' has pyproject.toml. 'root/' has nothing?
        # Wait, 'affordabot_scraper/scrapy.cfg' exists.
        # If I run 'scrapy' from there, I need 'city-scrapers-core' installed.
        # It is installed in BACKEND env.
        # So I should run from BACKEND directory?
        # NO, Scrapy needs `scrapy.cfg` to find settings.
        # Solution: Run from `affordabot_scraper` dir, but using Backend's poetry env?
        # OR: Run from Backend dir, but target the spider in `../affordabot_scraper`? 
        # Scrapy expects to be run from project root.
        
        # Workaround: Set PYTHONPATH to include backend env site-packages?
        # Or simpler:
        # Run `poetry run scrapy crawl ...` from `backend/` but pass valid settings?
        # Actually, if I run from `affordabot_scraper`, `poetry run` might expect pyproject.toml in `affordabot_scraper` (it doesn't exist).
        # 
        # Correct approach:
        # User's 'backend' env has dependencies.
        # 'affordabot_scraper' is just code.
        # I can run `scrapy` from `affordabot_scraper` dir using the backend's python.
        
        # Find backend python executable
        backend_python = shutil.which("python3") # This should be the venv python if running from daily_scrape
        
        cmd = [
            backend_python, "-m", "scrapy", "crawl", self.spider_name,
            "-O", output_file,
            "-s", "LOG_LEVEL=ERROR"
        ]
        
        logger.info(f"Running spider {self.spider_name}...")
        
        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.project_dir, # Run in scraper project root
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "PYTHONPATH": os.environ.get("PYTHONPATH", "") + ":" + os.getcwd()} 
                # inherit env, maybe add backend to pythonpath
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Spider failed: {stderr.decode()}")
                return []
            
            # Parse Results
            bills = []
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    data = json.load(f)
                    
                for item in data:
                    # Map Meeting -> ScrapedBill
                    # Item keys: _type, id, title, description, start, end, location, links, source
                    
                    bill_number = item.get("id") or str(uuid4())
                    title = item.get("title", "Untitled Meeting")
                    desc = item.get("description", "")
                    
                    # Convert Links to text
                    links_text = ""
                    if "links" in item:
                        links_text = "\n".join([f"[{link.get('title', 'Link')}]({link['href']})" for link in item['links']])
                    
                    full_text = f"{desc}\n\nLinks:\n{links_text}"
                    
                    dt = None
                    if item.get("start"):
                        try:
                            dt = datetime.fromisoformat(item["start"]).date()
                        except Exception:
                            pass
                            
                    bills.append(ScrapedBill(
                        bill_number=bill_number,
                        title=title,
                        text=full_text,
                        introduced_date=dt,
                        status=item.get("status", "Confirmed"),
                        raw_html=item.get("source", "") # Source URL
                    ))
                
                os.remove(output_file)
                return bills
            else:
                logger.warning("No output file generated by spider.")
                return []

        except Exception as e:
            logger.error(f"Error running adapter: {e}")
            return []

class SanJoseCSAdapter(CityScrapersAdapter):
    def __init__(self):
        super().__init__("City of San Jose", "sanjose_meetings")

