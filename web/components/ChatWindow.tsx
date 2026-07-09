"use client";

import { useState } from "react";
import { api, type ChatResponse } from "@/lib/api";
import { renderMarkdown } from "./Markdown";
import { Send, Sparkles } from "lucide-react";

type Message = {
  id: string;
  role: "user" | "agent";
  content: string;
  action?: string | null;
  timestamp: number;
};

const SUGGESTIONS = [
  "我现在该干啥",
  "添加任务 修登录 bug",
  "整理周报",
  "述职",
];

export function ChatWindow({ onAction }: { onAction?: () => void }) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "agent",
      content: "你好！我是拾光 🤖\n\n试试说「我现在该干啥」看今天的任务，或「添加任务 XXX」新建一个。",
      timestamp: Date.now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
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
      const res: ChatResponse = await api.chat(trimmed);
      const agentMsg: Message = {
        id: `a-${Date.now()}`,
        role: "agent",
        content: res.text,
        action: res.action,
        timestamp: Date.now(),
      };
      setMessages((m) => [...m, agentMsg]);
      // 触发父组件刷新（focus / 任务列表）
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
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"} fade-in`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2.5 ${
                m.role === "user"
                  ? "bg-accent text-black"
                  : "bg-bg-secondary border border-border text-fg"
              }`}
            >
              {m.role === "agent" ? (
                <div className="markdown text-sm">{renderMarkdown(m.content)}</div>
              ) : (
                <div className="text-sm whitespace-pre-wrap">{m.content}</div>
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
            placeholder="说话或输入命令..."
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
