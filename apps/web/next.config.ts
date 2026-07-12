import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // In prod the dashboard is same-origin with the API via this rewrite, so the
  // session cookie is first-party (see ARCHITECTURE §4). Locally the SPA talks
  // to :8000 directly with credentials:'include' and CORS handles it.
  async rewrites() {
    const api = process.env.API_INTERNAL_URL;
    if (!api) return [];
    return [
      { source: "/auth/:path*", destination: `${api}/auth/:path*` },
      { source: "/api/:path*", destination: `${api}/api/:path*` },
    ];
  },
};

export default nextConfig;
