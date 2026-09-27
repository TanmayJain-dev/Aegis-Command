import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:8000';

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${BACKEND_URL}/api/:path*`,
      },
      {
        // 🚀 THE FIX: Proxy WebSocket connections through Next.js to Python
        source: '/ws/:path*',
        destination: `${BACKEND_URL}/ws/:path*`,
      }
    ]
  },
};

export default nextConfig;