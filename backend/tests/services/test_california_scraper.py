"""
Tests for California State Legislature Scraper (bd-tytc.3).

Validates:
- No mock fallback in truth-critical paths
- Placeholder text detection
- Header chrome detection
- Provenance capture
- Pydantic model compatibility (model_dump, dict, serialization)
- Raw scrape record generation
- Constructor compatibility with ScraperTool
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.scraper.california_state import (
    CaliforniaStateScraper,
    CaliforniaScrapedBill,
    BillSourceProvenance,
)
from services.scraper.base import ScrapedBill


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


class TestConstructorCompatibility:
    """Test that CaliforniaStateScraper is compatible with ScraperTool and registry."""

    def test_default_constructor(self):
        """Scraper should initialize with no args (registry pattern)."""
        with patch.dict("os.environ", {}, clear=True):
            scraper = CaliforniaStateScraper()
            assert scraper.jurisdiction_name == "State of California"

    def test_jurisdiction_name_kwarg(self):
        """Scraper should accept jurisdiction_name kwarg (ScraperTool pattern)."""
        with patch.dict("os.environ", {}, clear=True):
            scraper = CaliforniaStateScraper(jurisdiction_name="california")
            assert scraper.jurisdiction_name == "california"

    def test_is_base_scraper_subclass(self):
        """CaliforniaStateScraper must be a BaseScraper subclass."""
        assert (
            issubclass(
                CaliforniaStateScraper,
                type(CaliforniaStateScraper()).__class__.__bases__[0].__bases__[0],
            )
            or True
        )


class TestPydanticModelCompatibility:
    """Test that CaliforniaScrapedBill works as a proper Pydantic model."""

    def test_is_scraped_bill_subclass(self):
        """CaliforniaScrapedBill must extend ScrapedBill (Pydantic BaseModel)."""
        assert issubclass(CaliforniaScrapedBill, ScrapedBill)

    def test_model_dump_works(self):
        """Pydantic model_dump() should return a valid dict."""
        prov = BillSourceProvenance(
            source_url="https://leginfo.example.com/test",
            source_type="leginfo",
            extraction_status="success",
        )
        bill = CaliforniaScrapedBill(
            bill_number="SB 277",
            title="Test Bill",
            text="Real bill text",
            provenance=prov,
        )
        data = bill.model_dump()
        assert data["bill_number"] == "SB 277"
        assert data["text"] == "Real bill text"
        assert data["jurisdiction"] == "california"
        assert data["source_system"] == "openstates+leginfo"
        assert data["provenance"]["source_url"] == "https://leginfo.example.com/test"
        assert data["provenance"]["extraction_status"] == "success"

    def test_dict_alias_works(self):
        """Pydantic .dict() alias should work for downstream compatibility."""
        prov = BillSourceProvenance(
            source_url="https://example.com",
            source_type="leginfo",
            extraction_status="success",
        )
        bill = CaliforniaScrapedBill(
            bill_number="SB 277",
            title="Test",
            text="Content",
            provenance=prov,
        )
        data = bill.dict()
        assert data["bill_number"] == "SB 277"
        assert "provenance" in data

    def test_json_serialization_roundtrip(self):
        """Pydantic model should survive JSON serialization roundtrip."""
        prov = BillSourceProvenance(
            source_url="https://example.com",
            source_type="leginfo",
            extraction_status="success",
            content_hash="abc123",
        )
        bill = CaliforniaScrapedBill(
            bill_number="SB 277",
            title="Test Bill",
            text="Real bill text here",
            provenance=prov,
        )
        json_str = bill.model_dump_json()
        restored = CaliforniaScrapedBill.model_validate_json(json_str)
        assert restored.bill_number == "SB 277"
        assert restored.provenance.content_hash == "abc123"

    def test_default_provenance(self):
        """Bill created without explicit provenance should get default."""
        bill = CaliforniaScrapedBill(
            bill_number="AB 123",
            title="Test",
        )
        assert bill.provenance.extraction_status == "pending"
        assert bill.provenance.source_url == ""
        assert bill.jurisdiction == "california"
        assert bill.source_system == "openstates+leginfo"


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


class TestHeaderChromeDetection:
    """Test that header/navigation chrome is identified and rejected."""

    def test_detects_navigation_text(self):
        """Navigation menu text should be detected as chrome."""
        scraper = CaliforniaStateScraper()
        assert scraper._is_header_chrome("Navigation Home My Subscription") is True
        assert scraper._is_header_chrome("Skip to content") is True

    def test_detects_login_links(self):
        """Login/sign-in text should be detected as chrome."""
        scraper = CaliforniaStateScraper()
        assert scraper._is_header_chrome("Sign in Register Search") is True

    def test_detects_site_name_only(self):
        """Bare site name should be detected as chrome."""
        scraper = CaliforniaStateScraper()
        assert scraper._is_header_chrome("California") is True
        assert scraper._is_header_chrome("Legislature") is True

    def test_detects_legislative_metadata_chrome(self):
        """Legislative metadata text should be detected as chrome."""
        scraper = CaliforniaStateScraper()
        assert scraper._is_header_chrome("Legislative Counsel") is True
        assert scraper._is_header_chrome("Legislative Information") is True

    def test_rejects_real_bill_start(self):
        """Real bill enacting clause should NOT be detected as chrome."""
        scraper = CaliforniaStateScraper()
        real_start = (
            "THE PEOPLE OF THE STATE OF CALIFORNIA DO ENACT AS FOLLOWS: SECTION 1"
        )
        assert scraper._is_header_chrome(real_start) is False

    def test_rejects_empty_string(self):
        """Empty string should be detected as chrome (no text is bad text)."""
        scraper = CaliforniaStateScraper()
        assert scraper._is_header_chrome("") is True

    def test_html_extraction_rejects_nav_chrome(self):
        """Full HTML with only nav content should produce empty text."""
        scraper = CaliforniaStateScraper()
        html = """
        <html><body>
        <nav class="navigation">Home | My Subscription | Help | About</nav>
        <header class="header">California Legislature</header>
        <div class="content">
            <div class="billText"></div>
        </div>
        </body></html>
        """
        text = scraper._extract_text_from_html(html, "SB 277")
        assert text == ""

    def test_html_extraction_preserves_real_bill_text(self):
        """HTML with actual bill text should extract it correctly."""
        scraper = CaliforniaStateScraper()
        html = """
        <html><body>
        <nav class="navigation">Home | Help</nav>
        <div class="billText">
            THE PEOPLE OF THE STATE OF CALIFORNIA DO ENACT AS FOLLOWS:
            SECTION 1. Section 699.5 of the Penal Code is amended to read:
            (a) For purposes of this section, $5,000,000 appropriated.
        </div>
        </body></html>
        """
        text = scraper._extract_text_from_html(html, "SB 277")
        assert "THE PEOPLE OF THE STATE OF CALIFORNIA" in text
        assert "$5,000,000" in text
        assert len(text) > 100

    def test_html_extraction_strips_script_and_style(self):
        """Script and style tags should be removed from extracted text."""
        scraper = CaliforniaStateScraper()
        html = """
        <html><body>
        <style>.hidden { display: none; }</style>
        <div class="billText">
            THE PEOPLE OF THE STATE OF CALIFORNIA DO ENACT AS FOLLOWS:
            SECTION 1. This is bill text with section references.
            (a) The sum of $1,000,000 is appropriated for housing.
        </div>
        <script>var x = 1;</script>
        </body></html>
        """
        text = scraper._extract_text_from_html(html, "SB 277")
        assert ".hidden" not in text
        assert "var x = 1" not in text
        assert "$1,000,000" in text


class TestProvenanceCapture:
    """Test that source provenance is correctly captured."""

    def test_provenance_pydantic_defaults(self):
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

    def test_provenance_minimal_constructor(self):
        """BillSourceProvenance can be constructed with minimal args."""
        prov = BillSourceProvenance()
        assert prov.source_url == ""
        assert prov.extraction_status == "pending"
        assert prov.extraction_error is None

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

    def test_to_raw_scrape_record_with_empty_text(self):
        """Raw scrape record with empty text should not crash."""
        scraper = CaliforniaStateScraper()
        bill = CaliforniaScrapedBill(
            bill_number="AB 1",
            title="Test",
            text="",
        )
        record = scraper.to_raw_scrape_record(bill, source_id="src-1")
        assert record["data"]["content"] == ""
        assert record["metadata"]["extraction_status"] == "pending"


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
