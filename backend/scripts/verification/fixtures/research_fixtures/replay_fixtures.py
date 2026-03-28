"""
Replayable Research Fixtures for Golden Bill Corpus (bd-bkco.2).

Provides fixture storage, replay, and validation for research pipeline testing.
Separates pipeline logic regressions from search volatility.

Usage:
    from backend.scripts.verification.fixtures.research_fixtures import (
        ReplayableResearchFixture,
        FixtureStore,
    )

    fixture = ReplayableResearchFixture.load("us-hr-1319-2021")
    bill_text = fixture.get_bill_text()
    chunks = fixture.get_rag_chunks()
    web_sources = fixture.get_web_sources()
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FIXTURE_VERSION = "1.0"
FEATURE_KEY = "bd-bkco.2"


@dataclass
class ScrapedBillFixture:
    bill_number: str = ""
    title: str = ""
    text: str = ""
    introduced_date: Optional[str] = None
    status: Optional[str] = None
    source_url: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScrapedBillFixture":
        return cls(
            bill_number=data.get("bill_number", ""),
            title=data.get("title", ""),
            text=data.get("text", ""),
            introduced_date=data.get("introduced_date"),
            status=data.get("status"),
            source_url=data.get("source_url", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "bill_number": self.bill_number,
            "title": self.title,
            "text": self.text,
        }
        if self.introduced_date:
            result["introduced_date"] = self.introduced_date
        if self.status:
            result["status"] = self.status
        if self.source_url:
            result["source_url"] = self.source_url
        return result


@dataclass
class RagChunkFixture:
    chunk_id: str
    content: str
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RagChunkFixture":
        return cls(
            chunk_id=data.get("chunk_id", ""),
            content=data.get("content", ""),
            score=data.get("score", 0.0),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }

    def to_retrieved_chunk(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class WebSourceFixture:
    url: str = ""
    title: str = ""
    snippet: str = ""
    content: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebSourceFixture":
        return cls(
            url=data.get("url", "") or data.get("link", ""),
            title=data.get("title", ""),
            snippet=data.get("snippet", ""),
            content=data.get("content"),
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
        }
        if self.content:
            result["content"] = self.content
        return result


@dataclass
class SufficiencyBreakdown:
    source_text_present: bool = False
    rag_chunks_retrieved: int = 0
    web_research_sources_found: int = 0
    fiscal_notes_detected: bool = False
    bill_text_chunks: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SufficiencyBreakdown":
        return cls(
            source_text_present=data.get("source_text_present", False),
            rag_chunks_retrieved=data.get("rag_chunks_retrieved", 0),
            web_research_sources_found=data.get("web_research_sources_found", 0),
            fiscal_notes_detected=data.get("fiscal_notes_detected", False),
            bill_text_chunks=data.get("bill_text_chunks", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_text_present": self.source_text_present,
            "rag_chunks_retrieved": self.rag_chunks_retrieved,
            "web_research_sources_found": self.web_research_sources_found,
            "fiscal_notes_detected": self.fiscal_notes_detected,
            "bill_text_chunks": self.bill_text_chunks,
        }


@dataclass
class ReplayableResearchFixture:
    bill_id: str
    captured_at: str
    capture_mode: str
    scraped_bill_text: ScrapedBillFixture
    rag_chunks: List[RagChunkFixture]
    web_sources: List[WebSourceFixture]
    sufficiency_breakdown: SufficiencyBreakdown
    fixture_version: str = FIXTURE_VERSION
    feature_key: str = FEATURE_KEY

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReplayableResearchFixture":
        scraped_data = data.get("scraped_bill_text", {})
        if isinstance(scraped_data, dict):
            scraped = ScrapedBillFixture.from_dict(scraped_data)
        else:
            scraped = ScrapedBillFixture()

        return cls(
            fixture_version=data.get("fixture_version", FIXTURE_VERSION),
            feature_key=data.get("feature_key", FEATURE_KEY),
            bill_id=data["bill_id"],
            captured_at=data.get("captured_at", ""),
            capture_mode=data.get("capture_mode", "synthetic"),
            scraped_bill_text=scraped,
            rag_chunks=[
                RagChunkFixture.from_dict(c) for c in data.get("rag_chunks", [])
            ],
            web_sources=[
                WebSourceFixture.from_dict(w) for w in data.get("web_sources", [])
            ],
            sufficiency_breakdown=SufficiencyBreakdown.from_dict(
                data.get("sufficiency_breakdown", {})
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fixture_version": self.fixture_version,
            "feature_key": self.feature_key,
            "bill_id": self.bill_id,
            "captured_at": self.captured_at,
            "capture_mode": self.capture_mode,
            "scraped_bill_text": self.scraped_bill_text.to_dict(),
            "rag_chunks": [c.to_dict() for c in self.rag_chunks],
            "web_sources": [w.to_dict() for w in self.web_sources],
            "sufficiency_breakdown": self.sufficiency_breakdown.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def load(cls, bill_id: str) -> "ReplayableResearchFixture":
        fixture_dir = Path(__file__).parent
        fixture_path = fixture_dir / f"{bill_id}.json"
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found: {fixture_path}")
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def save(self) -> None:
        fixture_dir = Path(__file__).parent
        fixture_dir.mkdir(parents=True, exist_ok=True)
        fixture_path = fixture_dir / f"{self.bill_id}.json"
        fixture_path.write_text(self.to_json(), encoding="utf-8")
        logger.info(f"Saved fixture: {fixture_path}")

    def get_bill_text(self) -> str:
        return self.scraped_bill_text.text

    def get_bill_title(self) -> str:
        return self.scraped_bill_text.title

    def get_rag_chunks(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        chunks = [c.to_retrieved_chunk() for c in self.rag_chunks]
        if limit is not None:
            chunks = chunks[:limit]
        return chunks

    def get_web_sources(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        sources = [w.to_dict() for w in self.web_sources]
        if limit is not None:
            sources = sources[:limit]
        return sources

    def to_research_result(self) -> Dict[str, Any]:
        return {
            "bill_id": self.bill_id,
            "rag_chunks": self.get_rag_chunks(),
            "web_sources": self.get_web_sources(),
            "sufficiency_breakdown": self.sufficiency_breakdown.to_dict(),
            "is_sufficient": self._compute_sufficiency(),
        }

    def _compute_sufficiency(self) -> bool:
        breakdown = self.sufficiency_breakdown
        if not breakdown.source_text_present:
            return False
        if breakdown.rag_chunks_retrieved >= 3:
            return True
        if (
            breakdown.rag_chunks_retrieved >= 1
            and breakdown.web_research_sources_found >= 2
        ):
            return True
        if breakdown.web_research_sources_found >= 5:
            return True
        return False

    def for_prefix_evaluation(self) -> Dict[str, Any]:
        return {
            "bill_id": self.bill_id,
            "bill_text": self.get_bill_text(),
            "rag_chunks": self.get_rag_chunks(limit=3),
        }

    def for_full_run_evaluation(self) -> Dict[str, Any]:
        return self.to_research_result()


class FixtureStore:
    def __init__(self, fixtures: Dict[str, ReplayableResearchFixture]):
        self.fixtures = fixtures

    @classmethod
    def load_corpus(cls) -> "FixtureStore":
        fixture_dir = Path(__file__).parent
        fixtures: Dict[str, ReplayableResearchFixture] = {}

        if not fixture_dir.exists():
            logger.warning(f"Fixture directory not found: {fixture_dir}")
            return cls(fixtures)

        for fixture_path in fixture_dir.glob("*.json"):
            try:
                data = json.loads(fixture_path.read_text(encoding="utf-8"))
                fixture = ReplayableResearchFixture.from_dict(data)
                fixtures[fixture.bill_id] = fixture
            except Exception as e:
                logger.warning(f"Failed to load fixture {fixture_path}: {e}")

        logger.info(f"Loaded {len(fixtures)} fixtures from {fixture_dir}")
        return cls(fixtures)

    def get(self, bill_id: str) -> Optional[ReplayableResearchFixture]:
        return self.fixtures.get(bill_id)

    def all_bill_ids(self) -> List[str]:
        return sorted(self.fixtures.keys())

    def validate_against_manifest(
        self, manifest_bill_ids: List[str]
    ) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {
            "missing_fixtures": [],
            "extra_fixtures": [],
            "matched": [],
        }

        fixture_ids = set(self.fixtures.keys())
        manifest_ids = set(manifest_bill_ids)

        result["missing_fixtures"] = sorted(manifest_ids - fixture_ids)
        result["extra_fixtures"] = sorted(fixture_ids - manifest_ids)
        result["matched"] = sorted(fixture_ids & manifest_ids)

        return result


def create_synthetic_fixture(
    bill_id: str,
    bill_number: str = "",
    title: str = "",
    text: str = "",
    rag_chunks: Optional[List[Dict[str, Any]]] = None,
    web_sources: Optional[List[Dict[str, Any]]] = None,
    sufficiency_breakdown: Optional[Dict[str, Any]] = None,
) -> ReplayableResearchFixture:
    now = datetime.utcnow().isoformat() + "Z"

    return ReplayableResearchFixture(
        bill_id=bill_id,
        captured_at=now,
        capture_mode="synthetic",
        scraped_bill_text=ScrapedBillFixture(
            bill_number=bill_number or bill_id,
            title=title,
            text=text,
        ),
        rag_chunks=[RagChunkFixture.from_dict(c) for c in (rag_chunks or [])],
        web_sources=[WebSourceFixture.from_dict(w) for w in (web_sources or [])],
        sufficiency_breakdown=SufficiencyBreakdown.from_dict(
            sufficiency_breakdown or {}
        ),
    )
