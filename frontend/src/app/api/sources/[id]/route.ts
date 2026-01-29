import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth } from '../../_lib/fetchUtils';

export const dynamic = 'force-dynamic';

export async function DELETE(request: NextRequest, { params }: { params: { id: string } }) {
  const response = await fetchWithAuth(request, `/sources/${params.id}`, { method: 'DELETE' });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' },
  });
}
