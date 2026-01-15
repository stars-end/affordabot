import { NextRequest, NextResponse } from 'next/server';

// Mock pipeline detail for development
const MOCK_DETAIL = {
    id: 'run-001',
    bill_id: 'SJ-2024-041',
    jurisdiction: 'San Jose',
    status: 'completed',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    completed_at: new Date(Date.now() - 3000000).toISOString(),
    steps: [
        {
            step_name: 'Research',
            model: 'gpt-4',
            input: 'Research economic impact of San Jose bill 2024-041 regarding housing development fees...',
            output: 'Found relevant information about housing development fees and their economic impact...',
            created_at: new Date(Date.now() - 3500000).toISOString()
        },
        {
            step_name: 'Generate Analysis',
            model: 'claude-3',
            input: 'Based on the research data, generate a structured economic impact analysis...',
            output: '{"summary": "This bill proposes changes to housing development fees...", "impact_score": 0.75}',
            created_at: new Date(Date.now() - 3300000).toISOString()
        },
        {
            step_name: 'Review',
            model: 'gpt-4',
            input: 'Review the following analysis for accuracy and completeness...',
            output: '{"approved": true, "suggestions": ["Consider adding more data on regional comparisons"]}',
            created_at: new Date(Date.now() - 3100000).toISOString()
        }
    ],
    analysis: {
        summary: 'This bill proposes changes to housing development fees that may impact affordability.',
        impact_score: 0.75,
        citations: [
            { url: 'https://sanjose.gov/bills/2024-041', title: 'Official Bill Text' },
            { url: 'https://example.com/housing-study', title: 'Housing Impact Study 2024' }
        ]
    }
};

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    const { id } = await params;

    try {
        const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${backendUrl}/api/admin/pipeline-runs/${id}`, {
            headers: { 'Content-Type': 'application/json' },
        });

        if (response.ok) {
            const data = await response.json();
            return NextResponse.json(data);
        }

        // Fallback to mock data
        return NextResponse.json({ ...MOCK_DETAIL, id });
    } catch (error) {
        console.error('Pipeline detail API error:', error);
        return NextResponse.json({ ...MOCK_DETAIL, id });
    }
}
