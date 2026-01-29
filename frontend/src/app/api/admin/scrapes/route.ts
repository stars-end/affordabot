import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth } from '../../_lib/fetchUtils';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
    try {
        const { searchParams } = new URL(request.url);
        const jurisdiction = searchParams.get('jurisdiction');
        const limit = searchParams.get('limit') || '50';

        let path = `/api/admin/scrapes?limit=${limit}`;
        if (jurisdiction) {
            path += `&jurisdiction=${jurisdiction}`;
        }

        const response = await fetchWithAuth(request, path);

        if (!response.ok) {
            const error = await response.text();
            return NextResponse.json(
                { error: 'Failed to fetch scrape history', details: error },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('API route error:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
