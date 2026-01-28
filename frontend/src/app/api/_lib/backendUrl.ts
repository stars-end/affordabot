function normalizeBackendUrl(raw: string): string {
  return raw.replace(/\/+$/, '');
}

function inferRailwayBackendUrlFromHost(hostHeader?: string): string | undefined {
  if (!hostHeader) return undefined;
  const host = hostHeader.split(',')[0].trim().replace(/:\d+$/, '');
  if (!host.endsWith('.up.railway.app')) return undefined;
  if (host.startsWith('backend-')) return `https://${host}`;
  if (host.startsWith('frontend-')) return `https://backend-${host.slice('frontend-'.length)}`;
  return undefined;
}

export function getBackendUrl(hostHeader?: string): string {
  // 1. Prefer explicit environment variables
  const explicitUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    process.env.RAILWAY_SERVICE_BACKEND_URL ||
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.VITE_API_URL;

  if (explicitUrl) return normalizeBackendUrl(explicitUrl);

  // 2. Fallback to inference (flaky if service hashes differ)
  const derivedFromRailwayHost = inferRailwayBackendUrlFromHost(hostHeader);
  if (derivedFromRailwayHost) return normalizeBackendUrl(derivedFromRailwayHost);

  // 3. Fallback to localhost
  return 'http://localhost:8000';
}
