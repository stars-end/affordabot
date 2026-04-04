import pytest

from scripts.substrate.expand_legistar_source_inventory import extract_legistar_document_sources
from scripts.substrate.expand_legistar_source_inventory import normalize_jurisdiction_name
from scripts.substrate.expand_legistar_source_inventory import _resolve_jurisdiction_id


def test_extract_legistar_document_sources_returns_agenda_and_minutes_links() -> None:
    html = """
    <table class="rgMasterTable">
      <tr class="rgRow">
        <td><a id="ctl00_grid_ctl04_hypName">City Council</a></td>
        <td>04/07/2026</td>
        <td><a id="ctl00_grid_ctl04_hypAgenda" href="View.ashx?M=A&ID=123">Agenda</a></td>
        <td><a id="ctl00_grid_ctl04_hypMinutes" href="View.ashx?M=M&ID=123">Minutes</a></td>
      </tr>
      <tr class="rgAltRow">
        <td><a id="ctl00_grid_ctl06_hypName">Planning Commission</a></td>
        <td>04/08/2026</td>
        <td><a id="ctl00_grid_ctl06_hypAgenda" class="meetingAgendaNotAvailbleLink">Not&nbsp;available</a></td>
        <td><a id="ctl00_grid_ctl06_hypMinutes" class="otherNotAvaiableMinutes">Not&nbsp;available</a></td>
      </tr>
    </table>
    """

    rows = extract_legistar_document_sources(
        calendar_html=html,
        calendar_url="https://example.legistar.com/Calendar.aspx",
        jurisdiction_name="Sample City",
    )

    assert rows == [
        {
            "url": "https://example.legistar.com/View.ashx?M=A&ID=123",
            "source_name": "Sample City - City Council - Agenda - 04/07/2026",
            "document_type": "agenda",
            "meeting_name": "City Council",
            "meeting_date": "04/07/2026",
        },
        {
            "url": "https://example.legistar.com/View.ashx?M=M&ID=123",
            "source_name": "Sample City - City Council - Minutes - 04/07/2026",
            "document_type": "minutes",
            "meeting_name": "City Council",
            "meeting_date": "04/07/2026",
        },
    ]


def test_normalize_jurisdiction_name_strips_city_and_county_prefixes() -> None:
    assert normalize_jurisdiction_name("City of San Jose") == "san jose"
    assert normalize_jurisdiction_name("County of San Mateo") == "san mateo"
    assert normalize_jurisdiction_name("Mountain View") == "mountain view"


@pytest.mark.asyncio
async def test_resolve_jurisdiction_id_uses_normalized_name_fallback() -> None:
    class FakeDB:
        async def _fetchrow(self, query, *args):
            return None

        async def _fetch(self, query, *args):
            return [
                {"id": "abc-123", "name": "City of San Jose"},
                {"id": "def-456", "name": "City of Sunnyvale"},
            ]

    jurisdiction_id = await _resolve_jurisdiction_id(
        FakeDB(),
        jurisdiction_name="San Jose",
        jurisdiction_type="city",
    )

    assert jurisdiction_id == "abc-123"
