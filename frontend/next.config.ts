/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        // Tell Next.js to intercept any requests to /api/...
        source: '/api/:path*',
        // And secretly forward them to the Python backend running in the SAME container
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
    ]
  },
}

export default nextConfig;