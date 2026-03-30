/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const backend = process.env.BACKEND_ORIGIN || 'http://localhost:8000';
    return [{ source: '/api/backend/:path*', destination: `${backend}/:path*` }];
  },
};
module.exports = nextConfig;