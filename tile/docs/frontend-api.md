# AffordaBot Frontend API Client

**Location:** `frontend/src/lib/api.ts`

TypeScript API client for interacting with the AffordaBot backend from the Next.js frontend.

## Import

```typescript
import {
    scrapeJurisdiction,
    getBill,
    getLegislation,
    JURISDICTIONS,
} from '@/lib/api';
import type { Jurisdiction, SufficiencyState, Impact, Bill } from '@/lib/api';
```

## Configuration

```typescript { .api }
// Base URL resolved in order:
// 1. process.env.NEXT_PUBLIC_API_URL
// 2. process.env.VITE_API_URL
// 3. 'https://backend-production-c383.up.railway.app' (default)
const API_BASE_URL: string;
```

## Types

```typescript { .api }
type Jurisdiction = 'saratoga' | 'san-jose' | 'santa-clara-county' | 'california';

type SufficiencyState =
    | 'research_incomplete'
    | 'insufficient_evidence'
    | 'qualitative_only'
    | 'quantified';

interface Impact {
    impactNumber: number;
    description: string;
    clause: string;
    confidence: number | null;        // confidence_score (0.0–1.0)
    p10: number | null;               // scenario_bounds.conservative
    p25: number | null;
    p50: number | null;               // scenario_bounds.central (annual $/household)
    p75: number | null;
    p90: number | null;               // scenario_bounds.aggressive
    isQuantified?: boolean;
    numericBasis?: string | null;
    estimateMethod?: string | null;
    evidence?: Array<{
        source_name: string;
        url: string;
        excerpt: string;
        source_tier?: string | null;  // "tier_a" | "tier_b" | "tier_c"
    }>;
    chainOfCausality?: string;
}

interface Bill {
    number: string;
    title: string;
    jurisdiction: string;
    status: string;
    sufficiencyState?: SufficiencyState | null;
    insufficiencyReason?: string | null;
    quantificationEligible?: boolean;
    impacts: Impact[];
}
```

## Functions

### scrapeJurisdiction

Trigger scraping and LLM analysis for a jurisdiction.

```typescript { .api }
async function scrapeJurisdiction(jurisdiction: Jurisdiction): Promise<any>;
// Calls: POST {API_BASE_URL}/scrape/{jurisdiction}
// Returns: { jurisdiction: string, processed: number, skipped: number, errors: Array }
// Throws: Error if response is not ok
```

### getBill

Fetch details for a specific bill.

```typescript { .api }
async function getBill(jurisdiction: string, billNumber: string): Promise<any>;
// Calls: GET {API_BASE_URL}/legislation/{jurisdiction}/{billNumber}
// Returns: bill detail object from the backend
// Throws: Error if response is not ok
```

### getLegislation

Fetch stored legislation for a jurisdiction.

```typescript { .api }
async function getLegislation(
    jurisdiction: Jurisdiction,
    limit: number = 10
): Promise<any>;
// Calls: GET {API_BASE_URL}/legislation/{jurisdiction}?limit={limit}
// Returns: { jurisdiction: string, count: number, legislation: Array }
// Throws: Error if response is not ok
```

## Constants

```typescript { .api }
const JURISDICTIONS: readonly [
    { id: 'saratoga';            name: 'City of Saratoga';        type: 'city' },
    { id: 'san-jose';            name: 'City of San Jose';        type: 'city' },
    { id: 'santa-clara-county';  name: 'County of Santa Clara';  type: 'county' },
    { id: 'california';          name: 'State of California';     type: 'state' },
];
```

## Usage Examples

```typescript
import { getLegislation, getBill, scrapeJurisdiction, JURISDICTIONS } from '@/lib/api';

// Fetch all legislation for a jurisdiction
const data = await getLegislation('california', 20);
for (const bill of data.legislation) {
    console.log(bill.bill_number, bill.title, bill.total_impact_p50);
}

// Fetch a specific bill
const bill = await getBill('california', 'AB-1234');
for (const impact of bill.impacts) {
    if (impact.p50 != null) {
        console.log(`Impact ${impact.impact_number}: $${impact.p50}/year`);
    }
}

// Trigger scraping (admin action)
const result = await scrapeJurisdiction('saratoga');
console.log(`Processed ${result.processed} bills, skipped ${result.skipped}`);

// Use JURISDICTIONS for UI rendering
for (const j of JURISDICTIONS) {
    console.log(j.id, j.name, j.type);
}
```

---

## PromptService

**Location:** `frontend/src/services/PromptService.ts`

TypeScript service for managing LLM system prompts via the admin API.

```typescript
import { promptService } from '@/services/PromptService';
import type { SystemPrompt } from '@/services/PromptService';
```

### Types

```typescript { .api }
interface SystemPrompt {
    id: string;
    prompt_type: string;      // e.g., "legislation_analysis"
    system_prompt: string;
    description?: string;
    is_active: boolean;
    version: number;          // auto-incremented on each update
}
```

### Methods

```typescript { .api }
class PromptService {
    async getPrompts(): Promise<SystemPrompt[]>;
    // GET /api/admin/prompts
    // Throws: Error if request fails

    async updatePrompt(
        promptType: string,
        content: string,
        description?: string,   // Note: description not forwarded to backend currently
    ): Promise<SystemPrompt>;
    // POST /api/admin/prompts with body {type, system_prompt}
    // Returns the updated prompt (fetches after update)
    // Throws: Error with backend detail message on failure

    async getPrompt(promptType: string): Promise<SystemPrompt>;
    // GET /api/admin/prompts/{promptType}
    // Throws: Error if not found
}

export const promptService: PromptService;   // singleton instance
```

---

## adminService

**Location:** `frontend/src/services/adminService.ts`

TypeScript service object for admin operations (sources, scrapes, jurisdictions) via Next.js proxy routes.

```typescript
import { adminService } from '@/services/adminService';
import type { Source, ScrapeTask, ScrapeHistory, Jurisdiction, JurisdictionDashboardStats } from '@/services/adminService';
```

### Types

```typescript { .api }
interface Source {
    id: string;
    jurisdiction_id: string;
    url: string;
    type: string;              // "meeting" | "legislation" | other
    status: string;
    source_method: string;     // "scrape" | other
    handler?: string;
    last_scraped_at?: string;
}

interface ScrapeTask {
    task_id: string;
    jurisdiction: string;
    status: 'queued' | 'running' | 'completed' | 'failed';
    message: string;
    timestamp: string;
}

interface ScrapeHistory {
    id: string;
    jurisdiction: string;
    timestamp: string;
    bills_found: number;
    status: 'success' | 'partial' | 'failed';
    error?: string;
}

interface Jurisdiction {
    id: string;
    name: string;
    type: string;
    scrape_url?: string;
    api_type?: 'openstates' | 'legistar' | null;
    api_key_env?: string;
    openstates_jurisdiction_id?: string;
    scraper_class?: string;
    use_web_scraper_fallback?: boolean;
    source_priority?: 'api_first' | 'web_first' | 'api_only' | 'web_only' | 'both_merge';
}

interface JurisdictionDashboardStats {
    jurisdiction: string;
    last_scrape: string | null;
    total_raw_scrapes: number;
    processed_scrapes: number;
    total_bills: number;
    pipeline_status: 'healthy' | 'degraded' | 'unknown';
    active_alerts: string[];
}
```

### Methods

```typescript { .api }
export const adminService: {
    // Sources (via Next.js proxy → /api/admin/sources/)
    getSources(): Promise<Source[]>;
    // GET /api/sources

    createSource(source: Partial<Source>): Promise<Source>;
    // POST /api/sources

    deleteSource(id: string): Promise<any>;
    // DELETE /api/sources/{id}

    // Scrapes
    getScrapeHistory(): Promise<ScrapeHistory[]>;
    // GET /api/admin/scrapes

    triggerScrape(jurisdiction: string, force: boolean): Promise<ScrapeTask>;
    // POST /api/admin/scrape with body {jurisdiction, force}

    getTaskStatus(taskId: string): Promise<ScrapeTask>;
    // GET /api/admin/tasks/{taskId}

    // Jurisdictions
    getJurisdictions(): Promise<Jurisdiction[]>;
    // GET /api/admin/jurisdictions

    updateJurisdiction(id: string, updates: Partial<Jurisdiction>): Promise<Jurisdiction>;
    // PUT /api/admin/jurisdictions/{id}

    getJurisdictionDashboard(id: string): Promise<JurisdictionDashboardStats>;
    // GET /api/admin/jurisdiction/{id}/dashboard
}
```

---

## Next.js API Route Proxy Layer

**Location:** `frontend/src/app/api/`

The frontend also exposes Next.js API routes that proxy backend calls while forwarding Clerk authentication headers. These are consumed by the admin dashboard pages.

```typescript { .api }
// Utility used by all admin proxy routes:
// fetchWithAuth(request: NextRequest, backendPath: string, options?: RequestInit): Promise<Response>
// Located at: frontend/src/app/api/_lib/fetchUtils.ts
```

| Next.js Route | Method | Backend Endpoint |
|---------------|--------|-----------------|
| `/api/search?q={query}` | GET | `GET /api/bills/search?q={query}` |
| `/api/sources` | GET | `GET /api/admin/sources/` |
| `/api/sources` | POST | `POST /api/admin/sources/` |
| `/api/sources/{id}` | GET/PATCH/DELETE | `/api/admin/sources/{id}` |
| `/api/admin/alerts` | GET | `GET /api/admin/alerts` |
| `/api/admin/analyses` | GET | Backend analyses endpoint |
| `/api/admin/jurisdictions` | GET | `GET /api/admin/jurisdictions` |
| `/api/admin/jurisdictions/{id}` | GET | `GET /api/admin/jurisdictions/{id}` |
| `/api/admin/jurisdiction/{id}/dashboard` | GET | `GET /api/admin/jurisdiction/{id}/dashboard` |
| `/api/admin/reviews` | GET/POST | `/api/admin/reviews` |
| `/api/admin/reviews/{id}` | PATCH | `/api/admin/reviews/{id}` |
| `/api/admin/analyze` | POST | `POST /api/admin/analyze` |
| `/api/admin/health/models` | GET | `GET /api/admin/health/models` |
| `/api/admin/models` | GET | `GET /api/admin/models` |
| `/api/admin/scrape` | POST | `POST /scrape/{jurisdiction}` |
| `/api/admin/pipeline-runs` | GET | `GET /api/admin/pipeline-runs` |
| `/api/admin/pipeline-runs/{id}` | GET | `GET /api/admin/pipeline-runs/{id}` |
| `/api/admin/scrapes` | GET | `GET /api/admin/scrapes` |
| `/api/admin/prompts/{type}` | GET/POST | Prompts endpoints |
| `/api/discovery/run` | POST | `POST /api/discovery/run` |

### Search Route

```typescript { .api }
// GET /api/search?q={query}
// q: string (required) — search query (minimum 2 chars)
// Returns on success:
// {
//   "results": [{ "bill_id": str, "title": str, "jurisdiction": str, "status": str }],
//   "count": number
// }
// Returns on failure (graceful degradation):
// { "results": [], "message": string }
```
