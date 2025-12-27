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
  const derivedFromRailwayHost = inferRailwayBackendUrlFromHost(hostHeader);
  if (derivedFromRailwayHost) return normalizeBackendUrl(derivedFromRailwayHost);

  const raw =
    process.env.RAILWAY_SERVICE_BACKEND_URL ||
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.VITE_API_URL ||
    'http://localhost:8000';
  return normalizeBackendUrl(raw);
}
