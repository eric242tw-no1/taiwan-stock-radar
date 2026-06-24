import type { NextConfig } from "next";
import withPWAInit from "@ducanh2912/next-pwa";

const withPWA = withPWAInit({
  dest: "public",
  cacheOnFrontEndNav: true,
  aggressiveFrontEndNavCaching: true,
  reloadOnOnline: true,
  disable: process.env.NODE_ENV === "development",
  workboxOptions: {
    disableDevLogs: true,
  },
});

const nextConfig: NextConfig = {
  output: "standalone",
  // 預覽用第二個 dev server 時設 NEXT_DIST_DIR=.next-preview，讓 lock 檔
  // （distDir/lock）與主 server 分離，繞過 Next 16 同目錄單例鎖
  distDir: process.env.NEXT_DIST_DIR || ".next",
  turbopack: {},
  allowedDevOrigins: ["127.0.0.1", "localhost", "exact-pupil-snowfield.ngrok-free.dev"],
  experimental: {
    proxyTimeout: 120000, // 120s — debate API can take ~54s
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default withPWA(nextConfig);
