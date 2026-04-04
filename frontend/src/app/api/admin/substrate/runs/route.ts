import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth } from '../../../_lib/fetchUtils';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
    try {
        const { searchParams } = new URL(request.url);
        const params = new URLSearchParams();

        const limit = searchParams.get('limit');
        const offset = searchParams.get('offset');
        const runIdKey = searchParams.get('run_id_key');

        if (limit) params.set('limit', limit);
        if (offset) params.set('offset', offset);
        if (runIdKey) params.set('run_id_key', runIdKey);

        const path = `/api/admin/substrate/runs${params.toString() ? `?${params.toString()}` : ''}`;
        const response = await fetchWithAuth(request, path);
        if (!response.ok) {
            const error = await response.text();
            return NextResponse.json(
                { error: 'Failed to fetch substrate runs', details: error },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Substrate runs API route error:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
