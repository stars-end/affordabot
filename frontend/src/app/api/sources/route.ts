import { NextRequest, NextResponse } from 'next/server';

import { getBackendUrl } from '../_lib/backendUrl';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const jurisdiction_id = searchParams.get('jurisdiction_id');
  const qs = jurisdiction_id ? `?jurisdiction_id=${encodeURIComponent(jurisdiction_id)}` : '';

  const response = await fetch(`${getBackendUrl(request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined)}/sources/${qs}`);
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' },
  });
}

export async function POST(request: NextRequest) {
  const payload = await request.text();
  const response = await fetch(`${getBackendUrl(request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined)}/sources/`, {
    method: 'POST',
    headers: { 'content-type': request.headers.get('content-type') ?? 'application/json' },
    body: payload,
  });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' },
  });
}
