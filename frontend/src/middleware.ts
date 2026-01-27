import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

// Define protected routes
// Currently protecting everything under /admin except specific public paths if any
const isProtected = createRouteMatcher([
    '/admin(.*)',
]);

export default clerkMiddleware(async (auth, req) => {
    if (isProtected(req)) {

        // Railway dev env: allow cookie-gated bypass for verification runners (no Clerk creds).
        // Keeps prod locked down (no bypass on custom domains).
        const envName = process.env.RAILWAY_ENVIRONMENT_NAME;
        const isBypassEnvironment = ['dev', 'staging'].includes(envName || '');
        const token = req.cookies.get('x-test-user')?.value;
        const secret = process.env.TEST_AUTH_BYPASS_SECRET;

        if (isBypassEnvironment && token && secret) {
            // Validate signed token with Web Crypto API (supported in Next.js middleware)
            const [v, payloadB64, sigB64] = token.split('.');
            if (v === 'v1' && payloadB64 && sigB64) {
                try {
                    const msg = `v1.${payloadB64}`;
                    const encoder = new TextEncoder();
                    const key = await crypto.subtle.importKey(
                        'raw',
                        encoder.encode(secret),
                        { name: 'HMAC', hash: 'SHA-256' },
                        false,
                        ['verify']
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

                    if (isValid) {
                        const padding = '='.repeat((4 - payloadB64.length % 4) % 4);
                        const payload = JSON.parse(atob((payloadB64 + padding).replace(/-/g, '+').replace(/_/g, '/')));
                        if (!payload.exp || Date.now() / 1000 < payload.exp) {
                            return NextResponse.next();
                        }
                    }
                } catch (e) {
                    // Silently fail to normal Clerk auth on verification error
                }
            }
        }

        const { userId } = await auth();
        if (!userId) {
            // Railway/other reverse proxies can present an internal host (e.g. localhost:PORT) to Next.js.
            // Prefer forwarded headers so Clerk's `redirect_url` points at the public domain.
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

export const config = {
    matcher: [
        // Skip Next.js internals and all static files, unless found in search params
        '/((?!_next|api|trpc|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    ],
};
