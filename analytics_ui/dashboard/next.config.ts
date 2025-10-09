import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',
  trailingSlash: true,
  distDir: 'out',
  images: {
    unoptimized: true,
  },
  turbopack: {
    root: new URL(".", import.meta.url).pathname,
  },
};

export default nextConfig;
