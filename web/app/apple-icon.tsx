import { ImageResponse } from "next/og";

// 180x180 iOS 触屏书签 / PWA 主屏
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

// 静态导出 (output: "export") 下, 动态路由需要显式声明 force-static
export const dynamic = "force-static";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          fontSize: 140,
          background: "#0a0a0a",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 38, // iOS 180x180 标准圆角
        }}
      >
        🚀
      </div>
    ),
    { ...size }
  );
}
