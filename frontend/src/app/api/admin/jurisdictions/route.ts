import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

import { getBackendUrl } from '../../_lib/backendUrl';

export async function GET(request: NextRequest) {
    try {
        const backendUrl = getBackendUrl(
            request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined
        );
        const response = await fetch(`${backendUrl}/admin/jurisdictions`);
        if (!response.ok) {
            throw new Error(`Backend responded with ${response.status}`);
        }
        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Error fetching jurisdictions:', error);
        return NextResponse.json(
            { error: 'Failed to fetch jurisdictions' },
            { status: 500 }
        );
    }
}
