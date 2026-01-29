import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth } from '../../_lib/fetchUtils';

export async function GET(request: NextRequest) {
    try {
        const response = await fetchWithAuth(request, '/api/admin/jurisdictions');
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
