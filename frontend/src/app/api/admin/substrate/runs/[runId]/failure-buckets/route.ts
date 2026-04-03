import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth } from '../../../../../_lib/fetchUtils';

export const dynamic = 'force-dynamic';

export async function GET(
    request: NextRequest,
    { params }: { params: { runId: string } }
) {
    try {
        const { searchParams } = new URL(request.url);
        const query = new URLSearchParams();
        const runIdKey = searchParams.get('run_id_key');
        if (runIdKey) query.set('run_id_key', runIdKey);

        const path = `/api/admin/substrate/runs/${encodeURIComponent(params.runId)}/failure-buckets${query.toString() ? `?${query.toString()}` : ''}`;
        const response = await fetchWithAuth(request, path);
        if (!response.ok) {
            const error = await response.text();
            return NextResponse.json(
                { error: 'Failed to fetch substrate failure buckets', details: error },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Substrate failure buckets API route error:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
