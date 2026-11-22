const BACKEND_URL =
  process.env.BACKEND_URL ||
  `http://127.0.0.1:${process.env.BACKEND_PORT || "8000"}`;

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    unoptimized: true,
    remotePatterns: [
      { protocol: "https", hostname: "images.unsplash.com" },
      { protocol: "https", hostname: "d3fphkxyf5o5bm.cloudfront.net" },
      { protocol: "https", hostname: "images.mindtrip.ai" },
      { protocol: "https", hostname: "mindtrip.ai" },
      { protocol: "https", hostname: "**.googleusercontent.com" },
      { protocol: "https", hostname: "**.gstatic.com" },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
