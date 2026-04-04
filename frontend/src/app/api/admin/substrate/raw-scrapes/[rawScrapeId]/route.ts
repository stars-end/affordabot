import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth } from '../../../../_lib/fetchUtils';

export const dynamic = 'force-dynamic';

export async function GET(
    request: NextRequest,
    { params }: { params: { rawScrapeId: string } }
) {
    try {
        const path = `/api/admin/substrate/raw-scrapes/${encodeURIComponent(params.rawScrapeId)}`;
        const response = await fetchWithAuth(request, path);
        if (!response.ok) {
            const error = await response.text();
            return NextResponse.json(
                { error: 'Failed to fetch substrate raw row detail', details: error },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Substrate raw row detail API route error:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
