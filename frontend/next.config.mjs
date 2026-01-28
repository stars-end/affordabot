/** @type {import('next').NextConfig} */
const nextConfig = {
    async rewrites() {
        // DEBUG: Log backend URL to debug "Application not found" errors
        const envBackendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
        // Fallback to explicit Railway backend if env var is missing (prevents localhost errors in prod)
        const backendUrl = envBackendUrl || 'https://backend-dev-3d99.up.railway.app';

        console.log('--------------------------------------------------');
        console.log('🚀 Next.js Proxy Config Debug');
        console.log('ENV NEXT_PUBLIC_BACKEND_URL:', envBackendUrl);
        console.log('Resolved backendUrl:', backendUrl);
        console.log('--------------------------------------------------');

        return [
            {
                source: '/api/:path*',
                destination: `${backendUrl}/api/:path*`,
            },
        ];
    },
};

export default nextConfig;
