# Legislative Impact Quantification Models

Implement the Pydantic schemas and validation logic for structured legislative financial impact analysis, including probabilistic scenario bounds and impact mode classification.

## Capabilities

### Impact model validation

- A `LegislationImpact` with `mode = ImpactMode.DIRECT_FISCAL` and valid `ScenarioBounds` (p10, p50, p90) is accepted without validation errors [@test](./tests/test_valid_impact.py)
- `ScenarioBounds` requires `p10 <= p50 <= p90`; providing out-of-order values raises a `ValidationError` [@test](./tests/test_scenario_bounds_order.py)
- A `LegislationAnalysisResponse` containing a list of `LegislationImpact` objects passes validation when all impacts have consistent modes and bounds [@test](./tests/test_analysis_response.py)
- An impact with `mode = ImpactMode.QUALITATIVE_ONLY` is valid with all scenario bounds set to `None` [@test](./tests/test_qualitative_impact.py)

## Implementation

[@generates](./src/analysis_schemas.py)

## API

```python { #api }
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, model_validator

class ImpactMode(str, Enum):
    DIRECT_FISCAL = "direct_fiscal"
    COMPLIANCE_COST = "compliance_cost"
    PASS_THROUGH_INCIDENCE = "pass_through_incidence"
    ADOPTION_TAKE_UP = "adoption_take_up"
    QUALITATIVE_ONLY = "qualitative_only"

class ScenarioBounds(BaseModel):
    p10: Optional[float] = None
    p50: Optional[float] = None
    p90: Optional[float] = None

class LegislationImpact(BaseModel):
    description: str
    mode: ImpactMode
    bounds: Optional[ScenarioBounds] = None

class LegislationAnalysisResponse(BaseModel):
    bill_number: str
    jurisdiction: str
    impacts: List[LegislationImpact]
    sufficiency_state: str
```

## Dependencies { .dependencies }

### affordabot { .dependency }

Provides the `ImpactMode`, `ScenarioBounds`, `LegislationImpact`, and `LegislationAnalysisResponse` Pydantic models and their validators used throughout the affordabot analysis pipeline.

[@satisfied-by](affordabot)
