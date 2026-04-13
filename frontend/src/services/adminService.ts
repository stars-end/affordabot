const API_URL = '';
const NO_STORE_FETCH: RequestInit = { cache: 'no-store' };

export interface Source {
    id: string;
    jurisdiction_id: string;
    url: string;
    type: string;
    status: string;
    source_method: string;
    handler?: string;
    last_scraped_at?: string;
}

export interface ScrapeTask {
    task_id: string;
    jurisdiction: string;
    status: 'queued' | 'running' | 'completed' | 'failed';
    message: string;
    timestamp: string;
}

export interface ScrapeHistory {
    id: string;
    jurisdiction: string;
    timestamp: string;
    bills_found: number;
    status: 'success' | 'partial' | 'failed';
    error?: string;
}

export interface Jurisdiction {
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

export interface JurisdictionDashboardStats {
    jurisdiction: string;
    last_scrape: string | null;
    total_raw_scrapes: number;
    processed_scrapes: number;
    total_bills: number;
    pipeline_status: 'healthy' | 'degraded' | 'unknown';
    active_alerts: string[];
}

export interface SubstrateRun {
    run_id: string;
    first_created_at: string | null;
    last_created_at: string | null;
    status: 'healthy' | 'has_errors' | 'captured_only' | string;
    raw_scrapes_total: number;
    promoted_substrate_count: number;
    durable_raw_count: number;
    captured_candidate_count: number;
    retrievable_count: number;
    raw_capture_error_count: number;
}

export interface SubstrateRunsResponse {
    run_id_key: string;
    limit: number;
    offset: number;
    runs: SubstrateRun[];
}

export interface SubstrateFailureBucket {
    reason?: string;
    count?: number;
    [key: string]: unknown;
}

export interface SubstrateRunDetail {
    run_id: string;
    run_id_key: string;
    summary: Record<string, unknown>;
    failure_buckets: SubstrateFailureBucket[];
    jurisdiction_names: string[];
    raw_scrapes_total: number;
    latest_created_at: string | null;
}

export interface SubstrateRawScrapeRow {
    id: string;
    created_at: string | null;
    url: string | null;
    source_url: string | null;
    source_name: string | null;
    source_type: string | null;
    jurisdiction_name: string | null;
    storage_uri: string | null;
    document_id: string | null;
    error_message: string | null;
    document_type: string | null;
    content_class: string | null;
    trust_tier: string | null;
    promotion_state: string | null;
    promotion_reason_category: string | null;
    ingestion_truth_stage: string | null;
    ingestion_truth_retrievable: boolean;
    content_preview: string;
    content_length: number;
}

export interface SubstrateRunRawScrapesResponse {
    run_id: string;
    run_id_key: string;
    limit: number;
    offset: number;
    filters: {
        jurisdiction_name?: string | null;
        document_type?: string | null;
        promotion_state?: string | null;
        trust_tier?: string | null;
        content_class?: string | null;
    };
    raw_scrapes: SubstrateRawScrapeRow[];
}

export interface SubstrateRawScrapeDetail extends SubstrateRawScrapeRow {
    metadata?: Record<string, unknown>;
    ingestion_truth?: Record<string, unknown>;
}

export interface SubstrateRunRawFilters {
    jurisdiction_name?: string;
    document_type?: string;
    promotion_state?: string;
    trust_tier?: string;
    content_class?: string;
}

export interface PipelineFreshness {
    status: string;
    fresh_hours: number;
    stale_usable_ceiling_hours: number;
    fail_closed_ceiling_hours: number;
    alerts: string[];
}

export interface PipelineCounts {
    search_results: number;
    raw_scrapes: number;
    artifacts: number;
    chunks: number;
    analyses: number;
}

export interface PipelineLatestAnalysis {
    status: 'ready' | 'not_ready' | 'blocked' | string;
    sufficiency_state: string;
    evidence_count: number;
}

export interface PipelineOperatorLinks {
    windmill_run_url?: string | null;
    windmill_workspace?: string | null;
}

export interface PipelineJurisdictionStatus {
    contract_version: string;
    jurisdiction_id: string;
    jurisdiction_name: string;
    source_family: string;
    pipeline_status: string;
    last_success_at: string | null;
    freshness: PipelineFreshness;
    counts: PipelineCounts;
    latest_analysis: PipelineLatestAnalysis;
    alerts: string[];
    operator_links: PipelineOperatorLinks;
}

export interface PipelineRunDetail {
    contract_version: string;
    run_id: string;
    status: string;
    jurisdiction: string;
    source_family: string;
    bill_id: string | null;
    started_at: string | null;
    completed_at: string | null;
    error: string | null;
    trigger_source: string | null;
    counts: PipelineCounts;
    latest_analysis: PipelineLatestAnalysis;
    alerts: string[];
    operator_links: PipelineOperatorLinks;
}

export interface PipelineRunStep {
    contract_version: string;
    step_id: string;
    run_id: string;
    command: string;
    status: string;
    decision_reason: string | null;
    retry_class: string;
    alerts: string[];
    counts: Record<string, number>;
    refs: Record<string, unknown>;
    duration_ms: number;
    error: string | null;
    timestamp: string | null;
}

export interface PipelineRunStepsResponse {
    contract_version: string;
    run_id: string;
    steps: PipelineRunStep[];
}

export interface PipelineEvidenceItem {
    id: string;
    type: string;
    label: string;
    confidence: number | null;
    source_ref: string | null;
}

export interface PipelineRunEvidenceResponse {
    contract_version: string;
    run_id: string;
    evidence_count: number;
    items: PipelineEvidenceItem[];
}

export interface PipelineRefreshResponse {
    contract_version: string;
    status: string;
    decision_reason: string;
    jurisdiction_id: string;
    jurisdiction_name: string;
    source_family: string;
    message: string;
}

export const adminService = {
    // Sources
    async getSources(): Promise<Source[]> {
        const res = await fetch(`${API_URL}/api/sources`);
        if (!res.ok) throw new Error('Failed to fetch sources');
        return res.json();
    },

    async createSource(source: Partial<Source>) {
        const res = await fetch(`${API_URL}/api/sources`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(source),
        });
        if (!res.ok) throw new Error('Failed to create source');
        return res.json();
    },

    async deleteSource(id: string) {
        const res = await fetch(`${API_URL}/api/sources/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete source');
        return res.json();
    },

    // Scrapes
    async getScrapeHistory(): Promise<ScrapeHistory[]> {
        const res = await fetch(`${API_URL}/api/admin/scrapes`);
        if (!res.ok) throw new Error('Failed to fetch scrape history');
        return res.json();
    },

    async triggerScrape(jurisdiction: string, force: boolean): Promise<ScrapeTask> {
        const res = await fetch(`${API_URL}/api/admin/scrape`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jurisdiction, force }),
        });
        if (!res.ok) throw new Error('Failed to trigger scrape');
        return res.json();
    },

    async getTaskStatus(taskId: string): Promise<ScrapeTask> {
        const res = await fetch(`${API_URL}/api/admin/tasks/${taskId}`);
        if (!res.ok) throw new Error('Failed to fetch task status');
        return res.json();
    },

    // Jurisdictions
    async getJurisdictions(): Promise<Jurisdiction[]> {
        const res = await fetch(`${API_URL}/api/admin/jurisdictions`);
        if (!res.ok) throw new Error('Failed to fetch jurisdictions');
        return res.json();
    },

    async updateJurisdiction(id: string, updates: Partial<Jurisdiction>) {
        const res = await fetch(`${API_URL}/api/admin/jurisdictions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
        });
        if (!res.ok) throw new Error('Failed to update jurisdiction');
        return res.json();
    },

    async getJurisdictionDashboard(id: string): Promise<JurisdictionDashboardStats> {
        const res = await fetch(`${API_URL}/api/admin/jurisdiction/${id}/dashboard`);
        if (!res.ok) throw new Error('Failed to fetch dashboard stats');
        return res.json();
    },

    // Pipeline read model
    async getPipelineJurisdictionStatus(jurisdictionId: string, sourceFamily = 'meeting_minutes'): Promise<PipelineJurisdictionStatus> {
        const params = new URLSearchParams({ source_family: sourceFamily });
        const res = await fetch(
            `${API_URL}/api/admin/pipeline/jurisdictions/${encodeURIComponent(jurisdictionId)}/status?${params.toString()}`,
            NO_STORE_FETCH,
        );
        if (!res.ok) throw new Error('Failed to fetch pipeline jurisdiction status');
        return res.json();
    },

    async getPipelineRun(runId: string): Promise<PipelineRunDetail> {
        const res = await fetch(`${API_URL}/api/admin/pipeline/runs/${encodeURIComponent(runId)}`, NO_STORE_FETCH);
        if (!res.ok) throw new Error('Failed to fetch pipeline run');
        return res.json();
    },

    async getPipelineRunSteps(runId: string): Promise<PipelineRunStepsResponse> {
        const res = await fetch(`${API_URL}/api/admin/pipeline/runs/${encodeURIComponent(runId)}/steps`, NO_STORE_FETCH);
        if (!res.ok) throw new Error('Failed to fetch pipeline run steps');
        return res.json();
    },

    async getPipelineRunEvidence(runId: string): Promise<PipelineRunEvidenceResponse> {
        const res = await fetch(`${API_URL}/api/admin/pipeline/runs/${encodeURIComponent(runId)}/evidence`, NO_STORE_FETCH);
        if (!res.ok) throw new Error('Failed to fetch pipeline run evidence');
        return res.json();
    },

    async refreshPipelineJurisdiction(jurisdictionId: string, sourceFamily = 'meeting_minutes'): Promise<PipelineRefreshResponse> {
        const params = new URLSearchParams({ source_family: sourceFamily });
        const res = await fetch(
            `${API_URL}/api/admin/pipeline/jurisdictions/${encodeURIComponent(jurisdictionId)}/refresh?${params.toString()}`,
            { method: 'POST', cache: 'no-store' },
        );
        if (!res.ok) throw new Error('Failed to trigger pipeline refresh');
        return res.json();
    },

    // Substrate explorer
    async getSubstrateRuns(limit = 20, offset = 0, runIdKey = 'manual_run_id'): Promise<SubstrateRunsResponse> {
        const params = new URLSearchParams({
            limit: String(limit),
            offset: String(offset),
            run_id_key: runIdKey,
        });
        const res = await fetch(`${API_URL}/api/admin/substrate/runs?${params.toString()}`, NO_STORE_FETCH);
        if (!res.ok) throw new Error('Failed to fetch substrate runs');
        return res.json();
    },

    async getSubstrateRunDetail(runId: string, runIdKey = 'manual_run_id'): Promise<SubstrateRunDetail> {
        const params = new URLSearchParams({ run_id_key: runIdKey });
        const res = await fetch(
            `${API_URL}/api/admin/substrate/runs/${encodeURIComponent(runId)}?${params.toString()}`,
            NO_STORE_FETCH,
        );
        if (!res.ok) throw new Error('Failed to fetch substrate run detail');
        return res.json();
    },

    async getSubstrateFailureBuckets(runId: string, runIdKey = 'manual_run_id'): Promise<{ failure_buckets: SubstrateFailureBucket[] }> {
        const params = new URLSearchParams({ run_id_key: runIdKey });
        const res = await fetch(
            `${API_URL}/api/admin/substrate/runs/${encodeURIComponent(runId)}/failure-buckets?${params.toString()}`,
            NO_STORE_FETCH,
        );
        if (!res.ok) throw new Error('Failed to fetch substrate failure buckets');
        return res.json();
    },

    async getSubstrateRunRawScrapes(
        runId: string,
        options: { limit?: number; offset?: number; runIdKey?: string; filters?: SubstrateRunRawFilters } = {}
    ): Promise<SubstrateRunRawScrapesResponse> {
        const {
            limit = 50,
            offset = 0,
            runIdKey = 'manual_run_id',
            filters = {},
        } = options;
        const params = new URLSearchParams({
            limit: String(limit),
            offset: String(offset),
            run_id_key: runIdKey,
        });
        Object.entries(filters).forEach(([key, value]) => {
            if (value && value.trim()) {
                params.set(key, value.trim());
            }
        });
        const res = await fetch(
            `${API_URL}/api/admin/substrate/runs/${encodeURIComponent(runId)}/raw-scrapes?${params.toString()}`,
            NO_STORE_FETCH,
        );
        if (!res.ok) throw new Error('Failed to fetch substrate raw rows');
        return res.json();
    },

    async getSubstrateRawScrapeDetail(rawScrapeId: string): Promise<SubstrateRawScrapeDetail> {
        const res = await fetch(`${API_URL}/api/admin/substrate/raw-scrapes/${encodeURIComponent(rawScrapeId)}`, NO_STORE_FETCH);
        if (!res.ok) throw new Error('Failed to fetch substrate raw row detail');
        return res.json();
    }
};
