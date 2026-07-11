"use client";

import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Wrench,
  Trash2,
  Save,
  Eye,
  EyeOff,
  ChevronDown,
} from "lucide-react";
import useSWR from "swr";
import { api, type ChatMessage } from "@/lib/api";
import { useState, useEffect } from "react";

type Backend = "anthropic" | "deepseek" | "minimax" | "openai" | "custom";

interface LLMSettingsPublic {
  backend: Backend;
  model: string;
  api_key_masked: string | null;
  base_url: string | null;
  has_key: boolean;
  source: string;
}

interface LLMSettingsResponse {
  db_config: LLMSettingsPublic | null;
  env_config: LLMSettingsPublic;
  active_source: string;
  available: boolean;
  active_backend: string | null;
  active_model: string | null;
}

const BACKEND_LABELS: Record<Backend, { name: string; desc: string; needsKey: boolean; needsBaseUrl: boolean; docUrl?: string }> = {
  anthropic: {
    name: "Anthropic Claude",
    desc: "推荐，tool calling 强，中文好",
    needsKey: true,
    needsBaseUrl: false,
    docUrl: "https://console.anthropic.com/",
  },
  deepseek: {
    name: "DeepSeek",
    desc: "国内用户多，便宜，V3.2 + R1 强推理",
    needsKey: true,
    needsBaseUrl: true,
    docUrl: "https://platform.deepseek.com/api_keys",
  },
  minimax: {
    name: "MiniMax",
    desc: "国内用户多，abab6.5s 中文强；需 MiniMax key",
    needsKey: true,
    needsBaseUrl: true,
    docUrl: "https://api.minimax.chat/",
  },
  openai: {
    name: "OpenAI 兼容",
    desc: "OpenAI 官方 / Moonshot / 阿里云百炼 / 自定义",
    needsKey: true,
    needsBaseUrl: true,
  },
  custom: {
    name: "自定义",
    desc: "任意 OpenAI 兼容 endpoint（要 key + URL）",
    needsKey: true,
    needsBaseUrl: true,
  },
};

const DEFAULT_BASE_URLS: Record<Backend, string> = {
  anthropic: "https://api.anthropic.com",
  deepseek: "https://api.deepseek.com/v1",
  minimax: "https://api.minimax.chat/v1",
  openai: "https://api.openai.com/v1",
  custom: "",
};

const PRESETS: Record<Backend, string[]> = {
  anthropic: ["claude-sonnet-4-5", "claude-opus-4-5", "claude-3-5-haiku-20241022"],
  deepseek: ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
  minimax: [
    // MiniMax 官方 OpenAI 兼容 API 用的模型名（无前缀）
    // 用阿里云百炼 dashscope 时模型名要带 MiniMax- 前缀
    "abab6.5s-chat",
    "abab6.5t-chat",
    "abab6.5g-chat",
  ],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "moonshot-v1-128k"],
  custom: [],
};

export default function SettingsPage() {
  const { data: health } = useSWR("/api/health", () => api.health());
  const { data: settings, mutate: refreshSettings } = useSWR<LLMSettingsResponse>(
    "/api/settings/llm",
    () => api.getLLMSettings()
  );

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

        {/* LLM 配置（用户可编辑） */}
        <LLMConfigForm
          settings={settings}
          onSaved={refreshSettings}
        />

        {/* .env 默认值（只读，作为参考） */}
        {settings && settings.env_config && (
          <EnvConfigDisplay env={settings.env_config} activeSource={settings.active_source} />
        )}

        {/* 数据 */}
        <section className="rounded-lg border border-border bg-bg-secondary p-4 mt-4">
          <h2 className="text-sm font-semibold text-fg-secondary uppercase tracking-wider mb-3">
            数据
          </h2>
          <div className="text-xs text-fg-muted space-y-1">
            <p>数据目录：~/.cockpit/</p>
            <p>数据库：cockpit.db (SQLite)</p>
            <p>配置存：settings 表（key-value）</p>
            <p>备份：v1.1 接入 iCloud Drive 同步</p>
          </div>
        </section>
      </div>
    </div>
  );
}

function LLMConfigForm({
  settings,
  onSaved,
}: {
  settings: LLMSettingsResponse | undefined;
  onSaved: () => void;
}) {
  // 编辑状态：DB 配置优先，没有则用 env，再没有则用默认
  const initialSource: LLMSettingsPublic | undefined = settings?.db_config || settings?.env_config;
  const [backend, setBackend] = useState<Backend>(initialSource?.backend || "anthropic");
  const [model, setModel] = useState(initialSource?.model || "claude-sonnet-4-5");
  const [apiKey, setApiKey] = useState("");  // 留空 = 保留
  const [baseUrl, setBaseUrl] = useState(initialSource?.base_url || DEFAULT_BASE_URLS.anthropic);
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  // 当 settings 加载完，更新表单（只在首次）
  useEffect(() => {
    if (settings) {
      const src = settings.db_config || settings.env_config;
      if (src) {
        setBackend(src.backend);
        setModel(src.model);
        setBaseUrl(src.base_url || DEFAULT_BASE_URLS[src.backend]);
      }
    }
  }, [settings]);

  const meta = BACKEND_LABELS[backend];
  const presets = PRESETS[backend];

  // 切换后端时，重置 base_url / model
  const onBackendChange = (newBackend: Backend) => {
    setBackend(newBackend);
    setBaseUrl(DEFAULT_BASE_URLS[newBackend]);
    // 模型重置为该后端的第一个预设
    if (PRESETS[newBackend].length > 0 && !PRESETS[newBackend].includes(model)) {
      setModel(PRESETS[newBackend][0]);
    }
    setFeedback(null);
  };

  const test = async () => {
    setTesting(true);
    setFeedback(null);
    try {
      const r = await api.testLLM({
        backend,
        model,
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
      });
      if (r.ok) {
        setFeedback({ type: "ok", msg: `✓ ${r.backend} (${r.model}) 连接成功` });
      } else {
        setFeedback({ type: "err", msg: `✗ ${r.error || "连接失败"}` });
      }
    } catch (e) {
      setFeedback({ type: "err", msg: `✗ ${e instanceof Error ? e.message : String(e)}` });
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      await api.saveLLM({
        backend,
        model,
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
      });
      setFeedback({ type: "ok", msg: "✓ 已保存，LLM 已切换" });
      setApiKey("");  // 清空（已存 DB）
      onSaved();
    } catch (e) {
      setFeedback({ type: "err", msg: `✗ ${e instanceof Error ? e.message : String(e)}` });
    } finally {
      setSaving(false);
    }
  };

  const clear = async () => {
    if (!confirm("确定清除 UI 配置？会回退到 .env 默认值。")) return;
    try {
      await api.clearLLM();
      setFeedback({ type: "ok", msg: "✓ 已清除，回退到 .env 配置" });
      setApiKey("");
      onSaved();
    } catch (e) {
      setFeedback({ type: "err", msg: `✗ ${e instanceof Error ? e.message : String(e)}` });
    }
  };

  const currentSource = settings?.db_config ? "DB 用户配置" : "env 默认";

  return (
    <section className="rounded-lg border border-border bg-bg-secondary p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-fg-secondary uppercase tracking-wider">
          LLM 配置
        </h2>
        <div className="flex items-center gap-2 text-xs">
          {settings?.available ? (
            <span className="px-2 py-0.5 rounded bg-success/10 text-success">
              ● 已连接 · {settings.active_model}
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded bg-warning/10 text-warning">
              ○ 未连接
            </span>
          )}
          <span className="text-fg-muted">来源: {currentSource}</span>
        </div>
      </div>

      {/* 后端选择 */}
      <div className="mb-3">
        <label className="text-xs text-fg-secondary block mb-1.5">后端</label>
        <div className="grid grid-cols-2 gap-2">
          {(Object.keys(BACKEND_LABELS) as Backend[]).map((b) => {
            const info = BACKEND_LABELS[b];
            return (
              <button
                key={b}
                onClick={() => onBackendChange(b)}
                className={`text-left p-2.5 rounded border transition ${
                  backend === b
                    ? "border-accent bg-accent/10"
                    : "border-border hover:border-border-hover"
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium text-fg">{info.name}</span>
                  {info.docUrl && (
                    <a
                      href={info.docUrl}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-[10px] text-fg-muted hover:text-accent"
                      title="获取 API Key"
                    >
                      ↗ 拿 key
                    </a>
                  )}
                </div>
                <div className="text-[11px] text-fg-muted mt-0.5">{info.desc}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Base URL */}
      {meta.needsBaseUrl && (
        <div className="mb-3">
          <label className="text-xs text-fg-secondary block mb-1.5">
            Base URL
            {backend === "deepseek" && (
              <span className="text-fg-muted ml-2">
                默认: <code className="text-fg">https://api.deepseek.com/v1</code>（已自动填好）
              </span>
            )}
            {backend === "minimax" && (
              <span className="text-fg-muted ml-2">
                默认: <code className="text-fg">https://api.minimax.chat/v1</code>
                （官方 OpenAI 兼容端点；如果用阿里云百炼 key，改 base_url 为
                <code className="text-fg">https://dashscope.aliyuncs.com/compatible-mode/v1</code> 且模型名加 <code className="text-fg">MiniMax-</code> 前缀）
              </span>
            )}
            {backend === "openai" && (
              <span className="text-fg-muted ml-2">
                Moonshot: <code className="text-fg">https://api.moonshot.cn/v1</code> · 阿里云百炼: <code className="text-fg">https://dashscope.aliyuncs.com/compatible-mode/v1</code>
              </span>
            )}
          </label>
          <input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://..."
            className="w-full bg-bg border border-border rounded px-2.5 py-1.5 text-sm text-fg placeholder-fg-muted focus:outline-none focus:border-accent font-mono"
          />
        </div>
      )}

      {/* Model */}
      <div className="mb-3">
        <label className="text-xs text-fg-secondary block mb-1.5">模型</label>
        {presets.length > 0 ? (
          <div className="flex gap-2">
            <select
              value={presets.includes(model) ? model : "__custom__"}
              onChange={(e) => {
                if (e.target.value !== "__custom__") setModel(e.target.value);
                else setModel("");
              }}
              className="bg-bg border border-border rounded px-2.5 py-1.5 text-sm text-fg focus:outline-none focus:border-accent"
            >
              {presets.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
              <option value="__custom__">自定义...</option>
            </select>
            {!presets.includes(model) && (
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="自定义模型名"
                className="flex-1 bg-bg border border-border rounded px-2.5 py-1.5 text-sm text-fg placeholder-fg-muted focus:outline-none focus:border-accent"
              />
            )}
          </div>
        ) : (
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="模型名..."
            className="w-full bg-bg border border-border rounded px-2.5 py-1.5 text-sm text-fg placeholder-fg-muted focus:outline-none focus:border-accent"
          />
        )}
      </div>

      {/* API Key */}
      {meta.needsKey && (
        <div className="mb-3">
          <label className="text-xs text-fg-secondary block mb-1.5">
            API Key
            {settings?.db_config?.has_key && (
              <span className="text-fg-muted ml-2">
                （当前: <code className="text-fg">{settings.db_config.api_key_masked}</code>，留空保留）
              </span>
            )}
          </label>
          <div className="flex gap-2">
            <input
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={settings?.db_config?.has_key ? "输入新 key 替换" : "sk-..."}
              className="flex-1 bg-bg border border-border rounded px-2.5 py-1.5 text-sm text-fg placeholder-fg-muted focus:outline-none focus:border-accent font-mono"
            />
            <button
              onClick={() => setShowKey((s) => !s)}
              className="p-2 text-fg-muted hover:text-fg"
              title={showKey ? "隐藏" : "显示"}
            >
              {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex items-center gap-2 mt-4">
        <button
          onClick={test}
          disabled={testing}
          className="text-xs px-3 py-1.5 bg-bg border border-border rounded text-fg hover:border-accent disabled:opacity-50 transition flex items-center gap-1"
        >
          <Wrench size={12} />
          {testing ? "测试中..." : "测试连接"}
        </button>
        <button
          onClick={save}
          disabled={saving}
          className="text-xs px-3 py-1.5 bg-accent text-black rounded hover:bg-accent-hover disabled:opacity-50 transition flex items-center gap-1"
        >
          <Save size={12} />
          {saving ? "保存中..." : "保存"}
        </button>
        {settings?.db_config && (
          <button
            onClick={clear}
            className="text-xs px-3 py-1.5 bg-bg border border-border rounded text-fg-secondary hover:text-danger hover:border-danger transition flex items-center gap-1"
          >
            <Trash2 size={12} />
            清除配置
          </button>
        )}
        <button
          onClick={onSaved}
          className="ml-auto text-xs px-2 py-1.5 text-fg-muted hover:text-fg transition"
          title="刷新"
        >
          <RefreshCw size={12} />
        </button>
      </div>

      {/* 反馈 */}
      {feedback && (
        <div
          className={`mt-3 text-xs px-2.5 py-1.5 rounded ${
            feedback.type === "ok"
              ? "bg-success/10 text-success"
              : "bg-danger/10 text-danger"
          }`}
        >
          {feedback.msg}
        </div>
      )}
    </section>
  );
}

function EnvConfigDisplay({
  env,
  activeSource,
}: {
  env: LLMSettingsPublic;
  activeSource: string;
}) {
  return (
    <section className="rounded-lg border border-border bg-bg-secondary p-4 mb-4">
      <h2 className="text-sm font-semibold text-fg-secondary uppercase tracking-wider mb-3">
        .env 默认配置（只读）
      </h2>
      <div className="text-xs space-y-1 text-fg-secondary font-mono">
        <div>
          <span className="text-fg-muted">COCKPIT_LLM_BACKEND=</span>
          <span className="text-fg">{env.backend}</span>
        </div>
        <div>
          <span className="text-fg-muted">COCKPIT_LLM_MODEL=</span>
          <span className="text-fg">{env.model}</span>
        </div>
        <div>
          <span className="text-fg-muted">base_url=</span>
          <span className="text-fg">{env.base_url || "—"}</span>
        </div>
        <div>
          <span className="text-fg-muted">api_key=</span>
          <span className="text-fg">
            {env.has_key ? env.api_key_masked : "（未设置）"}
          </span>
        </div>
      </div>
      {activeSource === "env" && (
        <p className="text-[11px] text-fg-muted mt-2">
          当前 LLM 正在使用此配置。在上方表单保存即可覆盖。
        </p>
      )}
    </section>
  );
}
