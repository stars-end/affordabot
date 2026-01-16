/** @type {import('next').NextConfig} */
const nextConfig = {
    async rewrites() {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        return [
            {
                source: '/api/:path*',
                destination: `${backendUrl}/:path*`,
            },
        ];
    },
};

export default nextConfig;
