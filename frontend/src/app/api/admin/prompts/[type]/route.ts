import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || process.env.VITE_API_URL || process.env.RAILWAY_SERVICE_BACKEND_URL || 'http://localhost:8000';

export async function GET(
    request: NextRequest,
    { params }: { params: { type: string } }
) {
    try {
        const { type } = params;

        const response = await fetch(`${BACKEND_URL}/admin/prompts/${type}`);

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
