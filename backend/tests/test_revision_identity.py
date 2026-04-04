from services.revision_identity import build_canonical_document_key
from services.revision_identity import build_revision_seed


def test_build_canonical_document_key_normalizes_url_inputs() -> None:
    key = build_canonical_document_key(
        source_id="1234",
        url="https://City.gov/Meetings/Agenda/?utm_source=email&b=2&a=1#download",
        metadata={"document_type": "Agenda"},
        data={},
    )

    assert key.startswith("v1|source=1234|doctype=agenda|url=https://city.gov/Meetings/Agenda")
    assert "utm_source" not in key
    assert "#download" not in key
    assert "a=1&b=2" in key


def test_build_canonical_document_key_falls_back_to_title_and_date() -> None:
    key = build_canonical_document_key(
        source_id="source-abc",
        url="unknown://jurisdiction/meetings/source-name",
        metadata={"document_type": "minutes", "title": "City Council Minutes"},
        data={"published_date": "2026-03-31T19:00:00Z"},
    )

    assert key == (
        "v1|source=source-abc|doctype=minutes|title=city council minutes|date=2026-03-31"
    )


def test_build_revision_seed_provides_phase1_defaults() -> None:
    seed = build_revision_seed(
        {
            "source_id": "source-1",
            "url": "https://example.gov/agendas/1?utm_medium=social",
            "metadata": {"document_type": "agenda"},
            "data": {"title": "Agenda 1"},
        }
    )

    assert seed["canonical_document_key"].startswith("v1|source=source-1|doctype=agenda|url=")
    assert seed["previous_raw_scrape_id"] is None
    assert seed["revision_number"] == 1
    assert seed["seen_count"] == 1
    assert seed["last_seen_at"] is not None
