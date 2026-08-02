import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ToastProvider } from "@/components/Toast";

// icon 由 app/icon.tsx + app/apple-icon.tsx 动态生成 (Satori + Twemoji 渲染 🚀)
// Next.js 15 会自动注入 <link rel="icon"> 和 <link rel="apple-touch-icon">
export const metadata: Metadata = {
  title: "Cockpit · 你的个人项目驾驶舱",
  description: "不替你干活，替你记住你干过什么、要干什么。",
  applicationName: "Cockpit",
};

// 2026-08-01 改: 不再硬编码 themeColor/dark, 改成依赖 CSS color-scheme +
//   早期同步脚本切 html class。viewport 只留 device-width 必填项。
//   原因: Next.js viewport export 是静态的, 不能在切主题时改 meta;
//   但浏览器看 color-scheme 决定原生组件 (scrollbar / 表单) 颜色已够。
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

// 2026-08-01 立: 早期同步脚本 — 必须在 React 渲染前执行, 读 localStorage
//   切 html class 防 FOUC (Flash of unstyled content)。放在 <head> 顶部,
//   同步执行 (无 defer/async), 不依赖 React hydration。
//
//   行为: 读 localStorage['cockpit_theme'], 合法值 'light' / 'dark' 才应用;
//   非法或缺失默认 dark (保留产品原观感, 渐进增强, 不打扰老用户)。
const themeInitScript = `
(function() {
  try {
    var stored = localStorage.getItem('cockpit_theme');
    var theme = stored === 'light' || stored === 'dark' ? stored : 'dark';
    var root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }
    root.setAttribute('data-theme', theme);
  } catch (e) {
    // localStorage 不可用 (隐私模式 / SSR 异常), 静默走默认 dark
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
    // 2026-08-01 改: 去掉 <html> 上预设的 dark 类, 让早期同步脚本决定。
    //   suppressHydrationWarning 防止 React 警告: server 渲染时无 class,
    //   client 早期脚本立即加 class, 这之间的"不一致"是设计如此。
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="bg-bg text-fg">
        {/* ToastProvider (2026-07-28 立): 全局轻量 toast, 完成任务庆祝用 */}
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
