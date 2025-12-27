import { NextRequest, NextResponse } from 'next/server';

import { getBackendUrl } from '../../_lib/backendUrl';

export async function GET(request: NextRequest) {
    try {
        const backendUrl = getBackendUrl(
            request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined
        );
        const response = await fetch(`${backendUrl}/admin/models`);

        if (!response.ok) {
            const error = await response.text();
            return NextResponse.json(
                { error: 'Failed to fetch models', details: error },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('API route error:', error);
        return NextResponse.json(
            {
                error: 'Internal server error',
                details: error instanceof Error ? error.message : String(error),
                backend_url: getBackendUrl()
            },
            { status: 500 }
        );
    }
}

export async function POST(request: NextRequest) {
    try {
        const BACKEND_URL = getBackendUrl(
            request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined
        );
        const body = await request.json();

        const response = await fetch(`${BACKEND_URL}/admin/models`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const error = await response.text();
            return NextResponse.json(
                { error: 'Failed to update models', details: error },
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
