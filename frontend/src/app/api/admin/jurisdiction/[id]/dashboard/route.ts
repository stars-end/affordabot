import { NextRequest, NextResponse } from 'next/server';

import { getBackendUrl } from '../../../../_lib/backendUrl';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest, { params }: { params: { id: string } }) {
  const response = await fetch(
    `${getBackendUrl(request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined)}/admin/jurisdiction/${params.id}/dashboard`
  );
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' },
  });
}
