import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
    try {
        const { searchParams } = new URL(request.url);
        const jurisdiction = searchParams.get('jurisdiction');
        const billId = searchParams.get('bill_id');
        const step = searchParams.get('step');
        const limit = searchParams.get('limit') || '50';

        let url = `${BACKEND_URL}/admin/analyses?limit=${limit}`;
        if (jurisdiction) url += `&jurisdiction=${jurisdiction}`;
        if (billId) url += `&bill_id=${billId}`;
        if (step) url += `&step=${step}`;

        const response = await fetch(url);

        if (!response.ok) {
            const error = await response.text();
            return NextResponse.json(
                { error: 'Failed to fetch analysis history', details: error },
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
