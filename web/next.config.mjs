/** @type {import('next').NextConfig} */
// 历史：dev 模式曾经用 rewrites proxy /api/* → 127.0.0.1:7842，
// 但 Next.js dev 模式 rewrites 默认 30s timeout，LLM 调 5+ tool call
// 会超时报 500（实测 status:500 / Internal Server Error / ECONNRESET）。
// 修法：删 rewrites，前端通过 NEXT_PUBLIC_API_BASE 直连 7842（CORS 已开）。
// 生产用反向代理（nginx/Caddy）时反代加 proxy_read_timeout 600s 即可。
const nextConfig = {};

export default nextConfig;
