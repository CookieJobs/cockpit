import { ImageResponse } from "next/og";

// 32x32 现代浏览器主 favicon
// Satori 内部用 Twemoji 渲染 emoji, 跨平台一致 (Mac/Win/Linux 都一样)
// 不用系统 emoji 字体, 避免不同 OS 渲染差异
export const size = { width: 32, height: 32 };
export const contentType = "image/png";

// 静态导出 (output: "export") 下, 动态路由需要显式声明 force-static
export const dynamic = "force-static";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          fontSize: 26,
          background: "#0a0a0a",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 6,
        }}
      >
        🚀
      </div>
    ),
    { ...size }
  );
}
