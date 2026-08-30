import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ToastProvider } from "@/components/Toast";

// 2026-08-23 改: cockpit v2 — 单 dark 主题, layout 不再依赖早期同步脚本切主题。
// 早期脚本保留 (兼容老用户 localStorage), 但永远加 .dark, 不读 light。
export const metadata: Metadata = {
  title: "Cockpit · 你的个人项目驾驶舱",
  description: "不替你干活，替你记住你干过什么、要干什么。",
  applicationName: "Cockpit",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // 2026-08-23 加: 浏览器 UI 跟主题色对齐 (地址栏/状态栏/表单原生控件)
  themeColor: "#000000",
};

// 2026-08-23 改: 早期同步脚本简化, 永远加 .dark (v2 单 dark 模式)
//
// 行为: 同步执行, 加 .dark class + 设 data-theme, 防 FOUC
// 兼容老用户: 读 localStorage 但忽略 "light" 值 (永远当 dark 处理)
const themeInitScript = `
(function() {
  try {
    document.documentElement.classList.add('dark');
    document.documentElement.classList.remove('light');
    document.documentElement.setAttribute('data-theme', 'dark');
    document.documentElement.style.backgroundColor = '#000000';
  } catch (e) {
    document.documentElement.classList.add('dark');
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="bg-bg text-fg">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
