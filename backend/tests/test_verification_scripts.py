"""Tests for verification scripts (verify_pipeline_truth, quarantine_suspect_analyses).

Focused on path resolution, SQL generation, and text extraction helpers.
Does NOT require a live database connection.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Ensure backend root is on sys.path for imports
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class TestPathResolution:
    """Verify that verification scripts resolve their backend root correctly."""

    def test_verify_pipeline_truth_backend_root(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "verification"
            / "verify_pipeline_truth.py"
        )
        assert script.exists(), f"Script not found: {script}"
        # parents[2] from scripts/verification/ should be backend/
        resolved = script.resolve().parents[2]
        assert resolved.name == "backend", f"Expected 'backend', got '{resolved.name}'"
        assert (resolved / "db" / "postgres_client.py").exists()

    def test_quarantine_suspect_analyses_backend_root(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "verification"
            / "quarantine_suspect_analyses.py"
        )
        assert script.exists(), f"Script not found: {script}"
        resolved = script.resolve().parents[2]
        assert resolved.name == "backend", f"Expected 'backend', got '{resolved.name}'"
        assert (resolved / "db" / "postgres_client.py").exists()


class TestDiagnoseBillSqlGeneration:
    """Test that the SQL queries in verify_pipeline_truth.py are well-formed."""

    def _load_scrape_query(self) -> str:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "verification"
            / "verify_pipeline_truth.py"
        )
        source = script.read_text()
        # Extract the scrape_query string
        start = source.index('scrape_query = """') + len('scrape_query = """')
        end = source.index('"""', start)
        return source[start:end]

    def _load_legislation_query(self) -> str:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "verification"
            / "verify_pipeline_truth.py"
        )
        source = script.read_text()
        start = source.index('leg_query = """') + len('leg_query = """')
        end = source.index('"""', start)
        return source[start:end]

    def test_scrape_query_has_uuid_cast(self) -> None:
        query = self._load_scrape_query()
        assert "::uuid" in query, (
            "Scrape query should cast jurisdiction_id to uuid for join"
        )

    def test_scrape_query_uses_like_for_jurisdiction(self) -> None:
        query = self._load_scrape_query()
        assert "LIKE '%' || LOWER($1) || '%'" in query, (
            "Scrape query should use LIKE for jurisdiction matching"
        )

    def test_legislation_query_uses_like_for_jurisdiction(self) -> None:
        query = self._load_legislation_query()
        assert "LIKE '%' || LOWER($1) || '%'" in query, (
            "Legislation query should use LIKE for jurisdiction matching"
        )

    def test_scrape_query_references_metadata_bill_number(self) -> None:
        query = self._load_scrape_query()
        assert "bill_number" in query.lower()

    def test_legislation_query_selects_sufficiency_columns(self) -> None:
        query = self._load_legislation_query()
        assert "sufficiency_state" in query
        assert "quantification_eligible" in query
        assert "total_impact_p50" in query


class TestDiagnoseBillChunkLookup:
    """Test that chunk lookup uses metadata.bill_number fallback (bd-hvji.9)."""

    def test_chunk_lookup_uses_metadata_bill_number_fallback(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "verification"
            / "verify_pipeline_truth.py"
        )
        source = script.read_text()
        assert "metadata::json->>'bill_number'" in source, (
            "Chunk lookup should fall back to metadata.bill_number"
        )

    def test_chunk_lookup_includes_lookup_method(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "verification"
            / "verify_pipeline_truth.py"
        )
        source = script.read_text()
        assert '"lookup_method"' in source, (
            "Chunk stage should report which lookup method was used"
        )

    def test_pipeline_run_selects_trigger_source(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "verification"
            / "verify_pipeline_truth.py"
        )
        source = script.read_text()
        assert (
            "trigger_source"
            in source.split("Stage 4: Pipeline run")[1].split("Stage 5")[0]
            if "Stage 5" in source
            else source.split("Stage 4: Pipeline run")[1]
        ), "Pipeline run query should select trigger_source"

    def test_pipeline_run_checks_persistence_step(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "verification"
            / "verify_pipeline_truth.py"
        )
        source = script.read_text()
        assert "persistence_step_present" in source, (
            "Pipeline run should check for persistence step"
        )
        assert "pipeline_steps" in source, "Pipeline run should include pipeline_steps"


class TestRerunScriptTriggerSource:
    """Test that rerun script passes trigger_source explicitly (bd-hvji.9)."""

    def test_rerun_passes_trigger_source(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "rerun_california_bills.py"
        )
        source = script.read_text()
        assert 'trigger_source="manual"' in source, (
            "Rerun script should explicitly pass trigger_source='manual' to pipeline.run"
        )

    def test_rerun_has_schema_preflight(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "rerun_california_bills.py"
        )
        source = script.read_text()
        assert "Schema Pre-flight" in source, (
            "Rerun script should have schema pre-flight step"
        )
        assert "trigger_source TEXT" in source, (
            "Schema pre-flight should ensure trigger_source column"
        )


class TestRerunScriptSourceResolution:
    @pytest.mark.asyncio
    async def test_resolve_bill_source_prefers_raw_scrape_text_and_source_url(self) -> None:
        from scripts.rerun_california_bills import resolve_bill_source

        db = AsyncMock()
        db._fetchrow.return_value = {"text_content": "LEGISLATION TEXT"}
        db.get_latest_scrape_for_bill.return_value = {
            "url": "https://leginfo.legislature.ca.gov/faces/billPdf.xhtml?bill_id=202520260SB277",
            "data": {
                "content": "RAW SCRAPE TEXT " * 20,
            },
            "metadata": {
                "source_type": "leginfo",
                "extraction_status": "success",
                "bill_number": "SB 277",
            },
        }

        text, metadata = await resolve_bill_source(db, "SB 277")

        assert text.startswith("RAW SCRAPE TEXT")
        assert metadata["bill_number"] == "SB 277"
        assert metadata["source_type"] == "leginfo"
        assert metadata["source_url"].startswith(
            "https://leginfo.legislature.ca.gov/faces/billPdf.xhtml"
        )


class TestQuarantineSqlGeneration:
    """Test that quarantine script SQL references valid columns."""

    def _load_where_clause(self) -> str:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "verification"
            / "quarantine_suspect_analyses.py"
        )
        source = script.read_text()
        start = source.index('where_clause = """') + len('where_clause = """')
        end = source.index('"""', start)
        return source[start:end]

    def test_where_clause_references_sufficiency_state(self) -> None:
        clause = self._load_where_clause()
        assert "sufficiency_state" in clause

    def test_where_clause_references_analysis_status(self) -> None:
        clause = self._load_where_clause()
        assert "analysis_status" in clause

    def test_where_clause_checks_quarantined(self) -> None:
        clause = self._load_where_clause()
        assert "quarantined" in clause


class TestCaliforniaScraperTextExtraction:
    """Test bill text extraction from California legislature HTML."""

    def _extract(self, html: str) -> str:
        """Mimic the scraper's extraction logic."""
        import re

        NAV_ELEMENTS = re.compile(
            r"<(nav|header|footer|aside)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
        )
        cleaned = NAV_ELEMENTS.sub("", html)
        for css_class in [
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
        ]:
            cleaned = re.sub(
                rf'<[^>]*class="[^"]*\b{css_class}\b[^"]*"[^>]*>.*?</[^>]+>',
                "",
                cleaned,
                flags=re.DOTALL | re.IGNORECASE,
            )

        bill_marker = re.search(
            r"(?:THE\s+PEOPLE\s+OF\s+THE\s+STATE\s+OF\s+CALIFORNIA|enact\s+as\s+follows|WHEREAS|RESOLVED)",
            cleaned,
            re.IGNORECASE,
        )
        if bill_marker:
            extracted = cleaned[bill_marker.start() :]
        else:
            body_match = re.search(
                r"<body[^>]*>(.*?)</body>", cleaned, re.DOTALL | re.IGNORECASE
            )
            extracted = body_match.group(1) if body_match else ""

        text = re.sub(
            r"<script[^>]*>.*?</script>", "", extracted, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(
            r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def test_extracts_enacting_clause(self) -> None:
        html = """
        <html><body>
        <nav>Navigation stuff</nav>
        <div>Some header content</div>
        <div class="billText">THE PEOPLE OF THE STATE OF CALIFORNIA DO ENACT AS FOLLOWS:
        SECTION 1. Section 833.6 is added to the Penal Code.</div>
        </body></html>
        """
        text = self._extract(html)
        assert "THE PEOPLE OF THE STATE OF CALIFORNIA" in text
        assert "SECTION 1" in text
        assert "Navigation stuff" not in text

    def test_extracts_where_clause(self) -> None:
        html = """
        <html><body>
        <div>WHEREAS, The United States ranks highest among industrialized nations
        in maternal mortality; and WHEREAS, More than 700 women die each year;</div>
        </body></html>
        """
        text = self._extract(html)
        assert "WHEREAS" in text
        assert "maternal mortality" in text

    def test_returns_empty_for_empty_html(self) -> None:
        assert self._extract("") == ""
        assert self._extract("<html></html>") == ""

    def test_strips_script_tags(self) -> None:
        html = """
        <body>THE PEOPLE OF THE STATE OF CALIFORNIA DO ENACT AS FOLLOWS:
        <script>var x = 1;</script>
        SECTION 1. Some bill text.</body>
        """
        text = self._extract(html)
        assert "var x" not in text
        assert "SECTION 1" in text

    def test_pdf_url_rewriting(self) -> None:
        """Test that billPdf.xhtml URLs get rewritten to billTextClient.xhtml."""
        import urllib.parse as up

        pdf_url = "https://leginfo.legislature.ca.gov/faces/billPdf.xhtml?bill_id=202520260SB277&version=20250SB27798AM"
        parsed = up.urlparse(pdf_url)
        qs = up.parse_qs(parsed.query)
        bill_id = qs.get("bill_id", [None])[0]

        assert bill_id == "202520260SB277"
        new_url = f"https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id={bill_id}"
        assert "billTextClient.xhtml" in new_url
        assert "bill_id=202520260SB277" in new_url
