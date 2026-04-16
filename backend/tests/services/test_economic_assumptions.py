import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from schemas.economic_evidence import MechanismFamily  # noqa: E402
from services.economic_assumptions import AssumptionRegistry  # noqa: E402


def test_registry_returns_valid_assumption_when_applicability_matches():
    registry = AssumptionRegistry()
    result = registry.resolve(
        MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
        {"housing", "rental_market", "local_tax_or_fee"},
    )

    assert result.matched is True
    assert result.card is not None
    assert result.card.family == MechanismFamily.FEE_OR_TAX_PASS_THROUGH
    assert result.card.low <= result.card.central <= result.card.high


def test_registry_fails_closed_on_applicability_mismatch():
    registry = AssumptionRegistry()
    result = registry.resolve(
        MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
        {"telecom", "wireless", "usage_fee"},
    )

    assert result.matched is False
    assert result.card is None
    assert result.reason is not None
    assert "No applicability-constrained assumption profile matched" in result.reason


def test_registry_fails_closed_when_excluded_tag_present():
    registry = AssumptionRegistry()
    result = registry.resolve(
        MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
        {"housing", "rental_market", "local_tax_or_fee", "owner_occupied_only"},
    )
    assert result.matched is False
