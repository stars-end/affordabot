import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

// Define protected routes
// Currently protecting everything under /admin except specific public paths if any
const isProtected = createRouteMatcher([
    '/admin(.*)',
]);

export default clerkMiddleware(async (auth, req) => {
    // TEST BYPASS LOGIC (Layer 3)
    if (process.env.ENABLE_TEST_AUTH_BYPASS === 'true' && req.headers.get('x-test-user') === 'admin') {
        return NextResponse.next();
    }

    if (isProtected(req)) {
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
        '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
        // Always run for API routes
        '/(api|trpc)(.*)',
    ],
};
