import { NextRequest, NextResponse } from 'next/server';

import { getBackendUrl } from '../../_lib/backendUrl';

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  const payload = await request.text();
  const response = await fetch(
    `${getBackendUrl(request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined)}/discovery/run`,
    {
    method: 'POST',
    headers: { 'content-type': request.headers.get('content-type') ?? 'application/json' },
    body: payload,
    }
  );
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' },
  });
}
