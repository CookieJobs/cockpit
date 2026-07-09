"use client";

import Link from "next/link";
import { ArrowLeft, CheckCircle2, AlertCircle } from "lucide-react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useState } from "react";

export default function SettingsPage() {
  const { data: health } = useSWR("/api/health", () => api.health());
  return (
    <div className="min-h-screen bg-bg text-fg">
      <div className="max-w-2xl mx-auto p-6">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/" className="text-fg-muted hover:text-fg transition">
            <ArrowLeft size={18} />
          </Link>
          <h1 className="text-2xl font-semibold">设置</h1>
        </div>

        {/* 后端状态 */}
        <section className="rounded-lg border border-border bg-bg-secondary p-4 mb-4">
          <h2 className="text-sm font-semibold text-fg-secondary uppercase tracking-wider mb-3">
            后端连接
          </h2>
          {health ? (
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 size={14} className="text-success" />
              <span>已连接 · {health.name} v{health.version}</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-warning">
              <AlertCircle size={14} />
              <span>连接中...</span>
            </div>
          )}
        </section>

        {/* LLM 配置（占位） */}
        <section className="rounded-lg border border-border bg-bg-secondary p-4 mb-4">
          <h2 className="text-sm font-semibold text-fg-secondary uppercase tracking-wider mb-3">
            LLM 配置
          </h2>
          <p className="text-sm text-fg-muted mb-3">
            当前版本：命令解析（无 LLM）
          </p>
          <div className="text-xs text-fg-muted space-y-1">
            <p>3c 阶段会接入 Anthropic Claude + Ollama</p>
            <p>支持：用户自带 API Key / 本地 Ollama 降级</p>
          </div>
        </section>

        {/* 数据 */}
        <section className="rounded-lg border border-border bg-bg-secondary p-4">
          <h2 className="text-sm font-semibold text-fg-secondary uppercase tracking-wider mb-3">
            数据
          </h2>
          <div className="text-xs text-fg-muted space-y-1">
            <p>数据目录：~/.shiguang/</p>
            <p>数据库：shiguang.db (SQLite)</p>
            <p>备份：v1.1 接入 iCloud Drive 同步</p>
          </div>
        </section>
      </div>
    </div>
  );
}
