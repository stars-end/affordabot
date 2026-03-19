"""
Tests for California State Legislature Scraper (bd-tytc.3).

Validates:
- No mock fallback in truth-critical paths
- Placeholder text detection
- Provenance capture
- Raw scrape record generation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.scraper.california_state import (
    CaliforniaStateScraper,
    CaliforniaScrapedBill,
    BillSourceProvenance,
)


class TestCaliforniaScraperNoMockFallback:
    """Test that California scraper fails closed without API key."""

    def test_init_without_api_key(self):
        """Scraper should initialize but not be usable without API key."""
        with patch.dict("os.environ", {}, clear=True):
            scraper = CaliforniaStateScraper()
            assert scraper.api_key is None

    @pytest.mark.asyncio
    async def test_scrape_raises_without_api_key(self):
        """Scraping without API key should raise RuntimeError, not return mock data."""
        with patch.dict("os.environ", {}, clear=True):
            scraper = CaliforniaStateScraper()

            with pytest.raises(RuntimeError) as exc_info:
                await scraper.scrape()

            assert "OPENSTATES_API_KEY" in str(exc_info.value)
            assert "No mock fallback" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_scrape_specific_bills_raises_without_api_key(self):
        """Targeted scraping without API key should raise RuntimeError."""
        with patch.dict("os.environ", {}, clear=True):
            scraper = CaliforniaStateScraper()

            with pytest.raises(RuntimeError) as exc_info:
                await scraper.scrape_specific_bills(["SB 277"])

            assert "OPENSTATES_API_KEY" in str(exc_info.value)


class TestPlaceholderDetection:
    """Test that placeholder text is correctly identified."""

    def test_detects_introduced_placeholder(self):
        """'Introduced' should be detected as placeholder."""
        scraper = CaliforniaStateScraper()
        assert scraper._is_placeholder_text("Introduced") is True
        assert scraper._is_placeholder_text("introduced.") is True
        assert scraper._is_placeholder_text("INTRODUCED") is True

    def test_detects_amended_placeholder(self):
        """'Amended' should be detected as placeholder."""
        scraper = CaliforniaStateScraper()
        assert scraper._is_placeholder_text("Amended") is True
        assert scraper._is_placeholder_text("amended.") is True

    def test_detects_enrolled_placeholder(self):
        """'Enrolled' should be detected as placeholder."""
        scraper = CaliforniaStateScraper()
        assert scraper._is_placeholder_text("Enrolled") is True

    def test_detects_chaptered_placeholder(self):
        """'Chaptered' should be detected as placeholder."""
        scraper = CaliforniaStateScraper()
        assert scraper._is_placeholder_text("Chaptered") is True

    def test_detects_short_text_without_numbers(self):
        """Short text without any numbers should be treated as placeholder."""
        scraper = CaliforniaStateScraper()
        assert scraper._is_placeholder_text("Pending Action") is True
        assert scraper._is_placeholder_text("Review") is True

    def test_accepts_real_bill_text(self):
        """Real bill text should NOT be detected as placeholder."""
        scraper = CaliforniaStateScraper()

        real_text = """
        THE PEOPLE OF THE STATE OF CALIFORNIA DO ENACT AS FOLLOWS:
        SECTION 1. Section 1234 of the Health and Safety Code is amended.
        (a) The department shall establish a program with an appropriation 
        of $5,000,000 for housing affordability initiatives.
        """

        assert scraper._is_placeholder_text(real_text) is False

    def test_accepts_text_with_numbers(self):
        """Text with numbers (dollar amounts, section numbers) is real content."""
        scraper = CaliforniaStateScraper()
        assert (
            scraper._is_placeholder_text("Section 123. The sum of $1,000,000") is False
        )


class TestProvenanceCapture:
    """Test that source provenance is correctly captured."""

    def test_provenance_dataclass_defaults(self):
        """BillSourceProvenance should have sensible defaults."""
        prov = BillSourceProvenance(
            source_url="https://example.com",
            source_type="leginfo",
            version_identifier="v1",
            version_note="",
            extraction_status="pending",
        )

        assert prov.extraction_error is None
        assert prov.content_hash is None

    def test_california_scraped_bill_has_provenance(self):
        """CaliforniaScrapedBill should have provenance and jurisdiction."""
        prov = BillSourceProvenance(
            source_url="https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260SB277",
            source_type="leginfo",
            version_identifier="v1",
            version_note="Introduced",
            extraction_status="success",
        )

        bill = CaliforniaScrapedBill(
            bill_number="SB 277",
            title="An act relating to housing",
            text="The people of California...",
            provenance=prov,
        )

        assert bill.jurisdiction == "california"
        assert bill.source_system == "openstates+leginfo"
        assert bill.provenance.source_type == "leginfo"
        assert bill.provenance.extraction_status == "success"


class TestRawScrapeRecord:
    """Test conversion to raw_scrape record format."""

    def test_to_raw_scrape_record_includes_metadata(self):
        """Raw scrape record should include jurisdiction/source metadata."""
        scraper = CaliforniaStateScraper()

        prov = BillSourceProvenance(
            source_url="https://leginfo.legislature.ca.gov/test",
            source_type="leginfo",
            version_identifier="v1",
            version_note="Introduced",
            extraction_status="success",
            content_hash="abc123",
        )

        bill = CaliforniaScrapedBill(
            bill_number="SB 277",
            title="Test Bill",
            text="Real bill text here",
            provenance=prov,
        )

        record = scraper.to_raw_scrape_record(bill, source_id="source-uuid-123")

        assert record["source_id"] == "source-uuid-123"
        assert record["metadata"]["jurisdiction"] == "california"
        assert record["metadata"]["source_system"] == "openstates+leginfo"
        assert record["metadata"]["bill_number"] == "SB 277"
        assert record["metadata"]["extraction_status"] == "success"
        assert record["metadata"]["source_type"] == "leginfo"
        assert record["data"]["content"] == "Real bill text here"
        assert (
            record["data"]["provenance"]["source_url"]
            == "https://leginfo.legislature.ca.gov/test"
        )


class TestExtractLeginfoUrl:
    """Test extraction of official California legislature URLs."""

    def test_extracts_leginfo_url_from_versions(self):
        """Should extract leginfo URL from version links."""
        scraper = CaliforniaStateScraper()

        versions = [
            {
                "links": [
                    {
                        "url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260SB277"
                    }
                ]
            }
        ]
        sources = []

        url = scraper._extract_leginfo_url(versions, sources)

        assert "leginfo.legislature.ca.gov" in url
        assert "SB277" in url

    def test_extracts_leginfo_url_from_sources(self):
        """Should extract leginfo URL from sources if not in versions."""
        scraper = CaliforniaStateScraper()

        versions = [{"links": [{"url": "https://other.com"}]}]
        sources = [
            {
                "url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260ACR117"
            }
        ]

        url = scraper._extract_leginfo_url(versions, sources)

        assert "leginfo.legislature.ca.gov" in url
        assert "ACR117" in url

    def test_returns_empty_if_no_urls(self):
        """Should return empty string if no URLs found."""
        scraper = CaliforniaStateScraper()

        versions = []
        sources = []

        url = scraper._extract_leginfo_url(versions, sources)

        assert url == ""
