import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const apiUrl =
      process.env.MITROS_API_INTERNAL_URL ??
      process.env.NEXT_PUBLIC_MITROS_API_URL ??
      "https://mitros.onrender.com";
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
