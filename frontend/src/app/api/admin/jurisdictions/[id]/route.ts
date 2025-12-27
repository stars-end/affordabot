import { NextRequest, NextResponse } from 'next/server';

import { getBackendUrl } from '../../../_lib/backendUrl';

export async function PUT(request: NextRequest, { params }: { params: { id: string } }) {
    try {
        const body = await request.json();
        const backendUrl = getBackendUrl(
            request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined
        );
        const response = await fetch(`${backendUrl}/admin/jurisdictions/${params.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            throw new Error(`Backend responded with ${response.status}`);
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Error updating jurisdiction:', error);
        return NextResponse.json(
            { error: 'Failed to update jurisdiction' },
            { status: 500 }
        );
    }
}
