from scripts.substrate.evaluate_promotion_candidates import merge_eval_metadata


def test_merge_eval_metadata_prefers_raw_and_sets_canonical_url():
    raw_metadata, eval_metadata, canonical_url = merge_eval_metadata(
        {
            "raw_metadata": {
                "canonical_url": "https://www.sanjoseca.gov/raw",
                "document_type": "agenda",
                "trust_tier": "primary_government",
            },
            "source_metadata": {
                "canonical_url": "https://www.sanjoseca.gov/source",
                "document_type": "meeting_calendar",
            },
            "raw_url": "https://www.sanjoseca.gov/fallback-raw",
            "source_url": "https://www.sanjoseca.gov/fallback-source",
        }
    )

    assert raw_metadata["canonical_url"] == "https://www.sanjoseca.gov/raw"
    assert eval_metadata["document_type"] == "agenda"
    assert canonical_url == "https://www.sanjoseca.gov/raw"


def test_merge_eval_metadata_uses_row_urls_when_metadata_missing():
    _, eval_metadata, canonical_url = merge_eval_metadata(
        {
            "raw_metadata": {},
            "source_metadata": {},
            "raw_url": "https://sanjose.legistar.com/detail",
            "source_url": "https://sanjose.legistar.com/source",
        }
    )

    assert canonical_url == "https://sanjose.legistar.com/detail"
    assert eval_metadata["url"] == "https://sanjose.legistar.com/detail"
