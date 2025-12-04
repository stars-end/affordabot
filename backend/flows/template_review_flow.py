"""Prefect flow for weekly template reviews."""

from prefect import flow, task
from supabase import create_client
import os
import asyncio
from services.template_review_service import TemplateReviewService
from llm_common import LLMClient, WebSearchClient

@task(name="review_templates_task")
async def review_templates_task():
    """Run template review analysis."""
    supabase = create_client(
        os.environ['SUPABASE_URL'],
        os.environ['SUPABASE_SERVICE_ROLE_KEY']
    )
    
    llm_client = LLMClient(provider="openai")
    # Assuming WebSearchClient needs api_key
    search_client = WebSearchClient(
        api_key=os.environ.get('Z_AI_API_KEY', 'mock-key'),
        supabase_client=supabase
    )
    
    service = TemplateReviewService(supabase, llm_client, search_client)
    
    print("🔍 Reviewing City templates...")
    reviews = await service.review_templates("city")
    
    print(f"✅ Generated {len(reviews)} template suggestions")
    return reviews

@flow(name="weekly_template_review")
async def weekly_template_review():
    """Weekly job to review and improve scraping templates."""
    await review_templates_task()

if __name__ == "__main__":
    asyncio.run(weekly_template_review())
