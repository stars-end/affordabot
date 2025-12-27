import { NextRequest, NextResponse } from 'next/server';

import { getBackendUrl } from '../../_lib/backendUrl';

export const dynamic = 'force-dynamic';

export async function DELETE(request: NextRequest, { params }: { params: { id: string } }) {
  const response = await fetch(
    `${getBackendUrl(request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined)}/sources/${params.id}`,
    { method: 'DELETE' }
  );
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' },
  });
}
