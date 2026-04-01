from scripts.substrate.run_grounded_validation_sweep import (
    CAPTURED_CANDIDATE,
    DURABLE_RAW,
    PROMOTED_SUBSTRATE,
    build_summary,
    compute_usefulness,
    default_cases,
    evaluate_case_checks,
)


def test_default_cases_cover_required_case_types():
    cases = default_cases()
    case_types = {case.case_type for case in cases}

    assert "official_html_meeting_detail" in case_types
    assert "official_pdf_agenda" in case_types
    assert "official_code_page" in case_types
    assert "third_party_deny_path" in case_types


def test_compute_usefulness_promoted_substrate_is_analysis_useful():
    metadata = {
        "promotion_state": PROMOTED_SUBSTRATE,
        "trust_tier": "primary_government",
        "trust_host_classification": "official_government",
        "ingestion_truth": {"raw_captured": True, "retrievable": True},
    }

    usefulness = compute_usefulness(metadata)

    assert usefulness["analysis_useful"] is True
    assert usefulness["moat_useful"] is True
    assert usefulness["overall_useful"] is True


def test_compute_usefulness_untrusted_capture_is_not_useful():
    metadata = {
        "promotion_state": CAPTURED_CANDIDATE,
        "trust_tier": "non_official",
        "trust_host_classification": "non_official",
        "ingestion_truth": {"raw_captured": True},
    }

    usefulness = compute_usefulness(metadata)

    assert usefulness["analysis_useful"] is False
    assert usefulness["moat_useful"] is False
    assert usefulness["overall_useful"] is False


def test_evaluate_case_checks_reports_expected_mismatch():
    case = next(c for c in default_cases() if c.case_id == "official_code_page")
    metadata = {
        "promotion_state": PROMOTED_SUBSTRATE,  # Should fail for this case
        "trust_tier": "official_partner",
        "trust_host_classification": "official_civic_partner",
        "ingestion_truth": {"raw_captured": True},
    }

    checks = evaluate_case_checks(case=case, metadata=metadata)

    assert checks["promotion_state_expected"] is False
    assert checks["all_expected"] is False


def test_build_summary_counts_failures_and_states():
    summary = build_summary(
        [
            {
                "case": {"case_id": "a"},
                "status": "pass",
                "observed": {"promotion_state": DURABLE_RAW, "promotion_reason_category": "unclear"},
                "usefulness": {
                    "analysis_useful": False,
                    "moat_useful": True,
                    "overall_useful": True,
                },
                "checks": {"all_expected": True},
            },
            {
                "case": {"case_id": "b"},
                "status": "fail",
                "observed": {
                    "promotion_state": CAPTURED_CANDIDATE,
                    "promotion_reason_category": "untrusted_source",
                },
                "usefulness": {
                    "analysis_useful": False,
                    "moat_useful": False,
                    "overall_useful": False,
                },
                "checks": {
                    "promotion_state_expected": False,
                    "official_path_expected": True,
                    "analysis_useful_expected": True,
                    "moat_useful_expected": True,
                    "all_expected": False,
                },
            },
        ]
    )

    assert summary["case_count"] == 2
    assert summary["status_counts"]["pass"] == 1
    assert summary["status_counts"]["fail"] == 1
    assert summary["promotion_state_counts"][DURABLE_RAW] == 1
    assert summary["promotion_state_counts"][CAPTURED_CANDIDATE] == 1
    assert summary["usefulness_counts"]["analysis_useful_true"] == 0
    assert summary["usefulness_counts"]["analysis_useful_false"] == 2
    assert summary["usefulness_counts"]["moat_useful_true"] == 1
    assert summary["usefulness_counts"]["moat_useful_false"] == 1
    assert summary["framework_worked"] is False
    assert len(summary["failures"]) == 1
