const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://backend-production-c383.up.railway.app';

export type Jurisdiction = 'saratoga' | 'san-jose' | 'santa-clara-county' | 'california';

export interface Impact {
    impactNumber: number;
    description: string;
    clause: string;
    confidence: number;
    p10: number;
    p25: number;
    p50: number;
    p75: number;
    p90: number;
}

export interface Bill {
    number: string;
    title: string;
    jurisdiction: string;
    status: string;
    impacts: Impact[];
}

export async function scrapeJurisdiction(jurisdiction: Jurisdiction): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/scrape/${jurisdiction}`, {
        method: 'POST',
    });

    if (!response.ok) {
        throw new Error(`Failed to scrape ${jurisdiction}`);
    }

    return await response.json();
}

export async function getBill(jurisdiction: string, billNumber: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/legislation/${jurisdiction}/${billNumber}`);

    if (!response.ok) {
        throw new Error(`Failed to get bill ${billNumber} for ${jurisdiction}`);
    }

    return await response.json();
}

export async function getLegislation(jurisdiction: Jurisdiction, limit: number = 10): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/legislation/${jurisdiction}?limit=${limit}`);

    if (!response.ok) {
        throw new Error(`Failed to get legislation for ${jurisdiction}`);
    }

    return await response.json();
}

export const JURISDICTIONS = [
    { id: 'saratoga', name: 'City of Saratoga', type: 'city' },
    { id: 'san-jose', name: 'City of San Jose', type: 'city' },
    { id: 'santa-clara-county', name: 'County of Santa Clara', type: 'county' },
    { id: 'california', name: 'State of California', type: 'state' },
] as const;
