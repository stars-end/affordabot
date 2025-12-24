"""Service for auto-discovering potential sources for a given jurisdiction.

This service uses GLM-4.7 to dynamically generate search queries for discovering
government sources. Discovery prompts are stored in the database for admin editing.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional

from llm_common.core import LLMConfig
from llm_common.providers import ZaiClient
from llm_common.core.models import LLMMessage, MessageRole

logger = logging.getLogger(__name__)


# Default discovery prompt (seeded to DB on first run)
DEFAULT_DISCOVERY_PROMPT = """You are a government document expert. Generate diverse web search queries to discover official government documents for {jurisdiction}.

Focus areas:
- City council meetings, agendas, and minutes
- Housing policy and legislation updates
- Zoning ordinances and land use regulations
- ADU (Accessory Dwelling Unit) policies
- Rent control and tenant protection laws
- Cost of living and affordability assessments
- Public housing programs and initiatives

Return ONLY a JSON array of 8-10 search query strings. No explanation.

Example output:
["San Jose city council housing agenda 2024", "San Jose ADU permit requirements", ...]
"""


class AutoDiscoveryService:
    """
    LLM-powered discovery service for finding government source URLs.
    
    Uses GLM-4.7 to generate contextually appropriate search queries,
    replacing static templates with dynamic LLM-generated queries.
    """
    
    def __init__(
        self, 
        search_client,  # WebSearchClient
        llm_client: Optional[ZaiClient] = None,
        db_client: Optional[Any] = None
    ):
        self.search_client = search_client
        self.db = db_client
        
        # Initialize LLM client for query generation
        if llm_client:
            self.llm_client = llm_client
        else:
            # Auto-initialize with Z.ai if available
            zai_key = os.environ.get("ZAI_API_KEY")
            if zai_key:
                self.llm_client = ZaiClient(LLMConfig(
                    api_key=zai_key,
                    provider="zai",
                    default_model="glm-4.7"
                ))
            else:
                self.llm_client = None
                logger.warning("No LLM client configured - falling back to static templates")
    
    async def get_discovery_prompt(self) -> str:
        """Fetch discovery prompt from DB, or use default if not found."""
        if self.db:
            try:
                prompt_record = await self.db.get_system_prompt("discovery_query_generator")
                if prompt_record:
                    return prompt_record.get("system_prompt", DEFAULT_DISCOVERY_PROMPT)
            except Exception as e:
                logger.warning(f"Failed to fetch discovery prompt from DB: {e}")
        
        return DEFAULT_DISCOVERY_PROMPT
    
    async def generate_queries(
        self, 
        jurisdiction_name: str, 
        jurisdiction_type: str = "city"
    ) -> List[str]:
        """
        Generate search queries using GLM-4.7.
        
        Returns a list of search query strings optimized for the jurisdiction.
        """
        if not self.llm_client:
            # Fallback to static templates
            return self._static_queries(jurisdiction_name, jurisdiction_type)
        
        try:
            # Fetch prompt from DB
            prompt_template = await self.get_discovery_prompt()
            prompt = prompt_template.format(
                jurisdiction=jurisdiction_name,
                jurisdiction_type=jurisdiction_type
            )
            
            logger.info(f"🧠 Generating discovery queries for {jurisdiction_name} using GLM-4.7...")
            
            response = await self.llm_client.chat_completion(
                messages=[LLMMessage(role=MessageRole.USER, content=prompt)],
                model="glm-4.7"
            )
            
            # Parse JSON array from response
            content = response.content.strip()
            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            queries = json.loads(content)
            
            if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
                logger.info(f"✅ Generated {len(queries)} queries for {jurisdiction_name}")
                return queries
            else:
                logger.warning("LLM returned invalid query format, using fallback")
                return self._static_queries(jurisdiction_name, jurisdiction_type)
                
        except Exception as e:
            logger.error(f"LLM query generation failed: {e}")
            return self._static_queries(jurisdiction_name, jurisdiction_type)
    
    def _static_queries(self, jurisdiction_name: str, jurisdiction_type: str) -> List[str]:
        """Fallback static query templates."""
        templates = {
            "city": [
                f"{jurisdiction_name} city council meetings",
                f"{jurisdiction_name} housing ordinance",
                f"{jurisdiction_name} zoning updates",
                f"{jurisdiction_name} ADU regulations",
            ],
            "county": [
                f"{jurisdiction_name} county board of supervisors meetings",
                f"{jurisdiction_name} county housing policy",
                f"{jurisdiction_name} county zoning",
            ],
        }
        return templates.get(jurisdiction_type, templates["city"])

    async def discover_sources(
        self, jurisdiction_name: str, jurisdiction_type: str = "city"
    ) -> List[Dict[str, Any]]:
        """
        Discover potential sources for a given jurisdiction.

        Uses LLM-generated queries for comprehensive discovery.
        
        :param jurisdiction_name: The name of the jurisdiction (e.g., "San Jose").
        :param jurisdiction_type: The type of jurisdiction ("city" or "county").
        :return: A list of potential sources, each a dictionary with search result info.
        """
        # Generate queries using LLM
        queries = await self.generate_queries(jurisdiction_name, jurisdiction_type)
        
        all_results = []
        seen_urls = set()
        
        for query in queries:
            logger.info(f"🔍 Searching: {query}")
            try:
                search_results = await self.search_client.search(query)
                for result in search_results:
                    if result.url and result.url not in seen_urls:
                        seen_urls.add(result.url)
                        result_dict = result.dict() if hasattr(result, 'dict') else result.model_dump()
                        result_dict['discovery_query'] = query  # Track which query found this
                        all_results.append(result_dict)
            except Exception as e:
                logger.warning(f"Search failed for query '{query}': {e}")
                continue
        
        logger.info(f"✅ Discovery complete: {len(all_results)} unique URLs found")
        return all_results
