from pydantic import BaseModel, Field
from typing import List

class ImpactEvidence(BaseModel):
    """Evidence supporting a cost of living impact."""
    source_name: str = Field(description="Name of source (e.g., 'NREL Study 2024')")
    url: str = Field(description="URL to original source")
    excerpt: str = Field(description="Relevant excerpt from source")

class LegislationImpact(BaseModel):
    """Single impact analysis for a piece of legislation."""
    impact_number: int = Field(ge=1, description="Impact sequence number")
    relevant_clause: str = Field(description="Exact text from legislation")
    impact_description: str = Field(description="Description of cost of living impact")
    evidence: List[ImpactEvidence] = Field(min_items=1, description="Evidence list")
    chain_of_causality: str = Field(description="Step-by-step reasoning")
    confidence_factor: float = Field(ge=0.0, le=1.0, description="Confidence in analysis")

    # Cost distribution (2025 dollars)
    p10: float = Field(description="10th percentile cost impact")
    p25: float = Field(description="25th percentile cost impact")
    p50: float = Field(description="50th percentile cost impact (median)")
    p75: float = Field(description="75th percentile cost impact")
    p90: float = Field(description="90th percentile cost impact")

class LegislationAnalysisResponse(BaseModel):
    """Complete analysis of a single bill/regulation."""
    bill_number: str
    impacts: List[LegislationImpact] = Field(default_factory=list)
    total_impact_p50: float = Field(description="Sum of median impacts")
    analysis_timestamp: str
    model_used: str
