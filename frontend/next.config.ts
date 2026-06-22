import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
    ],
  },
  async rewrites() {
    // In local-tunnel mode NEXT_PUBLIC_API_URL is empty, so the browser calls
    // relative /api/* paths which Next.js proxies to the local backend here.
    // This also keeps SSE streaming working (Node.js streams are piped through).
    const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        // Backend serves generated images / scenes / voice under /uploads.
        // Proxy them too so media loads same-origin through the tunnel domain
        // (external users can't reach the operator's localhost directly).
        source: "/uploads/:path*",
        destination: `${backendUrl}/uploads/:path*`,
      },
    ];
  },
};

export default nextConfig;
