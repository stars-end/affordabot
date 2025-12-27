import { NextRequest, NextResponse } from 'next/server';

import { getBackendUrl } from '../../../_lib/backendUrl';

export async function GET(
    request: NextRequest,
    { params }: { params: { type: string } }
) {
    try {
        const { type } = params;

        const backendUrl = getBackendUrl(
            request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined
        );
        const response = await fetch(`${backendUrl}/admin/prompts/${type}`);

        if (!response.ok) {
            const error = await response.text();
            return NextResponse.json(
                { error: `Failed to fetch ${type} prompt`, details: error },
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
