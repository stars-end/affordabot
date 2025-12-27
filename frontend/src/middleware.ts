import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

// Define protected routes
// Currently protecting everything under /admin except specific public paths if any
const isProtected = createRouteMatcher([
    '/admin(.*)',
]);

export default clerkMiddleware(async (auth, req) => {
    if (isProtected(req)) {
        const forwardedHostForBypass = req.headers.get('x-forwarded-host')?.split(',')[0]?.trim();
        const hostForBypass = (forwardedHostForBypass || req.headers.get('host') || '').replace(/:\d+$/, '');

        // Railway PR preview environments are non-production and are primarily for CI verification.
        // Avoid coupling verification runs to Clerk credentials by allowing /admin to load in PR previews.
        const isRailwayPrPreview =
            hostForBypass.includes('-pr-') && hostForBypass.endsWith('.up.railway.app');
        if (isRailwayPrPreview) {
            return NextResponse.next();
        }

        // Railway dev env: allow cookie-gated bypass for verification runners (no Clerk creds).
        // Keeps prod locked down (no bypass on custom domains).
        const isRailwayDev =
            hostForBypass.includes('frontend-dev-') && hostForBypass.endsWith('.up.railway.app');
        if (isRailwayDev && req.cookies.get('x-test-user')?.value === 'admin') {
            return NextResponse.next();
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
