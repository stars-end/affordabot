import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth } from '../../_lib/fetchUtils';

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();

        const response = await fetchWithAuth(request, '/api/admin/scrape', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const error = await response.text();
            return NextResponse.json(
                { error: 'Failed to trigger scrape', details: error },
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
                details: error instanceof Error ? error.message : String(error)
            },
            { status: 500 }
        );
    }
}
