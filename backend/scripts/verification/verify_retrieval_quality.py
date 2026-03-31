#!/usr/bin/env python3
"""Verify retrieval-quality signals for control fixtures (bd-bkco.4).

Checks:
1) Decisive evidence: top retrieved chunks should support the expected conclusion.
2) Conclusion sensitivity: materially different chunk sets should change conclusion.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.verification.fixtures.research_fixtures import FixtureStore


ConclusionLabel = str

STOPWORDS = {
    "act",
    "bill",
    "concurrent",
    "house",
    "rights",
    "resolution",
    "the",
    "of",
    "and",
    "to",
    "for",
    "with",
    "in",
    "on",
    "a",
    "an",
}


def _tokenize(text: str) -> List[str]:
    return [tok for tok in re.findall(r"[a-z0-9]+", text.lower()) if tok]


def _chunk_text(chunks: Sequence[Dict[str, Any]]) -> str:
    return " ".join(str(c.get("content", "")) for c in chunks).lower()


def infer_conclusion_label(chunks: Sequence[Dict[str, Any]]) -> ConclusionLabel:
    text = _chunk_text(chunks)

    if re.search(
        r"\b(worker|employee|independent contractor|abc test|labor code)\b", text
    ):
        return "worker_classification"

    if re.search(r"\b(parent|education|school|students?)\b", text):
        return "parental_rights_education"

    if re.search(r"\b(non-binding|recognizes|resolution|no fiscal|no appropriation)\b", text):
        return "fail_closed_non_fiscal"

    if re.search(r"\b(appropriation|funding|budget|grant|fiscal)\b", text):
        return "quantifiable_candidate"

    return "unknown"


def expected_conclusion_label(
    bill_id: str, title: str, manifest_record: Dict[str, Any]
) -> ConclusionLabel:
    control_type = str(manifest_record.get("control_type", ""))

    if control_type in {"ceremonial_resolution", "non_binding_resolution"}:
        return "fail_closed_non_fiscal"
    if control_type == "cross_jurisdiction_id_collision_anchor":
        return "worker_classification"
    if control_type == "cross_jurisdiction_id_collision_pair":
        return "parental_rights_education"

    title_guess = infer_conclusion_label([{"content": title}])
    if title_guess != "unknown":
        return title_guess

    if manifest_record.get("expected_quantifiable") is False:
        return "fail_closed_non_fiscal"
    return "quantifiable_candidate"


def _title_overlap_tokens(title: str, chunks: Sequence[Dict[str, Any]]) -> int:
    title_tokens = {
        t for t in _tokenize(title) if len(t) >= 4 and t not in STOPWORDS
    }
    chunk_tokens = set(_tokenize(_chunk_text(chunks)))
    return len(title_tokens & chunk_tokens)


def check_decisive_evidence(
    bill_id: str,
    title: str,
    top_chunks: Sequence[Dict[str, Any]],
    expected_label: ConclusionLabel,
) -> Dict[str, Any]:
    if not top_chunks:
        return {
            "bill_id": bill_id,
            "check": "decisive_evidence",
            "passed": False,
            "reason": "no_top_chunks",
        }

    inferred = infer_conclusion_label(top_chunks)
    overlap = _title_overlap_tokens(title, top_chunks)
    passed = inferred == expected_label and overlap >= 1

    return {
        "bill_id": bill_id,
        "check": "decisive_evidence",
        "passed": passed,
        "expected_label": expected_label,
        "inferred_label": inferred,
        "title_overlap_tokens": overlap,
        "top_chunk_ids": [str(c.get("chunk_id", "")) for c in top_chunks],
    }


def check_conclusion_sensitivity(
    bill_id: str,
    baseline_chunks: Sequence[Dict[str, Any]],
    contrast_bill_id: str,
    contrast_chunks: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    baseline_label = infer_conclusion_label(baseline_chunks)
    contrast_label = infer_conclusion_label(contrast_chunks)
    passed = baseline_label != contrast_label

    return {
        "bill_id": bill_id,
        "check": "conclusion_sensitivity",
        "passed": passed,
        "baseline_label": baseline_label,
        "contrast_bill_id": contrast_bill_id,
        "contrast_label": contrast_label,
    }


def load_manifest(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    manifest_path = (
        repo_root
        / "backend"
        / "scripts"
        / "verification"
        / "fixtures"
        / "golden_bill_corpus_manifest.json"
    )
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    bills = data.get("bills", [])
    return {
        str(record["bill_id"]): record
        for record in bills
        if isinstance(record, dict) and "bill_id" in record
    }


def _choose_contrast(
    bill_id: str,
    baseline_label: ConclusionLabel,
    expected_by_bill: Dict[str, ConclusionLabel],
    chunks_by_bill: Dict[str, List[Dict[str, Any]]],
) -> Tuple[str, List[Dict[str, Any]]]:
    for candidate_id in sorted(chunks_by_bill):
        if candidate_id == bill_id:
            continue
        if expected_by_bill.get(candidate_id) != baseline_label:
            return candidate_id, chunks_by_bill[candidate_id]

    for candidate_id in sorted(chunks_by_bill):
        if candidate_id != bill_id:
            return candidate_id, chunks_by_bill[candidate_id]

    return bill_id, []


def evaluate_retrieval_quality(top_k: int = 1) -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    manifest = load_manifest(repo_root)
    store = FixtureStore.load_corpus()

    decisive_results: List[Dict[str, Any]] = []
    sensitivity_results: List[Dict[str, Any]] = []
    fixture_order = store.all_bill_ids()

    expected_by_bill: Dict[str, ConclusionLabel] = {}
    chunks_by_bill: Dict[str, List[Dict[str, Any]]] = {}
    titles_by_bill: Dict[str, str] = {}

    for bill_id in fixture_order:
        fixture = store.get(bill_id)
        if fixture is None:
            continue
        record = manifest.get(bill_id, {})
        expected_by_bill[bill_id] = expected_conclusion_label(
            bill_id=bill_id,
            title=fixture.get_bill_title(),
            manifest_record=record,
        )
        chunks_by_bill[bill_id] = fixture.get_rag_chunks(limit=top_k)
        titles_by_bill[bill_id] = fixture.get_bill_title()

    for bill_id in fixture_order:
        top_chunks = chunks_by_bill.get(bill_id, [])
        decisive_results.append(
            check_decisive_evidence(
                bill_id=bill_id,
                title=titles_by_bill.get(bill_id, ""),
                top_chunks=top_chunks,
                expected_label=expected_by_bill.get(bill_id, "unknown"),
            )
        )

    for bill_id in fixture_order:
        baseline_chunks = chunks_by_bill.get(bill_id, [])
        baseline_label = infer_conclusion_label(baseline_chunks)
        contrast_bill_id, contrast_chunks = _choose_contrast(
            bill_id=bill_id,
            baseline_label=baseline_label,
            expected_by_bill=expected_by_bill,
            chunks_by_bill=chunks_by_bill,
        )
        sensitivity_results.append(
            check_conclusion_sensitivity(
                bill_id=bill_id,
                baseline_chunks=baseline_chunks,
                contrast_bill_id=contrast_bill_id,
                contrast_chunks=contrast_chunks,
            )
        )

    failed_decisive = [r for r in decisive_results if not r.get("passed")]
    failed_sensitivity = [r for r in sensitivity_results if not r.get("passed")]

    return {
        "feature_key": "bd-bkco.4",
        "top_k": top_k,
        "fixtures_evaluated": len(fixture_order),
        "checks": {
            "decisive_evidence": decisive_results,
            "conclusion_sensitivity": sensitivity_results,
        },
        "summary": {
            "decisive_evidence_failed": len(failed_decisive),
            "conclusion_sensitivity_failed": len(failed_sensitivity),
            "passed": not failed_decisive and not failed_sensitivity,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify retrieval-quality checks for decisive evidence and conclusion sensitivity."
    )
    parser.add_argument("--top-k", type=int, default=1)
    parser.add_argument("--json-output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.top_k <= 0:
        print("FAIL: --top-k must be > 0")
        return 2

    report = evaluate_retrieval_quality(top_k=args.top_k)
    serialized = json.dumps(report, indent=2, sort_keys=True)
    print(serialized)

    if args.json_output is not None:
        args.json_output.write_text(serialized + "\n", encoding="utf-8")

    if report["summary"]["passed"]:
        print("PASS: retrieval-quality checks passed")
        return 0

    print("FAIL: retrieval-quality checks failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
