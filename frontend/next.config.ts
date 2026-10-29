import type { NextConfig } from "next";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8010";

const nextConfig: NextConfig = {
  devIndicators: false,
  // The API is proxied so auth cookies stay same-origin (no CORS, no third-party cookie issues).
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${BACKEND}/api/v1/:path*` }];
  },
  turbopack: {
    root: __dirname,
    rules: { "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" } },
  },
};

export default nextConfig;
