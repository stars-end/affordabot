import { NextRequest, NextResponse } from 'next/server';

import { getBackendUrl } from '../../../_lib/backendUrl';

export async function GET(
    request: NextRequest,
    { params }: { params: { taskId: string } }
) {
    const taskId = params.taskId;

    try {
        const response = await fetch(`${getBackendUrl()}/admin/tasks/${taskId}`);

        if (!response.ok) {
            // Pass through the error from backend if possible, or generic
            const error = await response.text();
            return NextResponse.json(
                { error: 'Failed to fetch task status', details: error },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error(`API route error fetching task ${taskId}:`, error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
