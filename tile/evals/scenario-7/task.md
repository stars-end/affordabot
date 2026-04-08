# Evidence Sufficiency Gates

Implement the deterministic evidence sufficiency gating logic that decides whether the pipeline is permitted to produce quantified financial impact estimates for a piece of legislation.

## Capabilities

### Sufficiency state determination

- Given strong fiscal evidence (fiscal keywords present, quantified support indicators found), `assess_sufficiency()` returns a `SufficiencyBreakdown` with `state = SufficiencyState.QUANTIFIED` [@test](./tests/test_sufficient_quantified.py)
- When evidence contains fiscal content but lacks quantified support indicators, the function returns `state = SufficiencyState.QUALITATIVE_ONLY` [@test](./tests/test_qualitative_only.py)
- When evidence contains none of the fiscal support keywords, the function returns `state = SufficiencyState.INSUFFICIENT_EVIDENCE` [@test](./tests/test_insufficient.py)
- `strip_quantification(analysis_response)` removes all quantified fields (p50, p10, p90 scenario bounds) from a `LegislationAnalysisResponse` and sets each impact's mode to `QUALITATIVE_ONLY` [@test](./tests/test_strip_quantification.py)

## Implementation

[@generates](./src/evidence_gates.py)

## API

```python { #api }
from schemas.analysis import (
    ImpactEvidence,
    LegislationAnalysisResponse,
    SufficiencyBreakdown,
    SufficiencyState,
)
from typing import List

def assess_sufficiency(evidence: List[ImpactEvidence]) -> SufficiencyBreakdown:
    """
    Assess whether the collected evidence is sufficient for quantified output.
    Returns a SufficiencyBreakdown with the determined SufficiencyState.
    """
    ...

def strip_quantification(response: LegislationAnalysisResponse) -> LegislationAnalysisResponse:
    """
    Remove quantified fields from a response, downgrading all impacts to QUALITATIVE_ONLY.
    """
    ...

def supports_quantified_evidence(evidence: List[ImpactEvidence]) -> bool:
    """Return True if evidence supports quantified analysis."""
    ...
```

## Dependencies { .dependencies }

### affordabot { .dependency }

Provides the `SufficiencyState` enum, `SufficiencyBreakdown`, `ImpactEvidence`, `LegislationAnalysisResponse`, `ImpactMode`, and the evidence keyword lists used by the deterministic gate logic.

[@satisfied-by](affordabot)
