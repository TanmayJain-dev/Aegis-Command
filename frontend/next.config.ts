import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        // 🚀 THE FIX: Tell Docker to route to the 'backend' container
        destination: 'http://backend:8000/api/:path*',
      },
    ]
  },
};

export default nextConfig;