import os
from typing import Type, TypeVar, Optional
import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel
from backend.contracts.extraction import ExtractorClient
from backend.clients.web_reader_client import WebReaderClient

T = TypeVar("T", bound=BaseModel)

class ZaiExtractor(ExtractorClient):
    """
    Extractor implementation using Z.ai Web Reader for content fetching
    and Z.ai LLM (via Instructor) for structured extraction.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "glm-4.5"):
        self.api_key = api_key or os.environ.get("ZAI_API_KEY")
        
        self.web_reader = WebReaderClient(api_key=self.api_key)
        self.model = model

        # Initialize instructor client
        if self.api_key:
            self.client = instructor.from_openai(
                AsyncOpenAI(
                    api_key=self.api_key,
                    base_url="https://api.z.ai/api/coding/paas/v4",
                )
            )
        else:
            self.client = None

    async def extract(self, url: str, schema: Type[T]) -> T:
        if not self.api_key or not self.client:
             raise ValueError("ZAI_API_KEY is not set")

        # 1. Fetch content
        # Pass extra args if WebReaderClient supports them
        # Increased timeout to 60s for SPAs
        content_data = await self.web_reader.fetch_content(url, timeout=60)
        # Handle wrapping in 'reader_result' if present
        data_block = content_data.get("reader_result", content_data)
        markdown = data_block.get("content", "")

        if not markdown:
            raise ValueError(f"No content returned from Web Reader for {url}")
        
        # 2. Extract structured data
        # Note: Instructor patches the client, so we use response_model
        return await self.client.chat.completions.create(
            model=self.model,
            response_model=schema,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise data extractor. Extract the requested data structure from the provided text."
                },
                {
                    "role": "user",
                    "content": f"Extract the data from this content:\n\n{markdown}"
                }
            ],
        )
