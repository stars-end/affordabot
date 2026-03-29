"""Research fixtures for golden bill corpus (bd-bkco.2)."""

from .replay_fixtures import (
    ReplayableResearchFixture,
    FixtureStore,
    FixtureProvenance,
    ScrapedBillFixture,
    RagChunkFixture,
    WebSourceFixture,
    SufficiencyBreakdown,
    create_synthetic_fixture,
    FIXTURE_VERSION,
    FEATURE_KEY,
)

__all__ = [
    "ReplayableResearchFixture",
    "FixtureStore",
    "FixtureProvenance",
    "ScrapedBillFixture",
    "RagChunkFixture",
    "WebSourceFixture",
    "SufficiencyBreakdown",
    "create_synthetic_fixture",
    "FIXTURE_VERSION",
    "FEATURE_KEY",
]
