import type { NextConfig } from "next";
import path from "path";

// Same-origin proxies to the local services, so the browser never needs CORS and every
// call stays on 127.0.0.1 (no IPv6 localhost fallback, works with Wi-Fi off).
// Order matters: the specific prefixes must come before the kernel catch-all.
const KERNEL = process.env.CHRONOS_KERNEL_HTTP ?? "http://127.0.0.1:8000";
const Z3 = process.env.CHRONOS_Z3_HTTP ?? "http://127.0.0.1:8001";
const AGENT = process.env.CHRONOS_AGENT_HTTP ?? "http://127.0.0.1:8002";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.resolve(__dirname),
  async rewrites() {
    return [
      { source: "/v1/z3/:path*", destination: `${Z3}/v1/z3/:path*` },
      { source: "/v1/agent/:path*", destination: `${AGENT}/v1/agent/:path*` },
      { source: "/v1/:path*", destination: `${KERNEL}/v1/:path*` },
    ];
  },
};

export default nextConfig;
