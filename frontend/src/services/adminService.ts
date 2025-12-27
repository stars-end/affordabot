const API_URL = '';

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
    }
};
