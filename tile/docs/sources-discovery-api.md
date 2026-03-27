# AffordaBot Sources & Discovery API

## Sources API

Admin-protected CRUD endpoints for managing data sources (URLs that the scrapers fetch from).

**Prefix:** `/api/admin/sources`
**Auth:** Clerk admin JWT required (see [Authentication](./auth.md))

### List Sources

```python { .api }
GET /api/admin/sources/?jurisdiction_id={id}
# jurisdiction_id: Optional[str] — filter by jurisdiction UUID
# Returns: List[dict]  # source records
# Each source record:
# {
#   "id": str,
#   "jurisdiction_id": str,
#   "url": str,
#   "type": str,          # "meeting" | "legislation" | other
#   "source_method": str, # "scrape" | other
#   "handler": str | None,
#   "status": str | None
# }
```

### Create Source

```python { .api }
POST /api/admin/sources/
# Body:
class SourceCreate(BaseModel):
    jurisdiction_id: str
    url: str
    type: str           # "meeting" | "legislation" | other
    source_method: str = "scrape"
    handler: Optional[str] = None
# Returns: dict  # created source record
```

### Get Source

```python { .api }
GET /api/admin/sources/{source_id}
# source_id: str — UUID
# Returns: dict  # source record
# Errors: 404 — source not found
```

### Update Source

```python { .api }
PATCH /api/admin/sources/{source_id}
# source_id: str — UUID
# Body:
class SourceUpdate(BaseModel):
    url: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    source_method: Optional[str] = None
    handler: Optional[str] = None
# Returns: dict  # updated source record
```

### Delete Source

```python { .api }
DELETE /api/admin/sources/{source_id}
# source_id: str — UUID
# Returns: {"status": "success"}
```

---

## Discovery API

Auto-discovery endpoint for finding potential government data sources for a jurisdiction. No authentication required.

**Prefix:** `/api/discovery`

### Run Discovery

```python { .api }
POST /api/discovery/run
# Body:
class DiscoveryRequest(BaseModel):
    jurisdiction_name: str   # e.g., "San Jose", "California"
    jurisdiction_type: str = "city"   # "city" | "county"
# Returns: List[Dict[str, Any]]
# Each result is a search result dict with:
# {
#   "url": str,
#   "title": str,
#   "snippet": str,
#   "discovery_query": str,   # the query that found this result
#   ...                        # other fields from WebSearchClient
# }
```

**How it works:**
1. Uses GLM-4.7 (Z.ai) to generate 8–10 search queries for the jurisdiction
2. Falls back to static query templates if LLM is unavailable
3. Runs each query via the web search client
4. Returns deduplicated results with the originating query tracked

**Focus areas for generated queries:**
- City council meetings, agendas, and minutes
- Housing policy and legislation updates
- Zoning ordinances and land use regulations
- ADU (Accessory Dwelling Unit) policies
- Rent control and tenant protection laws
- Cost of living and affordability assessments
- Public housing programs and initiatives

---

## Frontend Proxy Routes

The Next.js frontend provides these proxy routes for client-side use:

```typescript { .api }
// GET /api/sources?jurisdiction_id={id}
// → proxies to GET /api/admin/sources/?jurisdiction_id={id}

// POST /api/sources/
// → proxies to POST /api/admin/sources/

// GET /api/sources/{id}
// → proxies to GET /api/admin/sources/{id}

// PATCH /api/sources/{id}
// → proxies to PATCH /api/admin/sources/{id}

// DELETE /api/sources/{id}
// → proxies to DELETE /api/admin/sources/{id}

// POST /api/discovery/run
// → proxies to POST /api/discovery/run
```

All proxy routes forward the `Authorization` header from the Next.js request to the backend.
