"""Service for reviewing and improving scraping templates."""

from __future__ import annotations
from typing import List, Dict, Any
from db.postgres_client import PostgresDB
from llm_common import LLMClient, WebSearchClient
from services.auto_discovery_service import QUERY_TEMPLATES

class TemplateReviewService:
    def __init__(
        self, 
        db_client: PostgresDB,
        llm_client: LLMClient,
        web_search_client: WebSearchClient
    ):
        self.db = db_client
        self.llm_client = llm_client
        self.search_client = web_search_client

    async def review_templates(self, jurisdiction_type: str = "city") -> List[Dict[str, Any]]:
        """
        Review templates for a jurisdiction type using LLM analysis.
        
        Args:
            jurisdiction_type: "city" or "county"
            
        Returns:
            List of created review entries
        """
        templates = QUERY_TEMPLATES.get(jurisdiction_type, {})
        reviews = []
        
        # Sample jurisdictions to test against (hardcoded for now, could be dynamic)
        sample_jurisdictions = ["San Jose", "Palo Alto", "Mountain View"]
        
        for category, queries in templates.items():
            for current_template in queries:
                # 1. Test current template
                results = []
                for city in sample_jurisdictions:
                    query = current_template.format(name=city)
                    search_res = await self.search_client.search(query, count=2)
                    results.extend([r.snippet for r in search_res])
                
                # 2. Ask LLM to analyze and suggest improvements
                prompt = f"""
                Analyze these search results for the query template "{current_template}" (Category: {category}).
                Results: {results[:5]}
                
                Does this template effectively find {category} pages? 
                If not, suggest a BETTER template string (using {{name}} placeholder).
                Provide reasoning.
                
                Format:
                SUGGESTION: <new_template_or_SAME>
                REASONING: <reasoning>
                """
                
                response = await self.llm_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model="gpt-4o"
                )
                content = response.choices[0].message.content
                
                # Parse response (simple parsing)
                suggestion = "SAME"
                reasoning = "No change needed"
                
                for line in content.split('\n'):
                    if line.startswith("SUGGESTION:"):
                        suggestion = line.replace("SUGGESTION:", "").strip()
                    if line.startswith("REASONING:"):
                        reasoning = line.replace("REASONING:", "").strip()
                
                if suggestion != "SAME" and suggestion != current_template:
                    # Create review entry
                    review = {
                        "jurisdiction_type": jurisdiction_type,
                        "category": category,
                        "current_template": current_template,
                        "suggested_template": suggestion,
                        "reasoning": reasoning,
                        "status": "pending"
                    }
                    
                    res = await self.db.create_template_review(review)
                    if res:
                        reviews.append(res)
        
        return reviews
