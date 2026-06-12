// pi-fleet overlay of cc_points_dashboard/next.config.mjs — identical to the owner's copy
// plus output:"standalone" so the runtime image is ~200MB instead of ~1GB (Pi has ~6GB free).
// scripts/sync-apps.sh copies this over the rsynced source on the Pi; the Mac copy is untouched.
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
    ],
  },
};

export default nextConfig;
