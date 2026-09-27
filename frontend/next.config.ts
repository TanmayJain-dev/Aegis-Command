import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL;

const nextConfig: NextConfig = {
  async rewrites() {
    if (!BACKEND_URL || BACKEND_URL.includes("backend:8000")) {
      return [];
    }
    return [
      {
        source: '/api/:path*',
        destination: `${BACKEND_URL}/api/:path*`,
      },
      {
        source: '/ws/:path*',
        destination: `${BACKEND_URL}/ws/:path*`,
      }
    ];
  },
};

export default nextConfig;