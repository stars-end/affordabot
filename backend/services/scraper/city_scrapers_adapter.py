import json
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .base import BaseScraper, ScrapedBill

logger = logging.getLogger(__name__)


class CityScrapersAdapter(BaseScraper):
    """Run a CityScrapers Scrapy spider and map events into ScrapedBill records."""

    def __init__(self, jurisdiction_name: str, spider_name: str, project_dir: str | None = None):
        super().__init__(jurisdiction_name)
        self.spider_name = spider_name
        if project_dir:
            self.project_dir = Path(project_dir)
        else:
            self.project_dir = Path(__file__).resolve().parents[2] / "affordabot_scraper"

    async def scrape(self) -> list[ScrapedBill]:
        output_path = Path("/tmp") / f"{self.spider_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        try:
            self._run_spider(output_path)
            return self._parse_output(output_path)
        except Exception as exc:
            logger.error("CityScrapers adapter failed for spider=%s: %s", self.spider_name, exc)
            return []
        finally:
            if output_path.exists():
                output_path.unlink()

    def _run_spider(self, output_path: Path) -> None:
        python_bin = shutil.which("python3") or shutil.which("python") or "python3"
        env = dict(os.environ)
        backend_root = str(Path(__file__).resolve().parents[2])
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{backend_root}:{existing}" if existing else backend_root

        cmd = [
            python_bin,
            "-m",
            "scrapy",
            "crawl",
            self.spider_name,
            "-O",
            str(output_path),
            "-s",
            "LOG_LEVEL=ERROR",
        ]
        result = subprocess.run(
            cmd,
            cwd=self.project_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or "unknown scrapy error"
            raise RuntimeError(stderr)

    def _parse_output(self, output_path: Path) -> list[ScrapedBill]:
        if not output_path.exists():
            return []
        raw = json.loads(output_path.read_text())
        if not isinstance(raw, list):
            return []
        return [self._item_to_scraped_bill(item) for item in raw if isinstance(item, dict)]

    @staticmethod
    def _item_to_scraped_bill(item: dict) -> ScrapedBill:
        bill_number = item.get("id") or str(uuid4())
        title = item.get("title") or "Untitled Meeting"
        description = item.get("description") or ""
        links_text = CityScrapersAdapter._links_as_text(item.get("links"))
        text = description if not links_text else f"{description}\n\nLinks:\n{links_text}"
        introduced_date = CityScrapersAdapter._parse_start_date(item.get("start"))
        return ScrapedBill(
            bill_number=bill_number,
            title=title,
            text=text,
            introduced_date=introduced_date,
            status=item.get("status") or "Confirmed",
            raw_html=item.get("source") or "",
        )

    @staticmethod
    def _links_as_text(links: object) -> str:
        if not isinstance(links, list):
            return ""
        lines: list[str] = []
        for link in links:
            if not isinstance(link, dict):
                continue
            href = link.get("href")
            if not href:
                continue
            label = link.get("title") or "Link"
            lines.append(f"[{label}]({href})")
        return "\n".join(lines)

    @staticmethod
    def _parse_start_date(value: object):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except Exception:
            return None


class SanJoseCSAdapter(CityScrapersAdapter):
    def __init__(self):
        super().__init__("City of San Jose", "sanjose_meetings")


class SunnyvaleCSAdapter(CityScrapersAdapter):
    def __init__(self):
        super().__init__("City of Sunnyvale", "sunnyvale_agendas")
