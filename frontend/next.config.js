/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/analyze',
        destination: 'http://localhost:8000/analyze',
      },
      {
        source: '/api/jobs/:path*',
        destination: 'http://localhost:8000/jobs/:path*',
      },
      {
        source: '/api/download/:path*',
        destination: 'http://localhost:8000/download/:path*',
      },
      {
        source: '/api/health',
        destination: 'http://localhost:8000/health',
      },
    ];
  },
};

module.exports = nextConfig;