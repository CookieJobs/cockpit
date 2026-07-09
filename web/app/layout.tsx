import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "拾光 · 你的个人项目驾驶舱",
  description: "不替你干活，替你记住你干过什么、要干什么。",
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
