export interface Impact {
    relevant_clause: string;
    impact_description: string;
    confidence_score: number;
    p50: number;
    evidence: any[];
}

export interface Legislation {
    id: number;
    bill_number: string;
    title: string;
    text: string;
    status: string;
    impacts: Impact[];
    created_at: string;
}

export interface LegislationResponse {
    jurisdiction: string;
    count: number;
    legislation: Legislation[];
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function getLegislation(jurisdiction: string): Promise<LegislationResponse> {
    const res = await fetch(`${API_BASE}/legislation/${jurisdiction}`);
    if (!res.ok) throw new Error(`Failed to fetch legislation for ${jurisdiction}`);
    return res.json();
}

export async function scrapeJurisdiction(jurisdiction: string): Promise<void> {
    const res = await fetch(`${API_BASE}/scrape/${jurisdiction}`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to scrape ${jurisdiction}`);
    return res.json();
}
