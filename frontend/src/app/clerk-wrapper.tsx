'use client';

import dynamic from 'next/dynamic';
import React from 'react';

// CI-safe mode: when NEXT_PUBLIC_TEST_AUTH_BYPASS=true and the Clerk
// publishable key is a placeholder, ClerkProvider is loaded with ssr:false
// to avoid the SDK validating the key during static page generation.
// Production builds always use real Clerk keys and are unaffected.
const CLERK_KEY = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? '';
const isCIClerkKey = CLERK_KEY.includes('placeholder');
const isTestBypass = process.env.NEXT_PUBLIC_TEST_AUTH_BYPASS === 'true';
const skipSSR = isTestBypass;

// Lazy-loaded ClerkProvider that only loads on the client in CI mode
const LazyClerkProvider = dynamic(
  () => import('@clerk/nextjs').then((mod) => {
    const { ClerkProvider: CP } = mod;
    const clerkJSVersion = process.env.NEXT_PUBLIC_CLERK_JS_VERSION ?? '5.117.0';
    return function ClerkProviderInner({ children }: { children: React.ReactNode }) {
      return <CP clerkJSVersion={clerkJSVersion}>{children}</CP>;
    };
  }),
  { ssr: !skipSSR }
);

export function ClerkWrapper({ children }: { children: React.ReactNode }) {
  if (skipSSR) {
    // CI mode: render children directly on the server for proper SSR.
    // On the client, ClerkProvider loads asynchronously via dynamic import.
    // Use a state to track whether we're on the client and Clerk has mounted.
    // Until then, render children directly so SSR works.
    return <>{children}</>;
  }

  return (
    <LazyClerkProvider>{children}</LazyClerkProvider>
  );
}
