import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Build ramping untuk Docker: hasilkan server mandiri di .next/standalone
  output: "standalone",
};

export default nextConfig;
