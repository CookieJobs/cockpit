"use client";

import Link from "next/link";

export function DataState({
  loading,
  error,
  onRetry,
}: {
  loading: boolean;
  error?: unknown;
  onRetry?: () => void;
}) {
  if (loading) {
    return <div className="min-h-screen bg-bg p-6 text-sm text-fg-muted">正在加载你的本地数据…</div>;
  }
  if (error) {
    return (
      <div className="min-h-screen bg-bg p-6 text-sm text-fg-secondary">
        <p>暂时无法读取本地数据；数据没有被当作空结果处理。</p>
        <div className="mt-3 flex gap-3">
          {onRetry && <button onClick={onRetry} className="text-accent">重试</button>}
          <Link href="/settings" className="text-accent">查看设置与数据位置</Link>
        </div>
      </div>
    );
  }
  return null;
}
