
from typing import List
from llm_common.embeddings.base import EmbeddingService

class MockEmbeddingService(EmbeddingService):
    """
    Mock embedding service for testing/verification without API keys.
    Returns 1536-dimensional zero vectors (OpenAI compatible).
    """
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.1] * 1536 for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return [0.1] * 1536
