import { NextRequest, NextResponse } from 'next/server';
import { fetchWithAuth } from '../../../../_lib/fetchUtils';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest, { params }: { params: { id: string } }) {
  const response = await fetchWithAuth(request, `/api/admin/jurisdiction/${params.id}/dashboard`);
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' },
  });
}
