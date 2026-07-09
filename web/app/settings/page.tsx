"use client";

import Link from "next/link";
import { ArrowLeft, CheckCircle2, AlertCircle, RefreshCw, Wrench } from "lucide-react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useState } from "react";

export default function SettingsPage() {
  const { data: health } = useSWR("/api/health", () => api.health());
  const { data: llmStatus, mutate: refreshLLM } = useSWR(
    "/api/llm/status",
    () => api.llmStatus(),
    { refreshInterval: 0 }
  );
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await api.llmTest();
      setTestResult({ ok: r.ok, msg: `${r.backend} (${r.model}) 连接成功` });
    } catch (e) {
      setTestResult({ ok: false, msg: e instanceof Error ? e.message : String(e) });
    } finally {
      setTesting(false);
    }
  };

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

        {/* LLM 配置 */}
        <section className="rounded-lg border border-border bg-bg-secondary p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-fg-secondary uppercase tracking-wider">
              LLM 配置
            </h2>
            <button
              onClick={() => refreshLLM()}
              className="text-fg-muted hover:text-fg transition"
              title="刷新"
            >
              <RefreshCw size={14} />
            </button>
          </div>

          {llmStatus?.available ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle2 size={14} className="text-success" />
                <span>已连接 · {llmStatus.backend?.replace("Client", "")} ({llmStatus.model})</span>
              </div>
              <div className="text-xs text-fg-muted">
                配置后端：<code className="text-fg">{llmStatus.configured_backend}</code>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-warning">
                <AlertCircle size={14} />
                <span>未连接 LLM · 当前使用关键词模式</span>
              </div>
            </div>
          )}

          {/* 测试连接 */}
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={runTest}
              disabled={testing}
              className="text-xs px-3 py-1.5 bg-bg border border-border rounded text-fg hover:border-accent disabled:opacity-50 transition flex items-center gap-1"
            >
              <Wrench size={12} />
              {testing ? "测试中..." : "测试连接"}
            </button>
            {testResult && (
              <span className={`text-xs ${testResult.ok ? "text-success" : "text-danger"}`}>
                {testResult.ok ? "✓" : "✗"} {testResult.msg}
              </span>
            )}
          </div>

          {/* 配置说明 */}
          <details className="mt-4 text-xs">
            <summary className="text-fg-muted cursor-pointer hover:text-fg">
              如何配置 LLM？
            </summary>
            <div className="mt-2 space-y-2 text-fg-secondary leading-relaxed">
              <p><strong>方案 1：Anthropic Claude（推荐，tool calling 强）</strong></p>
              <p>编辑 <code className="text-fg">.env</code>，填入：</p>
              <pre className="bg-bg p-2 rounded text-[11px] overflow-x-auto">
{`SHIGUANG_LLM_BACKEND=anthropic
SHIGUANG_LLM_MODEL=claude-sonnet-4-5
ANTHROPIC_API_KEY=sk-ant-xxx`}
              </pre>
              <p className="mt-2"><strong>方案 2：Ollama 本地（免费，tool calling 弱）</strong></p>
              <pre className="bg-bg p-2 rounded text-[11px] overflow-x-auto">
{`SHIGUANG_LLM_BACKEND=ollama
OLLAMA_MODEL=qwen2.5:3b
# 需要本地运行 ollama serve 并 ollama pull qwen2.5:3b`}
              </pre>
              <p className="mt-2"><strong>方案 3：OpenAI 兼容（DeepSeek / Moonshot / 自定义）</strong></p>
              <pre className="bg-bg p-2 rounded text-[11px] overflow-x-auto">
{`SHIGUANG_LLM_BACKEND=openai
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat`}
              </pre>
              <p className="mt-2 text-fg-muted">
                修改 .env 后需要重启后端（uvicorn），或调用 <code className="text-fg">POST /api/llm/reset</code>。
              </p>
            </div>
          </details>
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
