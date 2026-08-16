import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://backend:8000/api/:path*',
      },
      {
        // 🚀 THE FIX: Proxy WebSocket connections through Next.js to Python
        source: '/ws/:path*',
        destination: 'http://backend:8000/ws/:path*',
      }
    ]
  },
};

export default nextConfig;