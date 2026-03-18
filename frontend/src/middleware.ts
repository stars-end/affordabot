import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const CLERK_KEY = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? '';
const isCIClerkKey = CLERK_KEY.includes('placeholder');
const isTestBypass = process.env.NEXT_PUBLIC_TEST_AUTH_BYPASS === 'true';
const CLERK_SECRET_KEY = process.env.CLERK_SECRET_KEY || '';

// Admin routes that require auth protection
const isProtectedRoute = (pathname: string) => pathname.startsWith('/admin');

async function verifySignedBypassCookie(cookieHeader: string | null, secret: string): Promise<boolean> {
    if (!cookieHeader) return false;
    const tokenMatch = cookieHeader.match(/x-test-user=v1\.([^;]+)/);
    const token = tokenMatch ? `v1.${tokenMatch[1]}` : null;
    if (!token) return false;
    const [v, payloadB64, sigB64] = token.split('.');
    if (v !== 'v1' || !payloadB64 || !sigB64) return false;
    try {
        const msg = `v1.${payloadB64}`;
        const encoder = new TextEncoder();
        const key = await crypto.subtle.importKey(
            'raw', encoder.encode(secret),
            { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']
        );
        const b64urlToUint8 = (b64url: string) => {
            const padding = '='.repeat((4 - b64url.length % 4) % 4);
            const b64 = (b64url + padding).replace(/-/g, '+').replace(/_/g, '/');
            const bin = atob(b64);
            const arr = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
            return arr;
        };
        const sig = b64urlToUint8(sigB64);
        const isValid = await crypto.subtle.verify('HMAC', key, sig, encoder.encode(msg));
        if (!isValid) return false;
        const padding = '='.repeat((4 - payloadB64.length % 4) % 4);
        const payload = JSON.parse(atob((payloadB64 + padding).replace(/-/g, '+').replace(/_/g, '/')));
        return !payload.exp || Date.now() / 1000 < payload.exp;
    } catch {
        return false;
    }
}

// CI middleware: validates signed bypass cookie for admin routes,
// allows all public routes without Clerk dependency.
function ciMiddleware() {
    return async (req: NextRequest) => {
        // Admin routes require the signed bypass cookie even in CI mode
        if (isProtectedRoute(req.nextUrl.pathname)) {
            const secret = process.env.TEST_AUTH_BYPASS_SECRET;
            if (!secret) {
                return NextResponse.next();
            }
            const cookieHeader = req.headers.get('cookie');
            if (!await verifySignedBypassCookie(cookieHeader, secret)) {
                // Return 401 instead of redirecting (Clerk not available in CI)
                return new NextResponse('Unauthorized: invalid or missing bypass cookie', {
                    status: 401,
                    headers: { 'Content-Type': 'text/plain' },
                });
            }
        }
        return NextResponse.next();
    };
}

// Production middleware: uses Clerk with bypass cookie support
function prodMiddleware() {
    // Dynamic import to avoid Clerk SDK loading in CI mode
    const { clerkMiddleware, createRouteMatcher } = require('@clerk/nextjs/server');
    const isProtected = createRouteMatcher(['/admin(.*)']);

    return clerkMiddleware(async (auth: any, req: any) => {
        if (isProtected(req)) {
            const envName = process.env.RAILWAY_ENVIRONMENT_NAME;
            const isBypassEnvironment = ['dev', 'staging'].includes(envName || '');
            const secret = process.env.TEST_AUTH_BYPASS_SECRET;

            if (isBypassEnvironment && secret) {
                if (await verifySignedBypassCookie(req.headers.get('cookie'), secret)) {
                    return NextResponse.next();
                }
            }

            const { userId } = await auth();
            if (!userId) {
                const forwardedHost = req.headers.get('x-forwarded-host')?.split(',')[0]?.trim();
                const forwardedProto = req.headers.get('x-forwarded-proto')?.split(',')[0]?.trim();
                const publicOrigin =
                    forwardedHost ? `${forwardedProto || 'https'}://${forwardedHost}` : req.nextUrl.origin;
                const returnBackUrl = new URL(`${req.nextUrl.pathname}${req.nextUrl.search}`, publicOrigin).toString();
                const signInUrl = new URL('/sign-in', publicOrigin);
                signInUrl.searchParams.set('redirect_url', returnBackUrl);
                return NextResponse.redirect(signInUrl);
            }
        }
    });
}

// Select middleware based on environment
// Test bypass mode: uses CI middleware without Clerk dependency
// Production: Clerk middleware handles auth with bypass cookie support
const middleware = isTestBypass ? ciMiddleware() : prodMiddleware();
export default middleware;

export const config = {
    matcher: [
        '/((?!_next|api|trpc|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    ],
};
