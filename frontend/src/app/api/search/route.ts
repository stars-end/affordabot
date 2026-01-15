import { NextRequest, NextResponse } from 'next/server';

// Search API endpoint that queries the backend for bills
export async function GET(request: NextRequest) {
    const searchParams = request.nextUrl.searchParams;
    const query = searchParams.get('q');

    if (!query || query.trim().length === 0) {
        return NextResponse.json({ results: [], message: 'Query parameter required' }, { status: 400 });
    }

    try {
        const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${backendUrl}/api/bills/search?q=${encodeURIComponent(query)}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            // If backend search doesn't exist yet, return empty results gracefully
            return NextResponse.json({
                results: [],
                message: 'Search service temporarily unavailable'
            });
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Search API error:', error);
        // Return empty results rather than error to provide graceful degradation
        return NextResponse.json({
            results: [],
            message: 'Search service unavailable'
        });
    }
}
