from __future__ import annotations
import httpx
import hashlib
import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel
from .exceptions import RateLimitError, SearchError

class SearchResult(BaseModel):
    """Single search result."""
    title: str
    url: str
    snippet: str
    published_date: Optional[str] = None
    relevance_score: Optional[float] = None

class WebSearchClient:
    """
    z.ai web search with intelligent caching.
    
    Caching Strategy:
    - L1: In-memory cache (TTL: 1 hour)
    - L2: Supabase cache (TTL: 24 hours)
    
    Cost Savings:
    - Target: 80% cache hit rate
    - Estimated: $450/month → $90/month
    """
    
    def __init__(
        self,
        api_key: str,
        supabase_client: Any,
        memory_cache_ttl: int = 3600,  # 1 hour
        db_cache_ttl: int = 86400       # 24 hours
    ):
        """
        Initialize web search client.
        
        Args:
            api_key: z.ai API key
            supabase_client: Supabase client for persistent cache
            memory_cache_ttl: In-memory cache TTL (seconds)
            db_cache_ttl: Database cache TTL (seconds)
        """
        self.api_key = api_key
        self.supabase = supabase_client
        self.memory_cache: Dict[str, Tuple[List[SearchResult], datetime]] = {}
        self.memory_ttl = memory_cache_ttl
        self.db_ttl = db_cache_ttl
        
        self.base_url = "https://api.z.ai/api/paas/v4/web-search"
        self.http_client = httpx.AsyncClient()
    
    def _generate_cache_key(
        self,
        query: str,
        count: int,
        domains: Optional[List[str]],
        recency: Optional[str]
    ) -> str:
        """Generate cache key from search parameters."""
        params = {
            "query": query,
            "count": count,
            "domains": sorted(domains) if domains else [],
            "recency": recency
        }
        return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    
    async def search(
        self,
        query: str,
        count: int = 10,
        domains: Optional[List[str]] = None,
        recency: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Search with caching.
        
        Args:
            query: Search query
            count: Number of results (1-25)
            domains: Filter by domains (e.g., ["*.gov", "*.edu"])
            recency: Time filter ("1d", "1w", "1m", "1y")
        
        Returns:
            List of search results
        
        Raises:
            RateLimitError: If z.ai rate limit exceeded
            SearchError: If search fails
        """
        cache_key = self._generate_cache_key(query, count, domains, recency)
        
        # L1: Check memory cache
        if cache_key in self.memory_cache:
            results, cached_at = self.memory_cache[cache_key]
            if datetime.now() - cached_at < timedelta(seconds=self.memory_ttl):
                print(f"✅ L1 cache hit: {query}")
                return results
        
        # L2: Check Supabase cache
        db_result = self.supabase.table('web_search_cache').select('*').eq(
            'cache_key', cache_key
        ).execute()
        
        if db_result.data:
            row = db_result.data[0]
            cached_at = datetime.fromisoformat(row['cached_at'])
            if datetime.now() - cached_at < timedelta(seconds=self.db_ttl):
                print(f"✅ L2 cache hit: {query}")
                results = [SearchResult(**r) for r in row['results']]
                # Populate L1 cache
                self.memory_cache[cache_key] = (results, datetime.now())
                return results
        
        # Cache miss: Call z.ai API
        print(f"🔍 Cache miss, calling z.ai: {query}")
        results = await self._call_zai_api(query, count, domains, recency)
        
        # Store in both caches
        self.memory_cache[cache_key] = (results, datetime.now())
        self.supabase.table('web_search_cache').upsert({
            'cache_key': cache_key,
            'query': query,
            'results': [r.model_dump() for r in results],
            'cached_at': datetime.now().isoformat()
        }).execute()
        
        return results
    
    async def _call_zai_api(
        self,
        query: str,
        count: int,
        domains: Optional[List[str]],
        recency: Optional[str]
    ) -> List[SearchResult]:
        """Call z.ai web search API."""
        payload = {
            "query": query,
            "count": count
        }
        
        if domains:
            payload["domains"] = domains
        if recency:
            payload["recency"] = recency
        
        response = await self.http_client.post(
            self.base_url,
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        
        if response.status_code == 429:
            raise RateLimitError("z.ai rate limit exceeded")
        
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise SearchError(f"Search failed: {e}")
            
        data = response.json()
        
        return [SearchResult(**item) for item in data.get("results", [])]
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache hit rate statistics."""
        # Query Supabase for cache stats
        result = self.supabase.rpc('get_cache_stats').execute()
        return result.data
