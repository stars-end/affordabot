from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List

from schemas.economic_evidence import AssumptionCard, MechanismFamily


@dataclass(frozen=True)
class AssumptionProfile:
    card: AssumptionCard
    required_tags: FrozenSet[str]
    excluded_tags: FrozenSet[str]


@dataclass(frozen=True)
class AssumptionResolution:
    matched: bool
    card: AssumptionCard | None = None
    reason: str | None = None


class AssumptionRegistry:
    """Explicit assumption registry for decision-grade economic quantification."""

    def __init__(self) -> None:
        self._profiles: Dict[MechanismFamily, List[AssumptionProfile]] = {
            MechanismFamily.DIRECT_FISCAL: [
                AssumptionProfile(
                    card=AssumptionCard(
                        id="direct_fiscal.annualization_factor.v1",
                        family=MechanismFamily.DIRECT_FISCAL,
                        low=0.95,
                        central=1.0,
                        high=1.05,
                        unit="multiplier",
                        source_url="https://www.gao.gov/assets/gao-23-106217.pdf",
                        source_excerpt=(
                            "Public budget scoring often annualizes partial-period "
                            "appropriation impacts for comparability."
                        ),
                        applicability_tags=[
                            "public_budget",
                            "appropriation",
                            "annualized_reporting",
                        ],
                        external_validity_notes=(
                            "Use only when source expresses partial-year totals and "
                            "reporting target is annualized fiscal exposure."
                        ),
                        confidence=0.64,
                        version="2026-04-14",
                        stale_after_days=365,
                    ),
                    required_tags=frozenset(
                        {"public_budget", "appropriation", "annualized_reporting"}
                    ),
                    excluded_tags=frozenset(),
                )
            ],
            MechanismFamily.COMPLIANCE_COST: [
                AssumptionProfile(
                    card=AssumptionCard(
                        id="compliance_cost.loaded_wage_multiplier.v1",
                        family=MechanismFamily.COMPLIANCE_COST,
                        low=1.20,
                        central=1.30,
                        high=1.45,
                        unit="multiplier",
                        source_url="https://www.bls.gov/news.release/ecec.nr0.htm",
                        source_excerpt=(
                            "Employer cost for employee compensation includes wages "
                            "and nonwage components; loaded labor rates exceed base wages."
                        ),
                        applicability_tags=[
                            "labor_cost",
                            "administrative_burden",
                            "us_employer_cost",
                        ],
                        external_validity_notes=(
                            "Apply only to staff-time compliance estimates where a "
                            "base wage requires benefits and overhead loading."
                        ),
                        confidence=0.73,
                        version="2026-04-14",
                        stale_after_days=180,
                    ),
                    required_tags=frozenset(
                        {"labor_cost", "administrative_burden", "us_employer_cost"}
                    ),
                    excluded_tags=frozenset({"capital_project"}),
                )
            ],
            MechanismFamily.FEE_OR_TAX_PASS_THROUGH: [
                AssumptionProfile(
                    card=AssumptionCard(
                        id="fee_or_tax_pass_through.housing.v1",
                        family=MechanismFamily.FEE_OR_TAX_PASS_THROUGH,
                        low=0.50,
                        central=0.68,
                        high=0.89,
                        unit="share",
                        source_url="https://www.philadelphiafed.org/-/media/frbp/assets/consumer-finance/discussion-papers/dp24-01.pdf",
                        source_excerpt=(
                            "Property-tax changes are substantially passed through "
                            "to renters, with variation across local market conditions."
                        ),
                        applicability_tags=[
                            "housing",
                            "rental_market",
                            "local_tax_or_fee",
                        ],
                        external_validity_notes=(
                            "Valid for rental housing incidence, especially new-lease "
                            "or turnover segments; do not reuse for utilities or telecom."
                        ),
                        confidence=0.76,
                        version="2026-04-14",
                        stale_after_days=365,
                    ),
                    required_tags=frozenset(
                        {"housing", "rental_market", "local_tax_or_fee"}
                    ),
                    excluded_tags=frozenset({"owner_occupied_only"}),
                )
            ],
            MechanismFamily.ADOPTION_TAKE_UP: [
                AssumptionProfile(
                    card=AssumptionCard(
                        id="adoption_take_up.means_tested_program.v1",
                        family=MechanismFamily.ADOPTION_TAKE_UP,
                        low=0.30,
                        central=0.45,
                        high=0.65,
                        unit="share",
                        source_url="https://www.urban.org/urban-wire/automatic-enrollment-discounted-transit-fare-programs-can-support-higher-participation",
                        source_excerpt=(
                            "Program participation often remains partial due to "
                            "awareness and administrative friction; automatic enrollment improves take-up."
                        ),
                        applicability_tags=[
                            "means_tested_program",
                            "enrollment_friction",
                            "household_benefit",
                        ],
                        external_validity_notes=(
                            "For enrollment-constrained public benefit programs; "
                            "not for mandatory participation or automatic universal delivery."
                        ),
                        confidence=0.67,
                        version="2026-04-14",
                        stale_after_days=365,
                    ),
                    required_tags=frozenset(
                        {
                            "means_tested_program",
                            "enrollment_friction",
                            "household_benefit",
                        }
                    ),
                    excluded_tags=frozenset({"mandatory_participation"}),
                )
            ],
        }

    def resolve(
        self,
        family: MechanismFamily,
        context_tags: set[str] | List[str],
    ) -> AssumptionResolution:
        tags = set(context_tags)
        profiles = self._profiles.get(family, [])

        for profile in profiles:
            if not profile.required_tags.issubset(tags):
                continue
            if profile.excluded_tags.intersection(tags):
                continue
            return AssumptionResolution(matched=True, card=profile.card)

        return AssumptionResolution(
            matched=False,
            reason=(
                "No applicability-constrained assumption profile matched "
                f"family={family.value} tags={sorted(tags)}."
            ),
        )
