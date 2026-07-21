import type { Metadata, Viewport } from "next";
import "./globals.css";

// icon 由 app/icon.tsx + app/apple-icon.tsx 动态生成 (Satori + Twemoji 渲染 🚀)
// Next.js 15 会自动注入 <link rel="icon"> 和 <link rel="apple-touch-icon">
export const metadata: Metadata = {
  title: "Cockpit · 你的个人项目驾驶舱",
  description: "不替你干活，替你记住你干过什么、要干什么。",
  applicationName: "Cockpit",
};

// themeColor / colorScheme 在 Next.js 15+ 必须放 viewport export
export const viewport: Viewport = {
  themeColor: "#0a0a0a",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className="dark">
      <body className="bg-bg text-fg">{children}</body>
    </html>
  );
}
