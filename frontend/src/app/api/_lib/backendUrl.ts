function normalizeBackendUrl(raw: string): string {
  return raw.replace(/\/+$/, '');
}

export function getBackendUrl(): string {
  const raw =
    process.env.RAILWAY_SERVICE_BACKEND_URL ||
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.VITE_API_URL ||
    'http://localhost:8000';
  return normalizeBackendUrl(raw);
}

