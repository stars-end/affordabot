import { NextResponse } from 'next/server';

// Mock alerts for development
const MOCK_ALERTS = [
    {
        id: 'alert-001',
        type: 'warning',
        title: 'Stale Scraper: San Jose',
        message: 'San Jose scraper has not run successfully in 48 hours',
        created_at: new Date(Date.now() - 172800000).toISOString(),
        resolved: false
    },
    {
        id: 'alert-002',
        type: 'info',
        title: 'New Bills Available',
        message: '5 new bills discovered in California legislature',
        created_at: new Date(Date.now() - 86400000).toISOString(),
        resolved: false
    }
];

export async function GET() {
    try {
        const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${backendUrl}/api/admin/alerts`, {
            headers: { 'Content-Type': 'application/json' },
        });

        if (response.ok) {
            const data = await response.json();
            return NextResponse.json(data);
        }

        return NextResponse.json({ alerts: MOCK_ALERTS });
    } catch (error) {
        console.error('Alerts API error:', error);
        return NextResponse.json({ alerts: MOCK_ALERTS });
    }
}
