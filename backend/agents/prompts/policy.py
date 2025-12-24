"""
Policy analysis prompts for affordabot.

This module contains prompts for:
- System prompt for policy analyst persona
- Bill analysis template
- Answer synthesis template
"""

# System prompt for policy analyst persona
SYSTEM_PROMPT = """You are an expert policy analyst specializing in local government legislation.
Your role is to analyze legislative bills, municipal policies, and government actions
with a focus on their practical impacts on residents and stakeholders.

Key principles:
1. Be impartial and evidence-based
2. Consider impacts on diverse stakeholders (residents, businesses, environment)
3. Identify fiscal implications clearly
4. Note any potential unintended consequences
5. Reference specific sections of legislation when possible

Always cite your sources using the provided evidence."""


# Template for detailed bill analysis
BILL_ANALYSIS_TEMPLATE = """
Please analyze the following legislation:

**Bill/Policy**: {bill_number}
**Jurisdiction**: {jurisdiction}

**Source Material**:
{bill_text}

Provide a comprehensive analysis including:

## 1. Summary
A brief 2-3 sentence overview of what this legislation does.

## 2. Key Provisions
- List the main components and requirements
- Note any thresholds, timelines, or specific criteria

## 3. Impact Analysis

### Positive Impacts
- List expected benefits for each stakeholder group

### Potential Concerns
- Identify possible negative effects or challenges

## 4. Fiscal Implications
- Estimated costs to implement
- Revenue impacts
- Long-term budget considerations

## 5. Comparison to Similar Policies
- How does this compare to similar jurisdictions?

Cite specific evidence IDs for each major claim.
"""


# Template for policy question synthesis
SYNTHESIS_PROMPT = """You are synthesizing an answer to a policy question using collected evidence.

**Question**: {query}

**Collected Evidence**:
{context}

Instructions:
1. Provide a clear, direct answer to the question
2. Cite evidence by referencing the source URLs or document titles
3. If evidence is conflicting, explain the different perspectives
4. Note any gaps in the available evidence
5. Keep the response focused and actionable

Format your response with:
- A direct answer paragraph
- Supporting evidence (with citations)
- Any important caveats or considerations
"""


# Template for multi-impact analysis
IMPACT_ANALYSIS_TEMPLATE = """
Analyze the following policy for its impacts on the target population:

**Policy Context**: {policy_description}
**Target Population**: {population}
**Jurisdiction**: {jurisdiction}

**Evidence Collected**:
{evidence}

For each identified impact:
1. **Impact**: Description of the effect
2. **Magnitude**: Low/Medium/High
3. **Stakeholders**: Who is affected
4. **Timeline**: When effects are expected
5. **Evidence**: Citations supporting this impact
6. **Confidence**: How confident are we in this assessment

Return as structured JSON.
"""


# Quick research template
RESEARCH_PLAN_TEMPLATE = """
Create a research plan to answer this policy question:

**Question**: {query}
**Jurisdiction**: {jurisdiction}

Available tools:
{available_tools}

Create a plan that:
1. Identifies what information is needed
2. Specifies which tools to use
3. Prioritizes official/authoritative sources
4. Includes fall-back strategies if primary sources fail

Return the plan as structured JSON with tasks.
"""

