import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

import { getBackendUrl } from '../../_lib/backendUrl';

export async function GET(request: NextRequest) {
    try {
        const BACKEND_URL = getBackendUrl(
            request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined
        );
        const { searchParams } = new URL(request.url);
        const jurisdiction = searchParams.get('jurisdiction');
        const limit = searchParams.get('limit') || '50';

        let url = `${BACKEND_URL}/admin/scrapes?limit=${limit}`;
        if (jurisdiction) {
            url += `&jurisdiction=${jurisdiction}`;
        }

        const response = await fetch(url);

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
