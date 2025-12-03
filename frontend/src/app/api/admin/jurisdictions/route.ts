import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET() {
    try {
        const response = await fetch(`${BACKEND_URL}/admin/jurisdictions`);
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
