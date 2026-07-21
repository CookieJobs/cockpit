/** @type {import('next').NextConfig} */
// 历史：dev 模式曾经用 rewrites proxy /api/* → 127.0.0.1:7842，
// 但 Next.js dev 模式 rewrites 默认 30s timeout，LLM 调 5+ tool call
// 会超时报 500（实测 status:500 / Internal Server Error / ECONNRESET）。
// 修法：删 rewrites，前端通过 NEXT_PUBLIC_API_BASE 直连 7842（CORS 已开）。
// 生产用反向代理（nginx/Caddy）时反代加 proxy_read_timeout 600s 即可。
//
// 2026-07-21: 加 output: 'export' 启用静态导出 (Docker 部署用)。
// 静态导出后产物在 web/out/, 由 FastAPI 静态服务接管 (app/main.py),
// 单端口同源, 前端 fetch 用相对路径 /api/* 不会触发 CORS。
// images.unoptimized: true 是 output: 'export' 的硬性要求 (next/image 优化
// 服务需要 Node server, 静态导出不支持)。
const nextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
  // 静态导出时 trailingSlash 默认 false 即可, Next 会处理 SPA 路由
  trailingSlash: false,
};

export default nextConfig;
