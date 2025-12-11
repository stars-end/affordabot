import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add paths
backend_root = str(Path(__file__).parent.parent.parent)
sys.path.append(backend_root)
llm_common_path = str(Path(__file__).parent.parent.parent.parent / "llm-common")
sys.path.append(llm_common_path)

from services.llm.orchestrator import AnalysisPipeline, BillAnalysis, ReviewCritique  # noqa: E402
from llm_common.core import LLMClient, WebSearchResponse, WebSearchResult, LLMConfig  # noqa: E402

# Mocks
class MockWebSearchClient:
    async def search(self, query: str, **kwargs) -> WebSearchResponse:
        print(f"MockSearch: Searching for '{query}'")
        return WebSearchResponse(
            query=query,
            results=[
                WebSearchResult(
                    url="http://example.com/doc",
                    title="Example Document",
                    snippet="This is a snippet relevant to the bill.",
                    content="Full content...",
                    published_date="2025-01-01",
                    domain="example.com",
                    relevance_score=0.9
                )
            ],
            total_results=1,
            search_time_ms=100,
            cached=False,
            cost_usd=0.0,
            provider="mock"
        )

class MockLLMClient(LLMClient):
    def __init__(self):
        config = LLMConfig(api_key="mock", provider="openai", default_model="gpt-4o", budget_limit_usd=100.0)
        super().__init__(config)

    async def validate_api_key(self) -> bool:
        return True

    async def stream_completion(self, messages, model=None, **kwargs):
        yield "chunk"

    async def chat_completion(self, messages, model=None, **kwargs):
        # This is what LLMClient expects.
        # But our code calls .chat() or .generate() which might be extensions.
        # We'll implement them below.
        pass

    async def generate(self, model, messages, **kwargs):
        content = messages[-1]['content']
        # TaskPlanner request
        if "Available Tools" in content: 
            print("MockLLM: Generating Task Plan")
            return MagicMock(content="""
            {
                "reasoning": "Plan research.",
                "steps": [
                    {
                        "id": "1",
                        "description": "Search for bill context",
                        "tool_name": "web_search",
                        "tool_arguments": {"query": "bill context"}
                    }
                ]
            }
            """)
        return MagicMock(content="Mock response")

    async def chat(self, messages, response_model=None, **kwargs):
        print(f"MockLLM: Chat request for {response_model}")
        if response_model == BillAnalysis:
            return BillAnalysis(
                summary="Summary",
                impacts=[],
                confidence=1.0,
                sources=["http://example.com/doc"]
            )
        if response_model == ReviewCritique:
            return ReviewCritique(
                passed=True,
                critique="Good",
                missing_impacts=[],
                factual_errors=[]
            )
        return MagicMock(content="Mock chat response")

class MockCostTracker:
    async def track(self, **kwargs):
        pass

class MockDB:
    async def get_or_create_jurisdiction(self, name, type):
        return "mock_jurisdiction_id"
    async def store_legislation(self, j_id, data):
        return "mock_leg_id"
    async def store_impacts(self, l_id, impacts):
        return True

async def main():
    print("🚀 Verifying Agent Pipeline...")
    
    llm = MockLLMClient()
    search = MockWebSearchClient()
    # cost = MockCostTracker() # Removed
    db = MockDB()
    
    pipeline = AnalysisPipeline(llm, search, db)
    
    try:
        result = await pipeline.run(
            bill_id="Test-Bill-1",
            bill_text="This is a test bill.",
            jurisdiction="Mock City",
            models={"research": "mock", "generate": "mock", "review": "mock"}
        )
        print("✅ Pipeline ran successfully!")
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
