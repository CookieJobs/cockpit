"use client";

import { useState, useRef, useEffect } from "react";
import { api, type ChatResponse, type ChatMessage } from "@/lib/api";
import { renderMarkdown } from "./Markdown";
import { Send, Sparkles, Wrench, CheckCircle2, XCircle } from "lucide-react";

type Message = {
  id: string;
  role: "user" | "agent";
  content: string;
  toolCalls?: Array<{ name: string; args: Record<string, unknown>; result_preview?: string }>;
  usedLLM?: boolean;
  timestamp: number;
};

const SUGGESTIONS = [
  "我现在该干啥？",
  "添加任务：修登录 bug",
  "修登录 bug 完成了",
  "整理周报",
  "整理述职材料",
];

export function ChatWindow({ onAction }: { onAction?: () => void }) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "agent",
      content:
        "你好！我是拾光 🤖\n\n可以试试说「我现在该干啥」「添加任务 XXX」「修 bug 完成了」\n\n（带 ● LLM 徽章时我用 LLM 理解，无徽章时用关键词模式）",
      timestamp: Date.now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 自动滚到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    // 构造历史（仅保留文本，不带 tool_calls 等）
    const history: ChatMessage[] = messages
      .filter((m) => m.id !== "welcome")
      .map((m) => ({ role: m.role, content: m.content }));

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: Date.now(),
    };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const res: ChatResponse = await api.chat(trimmed, history);
      const agentMsg: Message = {
        id: `a-${Date.now()}`,
        role: "agent",
        content: res.text,
        toolCalls: res.tool_calls || undefined,
        usedLLM: res.used_llm,
        timestamp: Date.now(),
      };
      setMessages((m) => [...m, agentMsg]);
      if (onAction) onAction();
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      setMessages((m) => [
        ...m,
        {
          id: `e-${Date.now()}`,
          role: "agent",
          content: `❌ 错误：${errMsg}`,
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-bg">
      {/* 消息区 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"} fade-in`}
          >
            <div className="max-w-[85%] min-w-[200px]">
              {/* Tool calls 展示 */}
              {m.toolCalls && m.toolCalls.length > 0 && (
                <div className="mb-1.5 space-y-1">
                  {m.toolCalls.map((tc, i) => (
                    <ToolCallBadge key={i} tc={tc} />
                  ))}
                </div>
              )}
              <div
                className={`rounded-lg px-4 py-2.5 ${
                  m.role === "user"
                    ? "bg-accent text-black"
                    : "bg-bg-secondary border border-border text-fg"
                }`}
              >
                {m.role === "agent" ? (
                  <div className="markdown text-sm">
                    {renderMarkdown(m.content || (m.toolCalls?.length ? "✅ 已执行" : "（无响应）"))}
                  </div>
                ) : (
                  <div className="text-sm whitespace-pre-wrap">{m.content}</div>
                )}
              </div>
              {m.role === "agent" && m.usedLLM !== undefined && (
                <div className="mt-1 text-[10px] text-fg-muted">
                  {m.usedLLM ? "via LLM" : "via 关键词"}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start fade-in">
            <div className="bg-bg-secondary border border-border rounded-lg px-4 py-2.5">
              <div className="flex items-center gap-1 text-fg-muted text-sm">
                <Sparkles size={14} className="animate-pulse" />
                <span>思考中...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 快捷建议 */}
      {messages.length <= 1 && (
        <div className="px-4 pb-2 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="text-xs px-3 py-1.5 bg-bg-secondary border border-border rounded-full text-fg-secondary hover:border-border-hover hover:text-fg transition"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* 输入区 */}
      <div className="border-t border-border p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="说点什么..."
            className="flex-1 bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-fg placeholder-fg-muted focus:outline-none focus:border-accent"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="p-2 bg-accent text-black rounded-lg hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}

function ToolCallBadge({
  tc,
}: {
  tc: { name: string; args: Record<string, unknown>; result_preview?: string };
}) {
  return (
    <div className="rounded-md bg-bg-tertiary border border-border px-2.5 py-1.5 text-xs">
      <div className="flex items-center gap-1.5 text-fg-secondary">
        <Wrench size={11} />
        <span className="font-mono">{tc.name}</span>
        <span className="text-fg-muted">
          ({Object.entries(tc.args).slice(0, 2).map(([k, v]) => `${k}=${String(v).slice(0, 20)}`).join(", ")})
        </span>
      </div>
    </div>
  );
}
