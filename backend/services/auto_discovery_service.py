"""Service for auto-discovering potential sources for a given jurisdiction."""

from llm_common import WebSearchClient
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

QUERY_TEMPLATES = {
    "city": "city council meetings {jurisdiction}",
    "county": "county board of supervisors meetings {jurisdiction}",
}


class AutoDiscoveryService:
    def __init__(self, search_client: WebSearchClient):
        self.search_client = search_client

    async def discover_sources(
        self, jurisdiction_name: str, jurisdiction_type: str = "city"
    ) -> List[Dict[str, Any]]:
        """
        Discover potential sources for a given jurisdiction.

        :param jurisdiction_name: The name of the jurisdiction (e.g., "San Jose").
        :param jurisdiction_type: The type of jurisdiction ("city" or "county").
        :return: A list of potential sources, each a dictionary with search result info.
        """
        query_template = QUERY_TEMPLATES.get(jurisdiction_type)
        if not query_template:
            logger.warning(
                f"No query template found for jurisdiction type: {jurisdiction_type}"
            )
            return []

        query = query_template.format(jurisdiction=jurisdiction_name)
        logger.info(f"Executing discovery query: {query}")

        try:
            search_results = await self.search_client.search(query)
            return [result.dict() for result in search_results]
        except Exception as e:
            logger.error(f"An error occurred during web search: {e}")
            return []
