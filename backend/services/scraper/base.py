import httpx
import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, List, Optional, Sequence

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ScrapedBill(BaseModel):
    bill_number: str
    title: str
    text: Optional[str] = None
    introduced_date: Optional[date] = None
    status: Optional[str] = None
    raw_html: Optional[str] = None

class BaseScraper(ABC):
    def __init__(self, jurisdiction_name: str):
        self.jurisdiction_name = jurisdiction_name

    @abstractmethod
    async def scrape(self) -> List[ScrapedBill]:
        """
        Scrape legislation from the jurisdiction's source.
        Returns a list of ScrapedBill objects.
        """
        pass

    async def check_health(self) -> bool:
        """
        Check if the jurisdiction's source is accessible.
        Default implementation returns True. Override for real checks.
        """
        return True


class LegistarMatterScraper(BaseScraper):
    """Reusable Legistar API scraper for municipal/county matter feeds."""

    def __init__(
        self,
        jurisdiction_name: str,
        legistar_clients: Sequence[str],
        *,
        matter_filter: str = "MatterIntroDate ge datetime'2025-01-01'",
        top: int = 10,
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(jurisdiction_name)
        self.base_urls = [f"https://webapi.legistar.com/v1/{client}" for client in legistar_clients]
        self.matter_filter = matter_filter
        self.top = top
        self.timeout_seconds = timeout_seconds

    async def check_health(self) -> bool:
        async with httpx.AsyncClient(timeout=5.0) as client:
            for base_url in self.base_urls:
                try:
                    response = await client.get(f"{base_url}/matters", params={"$top": 1})
                    if response.status_code == 200:
                        return True
                except Exception:
                    continue
        return False

    async def scrape(self) -> List[ScrapedBill]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for base_url in self.base_urls:
                try:
                    matters = await self._fetch_matters(client, base_url)
                    return await self._build_bills_for_matters(client, base_url, matters)
                except (httpx.HTTPStatusError, httpx.ConnectError):
                    continue
                except Exception as exc:
                    logger.warning("Legistar scrape failed for %s via %s: %s", self.jurisdiction_name, base_url, exc)
                    continue
        return self._get_mock_data()

    async def _fetch_matters(self, client: httpx.AsyncClient, base_url: str) -> list[dict[str, Any]]:
        response = await client.get(
            f"{base_url}/matters",
            params={
                "$filter": self.matter_filter,
                "$orderby": "MatterIntroDate desc",
                "$top": self.top,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []

    async def _build_bills_for_matters(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        matters: list[dict[str, Any]],
    ) -> List[ScrapedBill]:
        bills: list[ScrapedBill] = []
        for matter in matters:
            text = await self._fetch_matter_text(client, base_url, matter)
            bills.append(self._matter_to_bill(matter, text))
        return bills

    async def _fetch_matter_text(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        matter: dict[str, Any],
    ) -> str:
        matter_id = matter.get("MatterId")
        if matter_id is None:
            return ""

        try:
            text_response = await client.get(f"{base_url}/matters/{matter_id}/texts")
            if text_response.status_code == 200:
                texts = text_response.json()
                if isinstance(texts, list):
                    combined = [
                        item.get("MatterTextPlain", "")
                        for item in texts
                        if isinstance(item, dict) and item.get("MatterTextPlain")
                    ]
                    if combined:
                        return "\n\n".join(combined)
            if text_response.status_code in {404, 405}:
                return await self._fetch_attachment_fallback_text(client, base_url, matter_id)
        except Exception as exc:
            logger.debug("Matter text fetch failed for %s/%s: %s", base_url, matter_id, exc)
        return ""

    async def _fetch_attachment_fallback_text(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        matter_id: Any,
    ) -> str:
        response = await client.get(f"{base_url}/matters/{matter_id}/attachments")
        if response.status_code != 200:
            return ""
        attachments = response.json()
        if not isinstance(attachments, list):
            return ""
        lines = []
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            name = attachment.get("MatterAttachmentName") or "Attachment"
            link = attachment.get("MatterAttachmentHyperlink") or ""
            if link:
                lines.append(f"Attachment: {name} ({link})")
            else:
                lines.append(f"Attachment: {name}")
        return "\n".join(lines)

    def _matter_to_bill(self, matter: dict[str, Any], full_text: str) -> ScrapedBill:
        title = (
            matter.get("MatterTitle")
            or matter.get("MatterName")
            or matter.get("MatterFile")
            or "Untitled"
        )
        text = full_text or matter.get("MatterName") or title
        introduced_date = self._parse_intro_date(matter.get("MatterIntroDate"))
        return ScrapedBill(
            bill_number=matter.get("MatterFile", "Unknown"),
            title=title,
            text=text,
            introduced_date=introduced_date,
            status=matter.get("MatterStatusName", "Unknown"),
            raw_html=str(matter),
        )

    @staticmethod
    def _parse_intro_date(value: Any) -> Optional[date]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except Exception:
            return None

    def _get_mock_data(self) -> List[ScrapedBill]:
        return []
