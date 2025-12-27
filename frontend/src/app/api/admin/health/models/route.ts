import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

import { getBackendUrl } from '../../../_lib/backendUrl';

export async function GET(request: NextRequest) {
    try {
        const backendUrl = getBackendUrl(
            request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined
        );
        const response = await fetch(`${backendUrl}/admin/health/models`);
        if (!response.ok) {
            throw new Error(`Backend responded with ${response.status}`);
        }
        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Error checking model health:', error);
        return NextResponse.json(
            { error: 'Failed to check model health' },
            { status: 500 }
        );
    }
}
