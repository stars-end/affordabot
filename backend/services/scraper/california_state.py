"""
California State Legislature Scraper.

Architecture (bd-tytc.3):
- OpenStates API is used for DISCOVERY and METADATA only
- Official California legislature-linked HTML/PDF/text is the CANONICAL bill text source
- No mock fallback in truth-critical runtime paths
- Bill text is written to raw_scrapes for ingestion before analysis
- Source provenance is preserved for retrieval filtering
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field
import httpx
import os
import logging
import hashlib
import re

from .base import BaseScraper, ScrapedBill

logger = logging.getLogger("california_scraper")

LEGISLATURE_BASE_URL = "https://leginfo.legislature.ca.gov"


class BillSourceProvenance(BaseModel):
    source_url: str = ""
    source_type: str = "unknown"
    version_identifier: str = ""
    version_note: str = ""
    extraction_status: str = "pending"
    extraction_error: Optional[str] = None
    content_hash: Optional[str] = None


class CaliforniaScrapedBill(ScrapedBill):
    provenance: BillSourceProvenance = Field(
        default_factory=lambda: BillSourceProvenance()
    )
    jurisdiction: str = "california"
    source_system: str = "openstates+leginfo"


class CaliforniaStateScraper(BaseScraper):
    def __init__(self, db_client=None, jurisdiction_name: str = "State of California"):
        super().__init__(jurisdiction_name)
        self.api_key = os.getenv("OPENSTATES_API_KEY")
        self.base_url = "https://v3.openstates.org"
        self.db = db_client

    async def check_health(self) -> bool:
        if not self.api_key:
            return False

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/jurisdictions",
                    headers={"X-API-KEY": self.api_key},
                )
                return response.status_code == 200
            except Exception:
                return False

    async def scrape(self) -> List[ScrapedBill]:
        """
        Scrape California State Legislature.

        Flow:
        1. Use OpenStates for bill discovery and metadata
        2. Follow official legislature links for canonical bill text
        3. Return bills with full provenance
        """
        if not self.api_key:
            raise RuntimeError(
                "OPENSTATES_API_KEY not set. "
                "California scraping requires OpenStates for discovery. "
                "No mock fallback available in truth-critical paths."
            )

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            bills = await self._discover_bills(client)
            enriched_bills = []

            for bill in bills:
                try:
                    enriched = await self._fetch_canonical_text(client, bill)
                    enriched_bills.append(enriched)
                except Exception as e:
                    logger.error(
                        f"Failed to fetch canonical text for {bill.bill_number}: {e}"
                    )
                    provenance = BillSourceProvenance(
                        source_url=bill.provenance.source_url
                        if bill.provenance
                        else "",
                        source_type="leginfo",
                        version_identifier=bill.provenance.version_identifier
                        if bill.provenance
                        else "",
                        version_note="",
                        extraction_status="failed",
                        extraction_error=str(e),
                    )
                    bill.provenance = provenance
                    enriched_bills.append(bill)

            return enriched_bills

    async def _discover_bills(
        self, client: httpx.AsyncClient
    ) -> List[CaliforniaScrapedBill]:
        """
        Use OpenStates API for bill discovery and metadata.
        Does NOT extract bill text - only metadata.
        """
        api_key = self.api_key
        assert api_key is not None
        response = await client.get(
            f"{self.base_url}/bills",
            params={
                "jurisdiction": "ca",
                "session": "20252026",
                "per_page": 20,
                "sort": "updated_desc",
                "include": ["sponsor", "actions", "versions"],
            },
            headers={"X-API-KEY": api_key},
        )
        response.raise_for_status()
        data = response.json()

        bills = []
        for bill_meta in data.get("results", []):
            bill_id = bill_meta.get("id")

            detail_response = await client.get(
                f"{self.base_url}/bills/{bill_id}",
                params={"include": ["versions", "actions", "sources"]},
                headers={"X-API-KEY": api_key},
            )
            bill_detail = detail_response.json()

            versions = bill_detail.get("versions", [])
            openstates_sources = bill_detail.get("sources", [])

            source_url = self._extract_leginfo_url(versions, openstates_sources)
            version_info = versions[0] if versions else {}

            provenance = BillSourceProvenance(
                source_url=source_url,
                source_type="leginfo"
                if "leginfo.legislature.ca.gov" in source_url
                else "openstates",
                version_identifier=version_info.get("id", ""),
                version_note=version_info.get("note", ""),
                extraction_status="discovered",
            )

            bill = CaliforniaScrapedBill(
                bill_number=bill_meta.get("identifier", "Unknown"),
                title=bill_meta.get("title", "Untitled"),
                text="",
                introduced_date=self._parse_date(bill_meta.get("created_at")),
                status=bill_meta.get("latest_action_description", "Unknown"),
                raw_html=str(bill_detail),
                provenance=provenance,
                jurisdiction="california",
                source_system="openstates+leginfo",
            )

            bills.append(bill)

        logger.info(f"Discovered {len(bills)} California bills via OpenStates")
        return bills

    def _extract_leginfo_url(self, versions: List[Dict], sources: List[Dict]) -> str:
        """
        Extract the official California legislature URL from OpenStates version/sources.
        Prefers leginfo.legislature.ca.gov URLs.
        """
        for version in versions:
            for link in version.get("links", []):
                url = link.get("url", "")
                if "leginfo.legislature.ca.gov" in url:
                    return url
            if version.get("url", ""):
                url = version["url"]
                if "leginfo.legislature.ca.gov" in url:
                    return url

        for source in sources:
            url = source.get("url", "")
            if "leginfo.legislature.ca.gov" in url:
                return url

        if versions:
            for link in versions[0].get("links", []):
                if link.get("url"):
                    return link["url"]
            if versions[0].get("url"):
                return versions[0]["url"]

        if sources and sources[0].get("url"):
            return sources[0]["url"]

        return ""

    async def _fetch_canonical_text(
        self, client: httpx.AsyncClient, bill: CaliforniaScrapedBill
    ) -> CaliforniaScrapedBill:
        """
        Fetch canonical bill text from official California legislature source.

        Falls back to placeholder status if text cannot be extracted,
        but NEVER returns mock/fake text.
        """
        source_url = bill.provenance.source_url

        if not source_url:
            bill.provenance.extraction_status = "no_source_url"
            bill.provenance.extraction_error = "No official source URL found"
            return bill

        try:
            # Convert PDF/NavClient URLs to billTextClient URLs for text extraction
            fetch_url = source_url
            if "billPdf.xhtml" in source_url or "billNavClient.xhtml" in source_url:
                import urllib.parse as up

                parsed = up.urlparse(source_url)
                qs = up.parse_qs(parsed.query)
                bill_id = qs.get("bill_id", [None])[0]
                if bill_id:
                    fetch_url = f"{LEGISLATURE_BASE_URL}/faces/billTextClient.xhtml?bill_id={bill_id}"
                    logger.info(
                        f"Rewriting URL to billTextClient for {bill.bill_number}: {fetch_url}"
                    )

            response = await client.get(fetch_url, timeout=30.0)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if "application/pdf" in content_type:
                bill.provenance.source_type = "leginfo_pdf"
                bill.provenance.extraction_status = "pdf_requires_processing"
                bill.provenance.extraction_error = (
                    "PDF text extraction not yet implemented"
                )
                logger.warning(f"PDF source for {bill.bill_number}: {source_url}")
                return bill

            html_content = response.text
            bill_text = self._extract_text_from_html(html_content, bill.bill_number)

            if self._is_placeholder_text(bill_text):
                bill.provenance.extraction_status = "placeholder_detected"
                bill.provenance.extraction_error = (
                    f"Extracted text appears to be placeholder: {bill_text[:100]}"
                )
                bill.text = ""
                logger.warning(f"Placeholder text detected for {bill.bill_number}")
                return bill

            if bill_text and len(bill_text) > 100:
                bill.text = bill_text
                bill.provenance.extraction_status = "success"
                bill.provenance.content_hash = hashlib.sha256(
                    bill_text.encode("utf-8")
                ).hexdigest()
                bill.raw_html = html_content
                logger.info(
                    f"Successfully extracted {len(bill_text)} chars for {bill.bill_number}"
                )
            else:
                bill.provenance.extraction_status = "insufficient_text"
                bill.provenance.extraction_error = (
                    f"Extracted text too short: {len(bill_text)} chars"
                )
                bill.text = ""

            return bill

        except httpx.HTTPStatusError as e:
            bill.provenance.extraction_status = "http_error"
            bill.provenance.extraction_error = f"HTTP {e.response.status_code}"
            logger.error(f"HTTP error fetching {source_url}: {e}")
            return bill
        except Exception as e:
            bill.provenance.extraction_status = "fetch_error"
            bill.provenance.extraction_error = str(e)
            logger.error(f"Error fetching canonical text for {bill.bill_number}: {e}")
            return bill

    _NAV_ELEMENTS = re.compile(
        r"<(nav|header|footer|aside)[^>]*>.*?</\1>",
        re.DOTALL | re.IGNORECASE,
    )
    _BOILERPLATE_CSS = [
        "navigation",
        "navbar",
        "nav-bar",
        "menu",
        "skipnav",
        "breadcrumb",
        "footer",
        "header",
        "banner",
        "skip-link",
    ]

    def _strip_boilerplate(self, html: str) -> str:
        html = self._NAV_ELEMENTS.sub("", html)
        for css_class in self._BOILERPLATE_CSS:
            html = re.sub(
                rf'<[^>]*class="[^"]*\b{css_class}\b[^"]*"[^>]*>.*?</[^>]+>',
                "",
                html,
                flags=re.DOTALL | re.IGNORECASE,
            )
        html = re.sub(
            r'<[^>]*id="[^"]*\b(nav|header|footer|menu)\b[^"]*"[^>]*>.*?</[^>]+>',
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        return html

    def _extract_text_from_html(self, html: str, bill_number: str) -> str:
        """
        Extract bill text from California legislature HTML.

        California leginfo bill text pages typically use:
        - <div class="billText">...</div> or similar bill-text containers
        - The actual text starts with legislative enacting clause like
          'THE PEOPLE OF THE STATE OF CALIFORNIA DO ENACT AS FOLLOWS'

        Falls back to body content ONLY after stripping nav/header chrome.
        """
        cleaned = self._strip_boilerplate(html)

        patterns = [
            r'<div[^>]*class="[^"]*billText[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="[^"]*bill_text[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*bill_text[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<td[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</td>',
            r"<main[^>]*>(.*?)</main>",
        ]

        extracted = ""
        for pattern in patterns:
            match = re.search(pattern, cleaned, re.DOTALL | re.IGNORECASE)
            if match:
                extracted = match.group(1)
                break

        if not extracted:
            # Try bill text markers BEFORE body fallback
            bill_marker = re.search(
                r"(?:THE\s+PEOPLE\s+OF\s+THE\s+STATE\s+OF\s+CALIFORNIA|enact\s+as\s+follows)",
                cleaned,
                re.IGNORECASE,
            )
            if bill_marker:
                extracted = cleaned[bill_marker.start() :]

        if not extracted:
            body_match = re.search(
                r"<body[^>]*>(.*?)</body>", cleaned, re.DOTALL | re.IGNORECASE
            )
            if body_match:
                extracted = body_match.group(1)

        text = re.sub(
            r"<script[^>]*>.*?</script>", "", extracted, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(
            r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        if self._is_header_chrome(text):
            return ""

        return text

    def _is_header_chrome(self, text: str) -> bool:
        """
        Detect header/navigation chrome instead of real bill text.

        California leginfo pages may return navigation text, breadcrumb trails,
        or site chrome when the bill-text container is empty or misidentified.
        """
        if not text:
            return True

        # If text contains bill content markers, it's not chrome
        bill_markers = [
            r"(?i)THE\s+PEOPLE\s+OF\s+THE\s+STATE",
            r"(?i)enact\s+as\s+follows",
            r"(?i)SECTION\s+1\.",
            r"(?i)SEC\.\s+1\.",
            r"(?i)added\s+to\s+(the\s+)?(?:Penal|Health|Education|Government|Business|Civil|Code)",
        ]
        for pattern in bill_markers:
            if re.search(pattern, text):
                return False

        chrome_indicators = [
            r"(?i)^[A-Z\s]{5,}$",
            r"(?i)^(home|my\s+subscription|help|about|contact)",
            r"(?i)^(sign\s+in|log\s+in|register|search)",
            r"(?i)^( california|legislature|leginfo)\s*$",
            r"(?i)bill\s+number\s*:\s*$",
            r"(?i)^(session|house|senate|assembly)\s*$",
            r"(?i)^(navigation|menu|skip\s+to\s+content)",
            r"(?i)^(legislative\s+(counsel|information|data))",
        ]

        first_line = text.split(".")[0].strip() if text else ""
        for pattern in chrome_indicators:
            if re.match(pattern, first_line):
                return True

        return False

    def _is_placeholder_text(self, text: str) -> bool:
        """
        Check if the extracted text is a placeholder rather than real bill text.

        Known placeholders from OpenStates versions[].note:
        - "Introduced"
        - "Amended"
        - "Enrolled"
        - "Chaptered"
        """
        if not text:
            return True

        text_lower = text.strip().lower()

        placeholder_patterns = [
            r"^introduced\.?$",
            r"^amended\.?$",
            r"^enrolled\.?$",
            r"^chaptered\.?$",
            r"^pending$",
            r"^\d{1,4}$",
        ]

        for pattern in placeholder_patterns:
            if re.match(pattern, text_lower):
                return True

        if len(text) < 50 and not any(c.isdigit() for c in text):
            return True

        return False

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except (ValueError, AttributeError):
            return None

    async def scrape_specific_bills(
        self, bill_numbers: List[str]
    ) -> List[CaliforniaScrapedBill]:
        """
        Scrape specific bills by bill number (e.g., "SB 277", "ACR 117").

        Used for targeted re-ingestion of anchor bills.
        """
        if not self.api_key:
            raise RuntimeError(
                "OPENSTATES_API_KEY not set. "
                "California scraping requires OpenStates for discovery."
            )

        api_key = self.api_key

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            bills = []

            for bill_number in bill_numbers:
                normalized = self._normalize_bill_number(bill_number)

                try:
                    response = await client.get(
                        f"{self.base_url}/bills",
                        params={
                            "jurisdiction": "ca",
                            "session": "20252026",
                            "identifier": normalized,
                            "include": ["versions", "actions", "sources"],
                        },
                        headers={"X-API-KEY": api_key},
                    )
                    response.raise_for_status()
                    data = response.json()

                    results = data.get("results", [])
                    if not results:
                        logger.warning(f"Bill {bill_number} not found in OpenStates")
                        continue

                    bill_meta = results[0]
                    bill_id = bill_meta.get("id")

                    detail_response = await client.get(
                        f"{self.base_url}/bills/{bill_id}",
                        params={"include": ["versions", "actions", "sources"]},
                        headers={"X-API-KEY": api_key},
                    )
                    bill_detail = detail_response.json()

                    versions = bill_detail.get("versions", [])
                    sources = bill_detail.get("sources", [])
                    source_url = self._extract_leginfo_url(versions, sources)
                    version_info = versions[0] if versions else {}

                    provenance = BillSourceProvenance(
                        source_url=source_url,
                        source_type="leginfo"
                        if "leginfo.legislature.ca.gov" in source_url
                        else "openstates",
                        version_identifier=version_info.get("id", ""),
                        version_note=version_info.get("note", ""),
                        extraction_status="discovered",
                    )

                    bill = CaliforniaScrapedBill(
                        bill_number=bill_meta.get("identifier", bill_number),
                        title=bill_meta.get("title", "Untitled"),
                        text="",
                        introduced_date=self._parse_date(bill_meta.get("created_at")),
                        status=bill_meta.get("latest_action_description", "Unknown"),
                        raw_html=str(bill_detail),
                        provenance=provenance,
                        jurisdiction="california",
                        source_system="openstates+leginfo",
                    )

                    enriched = await self._fetch_canonical_text(client, bill)
                    bills.append(enriched)

                except Exception as e:
                    logger.error(f"Failed to scrape {bill_number}: {e}")

            return bills

    def _normalize_bill_number(self, bill_number: str) -> str:
        """Normalize bill number for API queries."""
        return bill_number.strip().upper()

    def to_raw_scrape_record(
        self, bill: CaliforniaScrapedBill, source_id: str
    ) -> Dict[str, Any]:
        """
        Convert a scraped bill to a raw_scrape record for ingestion.

        This method produces the data structure expected by
        PostgresDB.create_raw_scrape() and IngestionService.process_raw_scrape().
        """
        bill_text = bill.text or ""
        content_hash = hashlib.sha256(bill_text.encode("utf-8")).hexdigest()

        metadata = {
            "bill_number": bill.bill_number,
            "title": bill.title,
            "status": bill.status,
            "jurisdiction": bill.jurisdiction,
            "source_system": bill.source_system,
            "extraction_status": bill.provenance.extraction_status,
            "source_url": bill.provenance.source_url,
            "source_type": bill.provenance.source_type,
            "version_identifier": bill.provenance.version_identifier,
            "version_note": bill.provenance.version_note,
            "content_hash": bill.provenance.content_hash,
        }

        if bill.provenance.extraction_error:
            metadata["extraction_error"] = bill.provenance.extraction_error

        if bill.introduced_date:
            metadata["introduced_date"] = bill.introduced_date.isoformat()

        data_payload = {
            "content": bill_text,
            "bill_number": bill.bill_number,
            "title": bill.title,
            "status": bill.status,
            "raw_html": bill.raw_html,
            "provenance": {
                "source_url": bill.provenance.source_url,
                "source_type": bill.provenance.source_type,
                "version_identifier": bill.provenance.version_identifier,
                "version_note": bill.provenance.version_note,
                "extraction_status": bill.provenance.extraction_status,
                "extraction_error": bill.provenance.extraction_error,
                "content_hash": bill.provenance.content_hash,
            },
        }

        return {
            "source_id": source_id,
            "url": bill.provenance.source_url or f"california://{bill.bill_number}",
            "content_hash": content_hash,
            "content_type": "text/html",
            "data": data_payload,
            "metadata": metadata,
        }
