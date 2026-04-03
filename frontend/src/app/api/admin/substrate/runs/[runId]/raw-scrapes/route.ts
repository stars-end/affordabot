import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth } from '../../../../../_lib/fetchUtils';

export const dynamic = 'force-dynamic';

const PASSTHROUGH_FILTER_KEYS = [
    'jurisdiction_name',
    'document_type',
    'promotion_state',
    'trust_tier',
    'content_class',
] as const;

export async function GET(
    request: NextRequest,
    { params }: { params: { runId: string } }
) {
    try {
        const { searchParams } = new URL(request.url);
        const query = new URLSearchParams();

        const limit = searchParams.get('limit');
        const offset = searchParams.get('offset');
        const runIdKey = searchParams.get('run_id_key');

        if (limit) query.set('limit', limit);
        if (offset) query.set('offset', offset);
        if (runIdKey) query.set('run_id_key', runIdKey);

        PASSTHROUGH_FILTER_KEYS.forEach((key) => {
            const value = searchParams.get(key);
            if (value && value.trim()) {
                query.set(key, value.trim());
            }
        });

        const path = `/api/admin/substrate/runs/${encodeURIComponent(params.runId)}/raw-scrapes${query.toString() ? `?${query.toString()}` : ''}`;
        const response = await fetchWithAuth(request, path);
        if (!response.ok) {
            const error = await response.text();
            return NextResponse.json(
                { error: 'Failed to fetch substrate raw rows', details: error },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Substrate raw rows API route error:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
