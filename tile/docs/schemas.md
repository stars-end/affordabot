# AffordaBot Analysis Schemas

Pydantic models that define the structure of legislation analysis output. Located in `backend/schemas/analysis.py`.

## Import

```python
from schemas.analysis import (
    LegislationAnalysisResponse,
    LegislationImpact,
    ImpactEvidence,
    ScenarioBounds,
    SufficiencyState,
    SufficiencyBreakdown,
    ImpactGateSummary,
    ReviewCritique,
    ModeSelectionOutput,
    ParameterResolutionOutput,
    ParameterValidationOutput,
    ModeledParameter,
    ComponentBreakdown,
    PersistedEvidence,
    RetrievalPrerequisiteStatus,
    ImpactMode,
    SourceTier,
    FailureCode,
    SourceHierarchyStatus,
    ExcerptValidationStatus,
    AmbiguityStatus,
)
```

## Top-Level Response Models

### LegislationAnalysisResponse

Complete analysis output for a single bill or regulation.

```python { .api }
class LegislationAnalysisResponse(BaseModel):
    bill_number: str
    title: str = ""
    jurisdiction: str = ""
    status: str = ""
    sufficiency_state: SufficiencyState = SufficiencyState.RESEARCH_INCOMPLETE
    insufficiency_reason: Optional[str] = None   # human-readable reason if not quantified
    quantification_eligible: bool = False        # whether quantified output is permitted
    impacts: List[LegislationImpact] = []
    aggregate_scenario_bounds: Optional[ScenarioBounds] = None
    analysis_timestamp: str                      # ISO 8601 timestamp
    model_used: str

    # Computed property:
    @property
    def total_impact_p50(self) -> Optional[float]:
        # Returns aggregate_scenario_bounds.central if set,
        # otherwise sum of individual impact central values
        ...
```

**Legacy upgrade:** Responses with a top-level `total_impact_p50` float field are automatically upgraded to `aggregate_scenario_bounds`.

### LegislationImpact

A single identified cost-of-living impact within a bill analysis.

```python { .api }
class LegislationImpact(BaseModel):
    impact_number: int                         # ge=1, sequence number
    relevant_clause: str = ""                  # exact text from legislation
    legal_interpretation: str = ""             # interpretation of the legal mechanism
    impact_description: str = ""               # description of cost of living impact
    evidence: List[ImpactEvidence] = []
    chain_of_causality: str = ""               # step-by-step reasoning
    confidence_score: Optional[float] = None   # ge=0.0, le=1.0
    impact_mode: ImpactMode = ImpactMode.QUALITATIVE_ONLY
    mode_selection: Optional[ModeSelectionOutput] = None
    parameter_resolution: Optional[ParameterResolutionOutput] = None
    parameter_validation: Optional[ParameterValidationOutput] = None
    modeled_parameters: Dict[str, ModeledParameter] = {}
    component_breakdown: List[ComponentBreakdown] = []
    scenario_bounds: Optional[ScenarioBounds] = None
    composition_note: Optional[str] = None
    failure_codes: List[FailureCode] = []

    # Computed properties (read-only):
    @property
    def is_quantified(self) -> bool: ...    # True if scenario_bounds is set
    @property
    def p10(self) -> Optional[float]: ...  # scenario_bounds.conservative
    @property
    def p50(self) -> Optional[float]: ...  # scenario_bounds.central
    @property
    def p90(self) -> Optional[float]: ...  # scenario_bounds.aggressive
```

**Legacy upgrade:** Responses with `p10`/`p50`/`p90` fields are automatically upgraded to `scenario_bounds`.

## Evidence Models

### ImpactEvidence

Evidence supporting a cost-of-living impact.

```python { .api }
class ImpactEvidence(BaseModel):
    source_name: str = ""                          # e.g., "NREL Study 2024"
    url: str = ""                                  # must be HTTP(S) URL or empty string
    excerpt: str = ""                              # relevant excerpt from source
    source_tier: Optional[SourceTier] = None
    persisted_evidence_id: Optional[str] = None   # upstream EvidenceEnvelope.id
    persisted_evidence_kind: Optional[str] = None  # upstream EvidenceEnvelope.kind
```

### PersistedEvidence

Evidence preserved from an EvidenceEnvelope with full provenance fields.

```python { .api }
class PersistedEvidence(BaseModel):
    id: str = ""
    kind: str = ""
    url: str = ""
    excerpt: Optional[str] = None
    content_hash: Optional[str] = None
    derived_from: List[str] = []        # list of upstream evidence IDs
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    confidence: Optional[float] = None  # ge=0.0, le=1.0
    source_name: str = ""
    label: Optional[str] = None
```

## Quantification Models

### ScenarioBounds

Conservative/central/aggressive scenario estimates for monetary impact (annual $/household).

```python { .api }
class ScenarioBounds(BaseModel):
    conservative: float   # lower bound (p10-equivalent)
    central: float        # central estimate (p50-equivalent)
    aggressive: float     # upper bound (p90-equivalent)
    # Validates: conservative <= central <= aggressive
```

### ComponentBreakdown

Breakdown of a quantified impact into named components.

```python { .api }
class ComponentBreakdown(BaseModel):
    component_name: str
    base: float
    low: float
    high: float
    unit: Optional[str] = None
    formula: Optional[str] = None
```

### ModeledParameter

A single economic parameter used in impact quantification.

```python { .api }
class ModeledParameter(BaseModel):
    name: str
    value: float
    unit: Optional[str] = None
    source_url: str = ""
    source_excerpt: str = ""
```

## Pipeline Gate Models

### ModeSelectionOutput

Output of the impact mode selection pipeline step.

```python { .api }
class ModeSelectionOutput(BaseModel):
    candidate_modes: List[ImpactMode] = []
    selected_mode: ImpactMode = ImpactMode.QUALITATIVE_ONLY
    rejected_modes: List[ImpactMode] = []
    selection_rationale: str = ""
    ambiguity_status: AmbiguityStatus = AmbiguityStatus.CLEAR
    composition_candidate: bool = False   # must be False in Wave 1
```

### ParameterResolutionOutput

Output of the parameter resolution pipeline step.

```python { .api }
class ParameterResolutionOutput(BaseModel):
    required_parameters: List[str] = []
    resolved_parameters: Dict[str, ModeledParameter] = {}
    missing_parameters: List[str] = []
    source_hierarchy_status: Dict[str, SourceHierarchyStatus] = {}
    excerpt_validation_status: Dict[str, ExcerptValidationStatus] = {}
    literature_confidence: Dict[str, float] = {}
    dominant_uncertainty_parameters: List[str] = []
```

### ParameterValidationOutput

Output of the parameter validation pipeline step.

```python { .api }
class ParameterValidationOutput(BaseModel):
    schema_valid: bool = False
    arithmetic_valid: bool = False
    bound_construction_valid: bool = False
    claim_support_valid: bool = False
    validation_failures: List[FailureCode] = []
```

### RetrievalPrerequisiteStatus

Status of retrieval prerequisites for a specific impact.

```python { .api }
class RetrievalPrerequisiteStatus(BaseModel):
    source_text_present: bool = False
    rag_chunks_retrieved: int = 0
    web_research_sources_found: int = 0
    has_verifiable_url: bool = False
```

### ImpactGateSummary

Summary of gate evaluation for a single impact.

```python { .api }
class ImpactGateSummary(BaseModel):
    impact_id: str
    selected_mode: ImpactMode = ImpactMode.QUALITATIVE_ONLY
    quantification_eligible: bool = False
    sufficiency_state: SufficiencyState = SufficiencyState.QUALITATIVE_ONLY
    gate_failures: List[FailureCode] = []
    parameter_validation_summary: ParameterValidationOutput
    retrieval_prerequisite_status: RetrievalPrerequisiteStatus
```

### SufficiencyBreakdown

Bill-level deterministic sufficiency assessment derived after per-impact gating.

```python { .api }
class SufficiencyBreakdown(BaseModel):
    overall_quantification_eligible: bool = False
    overall_sufficiency_state: SufficiencyState = SufficiencyState.RESEARCH_INCOMPLETE
    impact_gate_summaries: List[ImpactGateSummary] = []
    bill_level_failures: List[FailureCode] = []
```

### ReviewCritique

Output of the LLM review pipeline step.

```python { .api }
class ReviewCritique(BaseModel):
    passed: bool
    critique: str
    missing_impacts: List[str] = []
    factual_errors: List[str] = []
```

## Request Models

### SystemPromptUpdate

**Location:** `backend/schemas/prompt.py`

```python { .api }
from schemas.prompt import SystemPromptUpdate

class SystemPromptUpdate(BaseModel):
    prompt_type: str
    system_prompt: str
    description: Optional[str] = None
```

Used by `PUT /api/prompts/{prompt_type}` to update a system prompt.

---

## Enums

### SufficiencyState

Describes the evidence sufficiency state for an analysis.

```python { .api }
class SufficiencyState(str, Enum):
    RESEARCH_INCOMPLETE = "research_incomplete"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    QUALITATIVE_ONLY = "qualitative_only"
    QUANTIFIED = "quantified"
```

### ImpactMode

The economic mechanism by which a bill impacts cost of living.

```python { .api }
class ImpactMode(str, Enum):
    DIRECT_FISCAL = "direct_fiscal"
    COMPLIANCE_COST = "compliance_cost"
    PASS_THROUGH_INCIDENCE = "pass_through_incidence"
    ADOPTION_TAKE_UP = "adoption_take_up"
    QUALITATIVE_ONLY = "qualitative_only"
```

### SourceTier

Evidence quality classification.

```python { .api }
class SourceTier(str, Enum):
    TIER_A = "tier_a"   # highest quality (e.g., bill text, fiscal analyses)
    TIER_B = "tier_b"   # medium quality (e.g., government reports)
    TIER_C = "tier_c"   # lower quality (e.g., news articles)
```

### FailureCode

Machine-readable failure codes for pipeline gate failures.

```python { .api }
class FailureCode(str, Enum):
    IMPACT_DISCOVERY_FAILED = "impact_discovery_failed"
    MODE_SELECTION_FAILED = "mode_selection_failed"
    PARAMETER_MISSING = "parameter_missing"
    PARAMETER_UNVERIFIABLE = "parameter_unverifiable"
    SOURCE_HIERARCHY_FAILED = "source_hierarchy_failed"
    EXCERPT_VALIDATION_FAILED = "excerpt_validation_failed"
    INVALID_SCENARIO_CONSTRUCTION = "invalid_scenario_construction"
    VALIDATION_FAILED = "validation_failed"
    FIXTURE_INVALID = "fixture_invalid"
```

### SourceHierarchyStatus

Status of the source hierarchy check for a parameter.

```python { .api }
class SourceHierarchyStatus(str, Enum):
    BILL_OR_REG_TEXT = "bill_or_reg_text"
    FISCAL_OR_REG_IMPACT_ANALYSIS = "fiscal_or_reg_impact_analysis"
    FAILED_CLOSED = "failed_closed"
```

### ExcerptValidationStatus

Whether a source excerpt was validated as authentic.

```python { .api }
class ExcerptValidationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
```

### AmbiguityStatus

Ambiguity classification from mode selection.

```python { .api }
class AmbiguityStatus(str, Enum):
    CLEAR = "clear"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
```
