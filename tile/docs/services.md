# AffordaBot Pipeline Services

Backend service classes implementing the data ingestion, LLM analysis, and observability pipeline.

## AnalysisPipeline

**Location:** `backend/services/llm/orchestrator.py`

The main multi-step LLM analysis pipeline for legislation. Orchestrates research, generation, review, and persistence steps.

```python
from services.llm.orchestrator import AnalysisPipeline, DEFAULT_OPENROUTER_FALLBACK_MODEL
from llm_common.core import LLMConfig, LLMClient
from llm_common.providers import ZaiClient, OpenRouterClient
from llm_common.web_search import WebSearchClient
```

```python { .api }
class AnalysisPipeline:
    def __init__(
        self,
        llm_client: LLMClient,
        search_client: WebSearchClient,
        db: PostgresDB,
        fallback_client: Optional[LLMClient] = None,
        retrieval_backend = None,    # LocalPgVectorBackend or similar
        embedding_fn = None,         # async function: (str) -> List[float]
    ) -> None: ...

    async def run(
        self,
        bill_id: str,
        bill_text: str,
        jurisdiction: str,
        models: Dict[str, str],
    ) -> dict:
        # models keys: "research", "generate", "review"
        # Each value is an LLM model identifier (e.g., "glm-4.7")
        # Returns pipeline result dict with analysis data
        ...
```

**Constants:**

```python { .api }
DEFAULT_OPENROUTER_FALLBACK_MODEL: str = "openrouter/auto"

CANONICAL_PIPELINE_STEPS: List[str] = [
    "ingestion_source",
    "chunk_index",
    "research_discovery",
    "impact_discovery",
    "mode_selection",
    "parameter_resolution",
    "sufficiency_gate",
    "generate",
    "parameter_validation",
    "review",
    "refine",
    "persistence",
    "notify_debug",
]

STEP_INDEX: Dict[str, int]  # maps step name -> 1-based index
```

**Exception:**

```python { .api }
class PrefixFixtureError(RuntimeError):
    # Raised when replay/fixture payloads are missing or invalid
    ...
```

**Usage example:**

```python
import os
from db.postgres_client import PostgresDB
from services.llm.orchestrator import AnalysisPipeline, DEFAULT_OPENROUTER_FALLBACK_MODEL
from llm_common.core import LLMConfig
from llm_common.providers import ZaiClient, OpenRouterClient
from services.llm.web_search_factory import create_web_search_client

async def run_pipeline():
    db = PostgresDB()
    await db.connect()

    llm_config = LLMConfig(
        api_key=os.environ["ZAI_API_KEY"],
        provider="zai",
        default_model="glm-4.7"
    )
    llm_client = ZaiClient(llm_config)

    # Optional fallback client
    fallback_client = None
    if os.environ.get("OPENROUTER_API_KEY"):
        or_config = LLMConfig(
            api_key=os.environ["OPENROUTER_API_KEY"],
            provider="openrouter",
            default_model=DEFAULT_OPENROUTER_FALLBACK_MODEL
        )
        fallback_client = OpenRouterClient(or_config)

    search_client = create_web_search_client(api_key=os.environ["ZAI_API_KEY"])

    pipeline = AnalysisPipeline(
        llm_client, search_client, db,
        fallback_client=fallback_client
    )

    result = await pipeline.run(
        bill_id="AB-1234",
        bill_text="Full bill text...",
        jurisdiction="California",
        models={
            "research": "glm-4.7",
            "generate": "glm-4.7",
            "review": "glm-4.7"
        }
    )
    await db.close()
    return result
```

---

## BaseScraper

**Location:** `backend/services/scraper/base.py`

Abstract base class for all jurisdiction-specific legislation scrapers.

```python
from services.scraper.base import BaseScraper, ScrapedBill
from services.scraper.registry import SCRAPERS
```

```python { .api }
class ScrapedBill(BaseModel):
    bill_number: str
    title: str
    text: Optional[str] = None
    introduced_date: Optional[date] = None
    status: Optional[str] = None
    raw_html: Optional[str] = None

class BaseScraper(ABC):
    def __init__(self, jurisdiction_name: str) -> None: ...

    @abstractmethod
    async def scrape(self) -> List[ScrapedBill]:
        # Scrape legislation from the jurisdiction's source
        ...

    async def check_health(self) -> bool:
        # Check if the source is accessible; returns True by default
        ...

    jurisdiction_name: str  # instance attribute
```

**Concrete scraper classes** (all subclass `BaseScraper`):

```python { .api }
# Registered in services/scraper/registry.py:
SCRAPERS: Dict[str, Tuple[Type[BaseScraper], str]] = {
    "saratoga":              (SaratogaScraper, "city"),
    "san-jose":              (SanJoseScraper, "city"),
    "sanjose":               (SanJoseScraper, "city"),
    "san-jose-cityscrapers": (SanJoseCSAdapter, "city"),
    "santa-clara-county":    (SantaClaraCountyScraper, "county"),
    "california":            (CaliforniaStateScraper, "state"),
    "nyc":                   (NYCScraper, "city"),
}
# Each entry: (scraper_class, jurisdiction_type)
```

**Usage:**

```python
from services.scraper.registry import SCRAPERS

scraper_class, jur_type = SCRAPERS["california"]
scraper = scraper_class()
bills = await scraper.scrape()      # List[ScrapedBill]
healthy = await scraper.check_health()  # bool
```

---

## GlassBoxService

**Location:** `backend/services/glass_box.py`

Pipeline observability service. Retrieves agent execution traces and pipeline run data from the database (and optionally from legacy file-based traces).

```python
from services.glass_box import GlassBoxService, AgentStep, PipelineStep
```

```python { .api }
class AgentStep(BaseModel):
    tool: str
    args: Dict[str, Any]
    result: Any
    task_id: str
    query_id: str
    timestamp: int          # Unix timestamp (ms)

class PipelineStep(BaseModel):
    id: str
    run_id: str
    step_number: int
    step_name: str          # one of CANONICAL_PIPELINE_STEPS
    status: str
    input_context: Optional[Dict[str, Any]] = None
    output_result: Optional[Dict[str, Any]] = None
    model_info: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    created_at: Any = None

class GlassBoxService:
    def __init__(
        self,
        db_client: Any = None,      # PostgresDB instance
        trace_dir: str = ".traces", # legacy file-based trace directory
    ) -> None: ...

    async def get_traces_for_query(self, query_id: str) -> List[AgentStep]:
        # Get full execution trace for an agent session
        ...

    async def list_queries(self) -> List[str]:
        # List all recorded agent session IDs
        ...

    async def get_pipeline_steps(self, run_id: str) -> List[PipelineStep]:
        # Get granular execution steps for a pipeline run
        ...

    async def list_pipeline_runs(self) -> dict:
        # List recent pipeline runs summary
        ...

    async def get_pipeline_run(self, run_id: str) -> Optional[dict]:
        # Get details for a specific pipeline run
        ...
```

---

## AutoDiscoveryService

**Location:** `backend/services/auto_discovery_service.py`

LLM-powered service for discovering government source URLs for a given jurisdiction. Uses GLM-4.7 to generate search queries dynamically.

```python
from services.auto_discovery_service import AutoDiscoveryService
from llm_common.providers import ZaiClient
from llm_common.web_search import WebSearchClient
```

```python { .api }
class AutoDiscoveryService:
    def __init__(
        self,
        search_client: WebSearchClient,
        llm_client: Optional[ZaiClient] = None,  # auto-initializes from ZAI_API_KEY if not provided
        db_client: Optional[Any] = None,           # PostgresDB for prompt retrieval
    ) -> None: ...

    async def get_discovery_prompt(self) -> str:
        # Fetch discovery prompt from DB (prompt_type="discovery_query_generator")
        # Falls back to DEFAULT_DISCOVERY_PROMPT if not found
        ...

    async def generate_queries(
        self,
        jurisdiction_name: str,
        jurisdiction_type: str = "city",
    ) -> List[str]:
        # Generate search queries using LLM (GLM-4.7)
        # Falls back to static templates if LLM unavailable
        ...

    async def discover_sources(
        self,
        jurisdiction_name: str,
        jurisdiction_type: str = "city",
    ) -> List[Dict[str, Any]]:
        # Discover potential sources for a jurisdiction
        # Returns list of search result dicts, each with a "discovery_query" field added
        ...
```

**jurisdiction_type values:** `"city"` | `"county"`

---

## SourceService

**Location:** `backend/services/source_service.py`

Service class for CRUD operations on data sources.

```python
from services.source_service import SourceService, SourceCreate, SourceUpdate
```

```python { .api }
class SourceCreate(BaseModel):
    jurisdiction_id: str
    url: str
    type: str           # "meeting" | "legislation" | other
    source_method: str = "scrape"
    handler: Optional[str] = None

class SourceUpdate(BaseModel):
    url: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    source_method: Optional[str] = None
    handler: Optional[str] = None

class SourceService:
    def __init__(self, db: PostgresDB) -> None: ...

    async def get_sources(
        self, jurisdiction_id: Optional[str] = None
    ) -> List[Dict[str, Any]]: ...

    async def get_source(self, source_id: str) -> Optional[Dict[str, Any]]: ...

    async def create_source(self, source: SourceCreate) -> Dict[str, Any]: ...

    async def update_source(
        self, source_id: str, source: SourceUpdate
    ) -> Dict[str, Any]: ...

    async def delete_source(self, source_id: str) -> None: ...
```
