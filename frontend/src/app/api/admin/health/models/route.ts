import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth } from '../../../_lib/fetchUtils';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
    try {
        const response = await fetchWithAuth(request, '/api/admin/health/models');
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
