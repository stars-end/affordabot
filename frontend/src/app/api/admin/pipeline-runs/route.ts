import { NextResponse } from 'next/server';

// Mock pipeline runs for development
const MOCK_RUNS = [
    {
        id: 'run-001',
        bill_id: 'SJ-2024-041',
        jurisdiction: 'San Jose',
        status: 'completed',
        created_at: new Date(Date.now() - 3600000).toISOString(),
        completed_at: new Date(Date.now() - 3000000).toISOString(),
        models: { research: 'gpt-4', generate: 'claude-3', review: 'gpt-4' }
    },
    {
        id: 'run-002',
        bill_id: 'CA-AB-1234',
        jurisdiction: 'California',
        status: 'failed',
        created_at: new Date(Date.now() - 7200000).toISOString(),
        models: { research: 'gpt-4', generate: 'claude-3' }
    },
    {
        id: 'run-003',
        bill_id: 'SC-2024-015',
        jurisdiction: 'Santa Clara County',
        status: 'running',
        created_at: new Date(Date.now() - 600000).toISOString(),
        models: { research: 'gpt-4' }
    }
];

export async function GET() {
    try {
        const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${backendUrl}/api/admin/pipeline-runs`, {
            headers: { 'Content-Type': 'application/json' },
        });

        if (response.ok) {
            const data = await response.json();
            return NextResponse.json(data);
        }

        // Fallback to mock data if backend unavailable
        return NextResponse.json({ runs: MOCK_RUNS });
    } catch (error) {
        console.error('Pipeline runs API error:', error);
        return NextResponse.json({ runs: MOCK_RUNS });
    }
}
