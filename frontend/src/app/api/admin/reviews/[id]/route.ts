import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

// MVP stub: accept updates but do not persist.
export async function PATCH(_request: NextRequest, _ctx: { params: { id: string } }) {
  return NextResponse.json({ ok: true });
}

