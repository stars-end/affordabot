import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

// MVP stub: backend review endpoints are not yet implemented.
export async function GET(_request: NextRequest) {
  return NextResponse.json([]);
}

