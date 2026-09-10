import type { NextConfig } from "next";

const staticExport = process.env.AERA_STATIC === "1";
const backend = process.env.AERA_BACKEND_URL || "http://127.0.0.1:8001";

const nextConfig: NextConfig = staticExport
  ? {
      output: "export",
      trailingSlash: true,
      images: { unoptimized: true },
    }
  : {
      async rewrites() {
        return [
          { source: "/api/:path*", destination: `${backend}/api/:path*` },
          { source: "/health", destination: `${backend}/health` },
        ];
      },
    };

export default nextConfig;
