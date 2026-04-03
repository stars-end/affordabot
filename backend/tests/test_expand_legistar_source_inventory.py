from scripts.substrate.expand_legistar_source_inventory import extract_legistar_document_sources


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
