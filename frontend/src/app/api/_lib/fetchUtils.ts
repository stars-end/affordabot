import { NextRequest } from 'next/server';
import { getBackendUrl } from './backendUrl';

/**
 * fetchWithAuth wraps the native fetch API to automatically:
 * 1. Resolve the backend URL based on headers/environment.
 * 2. Forward dynamic authentication headers (Cookie, Authorization) from the incoming request.
 * 
 * @param request The incoming NextRequest from the API Route Handler.
 * @param path The backend API path (e.g., '/api/admin/prompts').
 * @param options Standard RequestInit options for fetch.
 * @returns A Promise resolving to a Response object.
 */
export async function fetchWithAuth(
    request: NextRequest,
    path: string,
    options: RequestInit = {}
): Promise<Response> {
    const hostHeader = request.headers.get('x-forwarded-host') ?? request.headers.get('host') ?? undefined;
    const backendUrl = getBackendUrl(hostHeader);

    // Ensure path starts with /
    const sanitizedPath = path.startsWith('/') ? path : `/${path}`;
    const url = `${backendUrl}${sanitizedPath}`;

    // Merge headers, prioritizing forwarded ones
    const headers = new Headers(options.headers);

    // Forward Authentication Headers
    const cookie = request.headers.get('cookie');
    const auth = request.headers.get('authorization');

    if (cookie) headers.set('cookie', cookie);
    if (auth) headers.set('authorization', auth);

    return fetch(url, {
        ...options,
        headers,
    });
}
