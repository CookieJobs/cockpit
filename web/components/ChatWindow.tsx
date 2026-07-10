"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { api, type ChatResponse, type ChatHistoryMessage, type ChatSession } from "@/lib/api";
import { renderMarkdown } from "./Markdown";
import { Send, Sparkles, Wrench, Plus, History, Trash2, MessageSquare, X, Eraser } from "lucide-react";

const SESSION_STORAGE_KEY = "shiguang_session_id";

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

// localStorage 工具
function getStoredSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(SESSION_STORAGE_KEY);
}

function setStoredSessionId(id: string | null): void {
  if (typeof window === "undefined") return;
  if (id) localStorage.setItem(SESSION_STORAGE_KEY, id);
  else localStorage.removeItem(SESSION_STORAGE_KEY);
}

function genSessionId(): string {
  // 简单 UUID v4
  return "sess-" + crypto.randomUUID();
}

// 把后端 ChatHistoryMessage 转成 UI Message
function historyToUI(msgs: ChatHistoryMessage[]): Message[] {
  return msgs.map((m) => ({
    id: m.id,
    role: m.role === "user" ? "user" : "agent",
    // 后端 assistant content 是 JSON 字符串（Anthropic content list），取首个 text block
    content:
      m.role === "assistant" && m.content.startsWith("[")
        ? extractTextFromAnthropicContent(m.content) || m.content
        : m.content,
    toolCalls: m.tool_calls?.map((tc) => ({
      name: tc.name,
      args: tc.args,
    })),
    usedLLM: m.role === "assistant",
    timestamp: new Date(m.created_at).getTime(),
  }));
}

function extractTextFromAnthropicContent(jsonStr: string): string {
  try {
    const blocks = JSON.parse(jsonStr);
    if (Array.isArray(blocks)) {
      const texts = blocks
        .filter((b: unknown) => {
          if (typeof b !== "object" || b === null) return false;
          const obj = b as Record<string, unknown>;
          return obj.type === "text";
        })
        .map((b: { text: string }) => b.text);
      return texts.join("");
    }
  } catch {
    // ignore
  }
  return jsonStr;
}

export function ChatWindow({ onAction }: { onAction?: () => void }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 自动滚到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // 初始化：确保 session 存在 + 加载历史
  useEffect(() => {
    let cancelled = false;
    (async () => {
      let sid = getStoredSessionId();
      if (!sid) {
        sid = genSessionId();
        setStoredSessionId(sid);
      }
      try {
        // 确保 session 存在（幂等）
        await api.createSession(sid);
        if (cancelled) return;
        setSessionId(sid);
        // 加载历史
        const { messages: histMsgs } = await api.listMessages(sid, 40);
        if (cancelled) return;
        if (histMsgs.length > 0) {
          setMessages(historyToUI(histMsgs));
        } else {
          // 首次：显示欢迎
          setMessages([
            {
              id: "welcome",
              role: "agent",
              content:
                "你好！我是拾光 🤖\n\n可以试试说「我现在该干啥」「添加任务 XXX」「修 bug 完成了」\n\n带 ● LLM 徽章时我用 LLM 理解，无徽章时用关键词模式。\n对话已自动保存，刷新页面不会丢失～",
              timestamp: Date.now(),
            },
          ]);
        }
      } catch (e) {
        console.error("Failed to init chat session:", e);
        if (cancelled) return;
        // 兜底：欢迎消息，无 session
        setMessages([
          {
            id: "welcome",
            role: "agent",
            content: "你好！我是拾光 🤖（离线模式，对话不持久化）",
            timestamp: Date.now(),
          },
        ]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const { sessions: s } = await api.listSessions(false, 20);
      setSessions(s);
    } catch (e) {
      console.error("Failed to list sessions:", e);
    }
  }, []);

  const switchToSession = async (sid: string) => {
    if (sid === sessionId) {
      setHistoryOpen(false);
      return;
    }
    try {
      const { messages: histMsgs } = await api.listMessages(sid, 40);
      setSessionId(sid);
      setStoredSessionId(sid);
      setMessages(histMsgs.length > 0 ? historyToUI(histMsgs) : [
        {
          id: "welcome",
          role: "agent",
          content: "（空对话）",
          timestamp: Date.now(),
        },
      ]);
      setHistoryOpen(false);
    } catch (e) {
      console.error("Failed to switch session:", e);
    }
  };

  const startNewSession = async () => {
    const sid = genSessionId();
    try {
      await api.createSession(sid);
      setSessionId(sid);
      setStoredSessionId(sid);
      setMessages([
        {
          id: "welcome",
          role: "agent",
          content: "🆕 新对话已开启，说点什么吧～",
          timestamp: Date.now(),
        },
      ]);
      setHistoryOpen(false);
    } catch (e) {
      console.error("Failed to create session:", e);
    }
  };

  const deleteSession = async (sid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("确定删除这个对话吗？消息会一并清除。")) return;
    try {
      await api.deleteSession(sid);
      await refreshSessions();
      // 如果删的是当前 session，新建一个
      if (sid === sessionId) {
        await startNewSession();
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  const cleanupEmpty = async () => {
    if (
      !confirm(
        "清理所有空对话（≤ 2 条消息的 session）？\n\n将保留 3 条以上消息的有意义对话。"
      )
    )
      return;
    try {
      const res = await api.cleanupEmptySessions();
      await refreshSessions();
      alert(`已清理 ${res.deleted_count} 个空对话。`);
      if (res.deleted_ids.includes(sessionId || "")) {
        await startNewSession();
      }
    } catch (err) {
      console.error("Failed to cleanup sessions:", err);
    }
  };

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || !sessionId) return;

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
      const res: ChatResponse = await api.chat(trimmed, undefined, sessionId);
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
    <div className="flex flex-col h-full bg-bg relative">
      {/* 顶部工具栏 */}
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2 text-xs text-fg-muted">
          <MessageSquare size={12} />
          <span>对话</span>
          {sessionId && (
            <span className="text-[10px] text-fg-muted opacity-60">
              · {sessionId.slice(-8)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={startNewSession}
            className="text-xs px-2 py-1 bg-bg-secondary border border-border rounded text-fg-secondary hover:border-border-hover hover:text-fg transition flex items-center gap-1"
            title="开始新对话"
          >
            <Plus size={11} />
            新对话
          </button>
          <button
            onClick={() => {
              setHistoryOpen((v) => !v);
              if (!historyOpen) refreshSessions();
            }}
            className={`text-xs px-2 py-1 border border-border rounded transition flex items-center gap-1 ${
              historyOpen
                ? "bg-accent text-black"
                : "bg-bg-secondary text-fg-secondary hover:border-border-hover hover:text-fg"
            }`}
            title="历史对话"
          >
            <History size={11} />
            历史
          </button>
        </div>
      </div>

      {/* 历史对话侧栏 */}
      {historyOpen && (
        <SessionListPanel
          sessions={sessions}
          currentId={sessionId}
          onSwitch={switchToSession}
          onDelete={deleteSession}
          onCleanup={cleanupEmpty}
          onClose={() => setHistoryOpen(false)}
        />
      )}

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

function SessionListPanel({
  sessions,
  currentId,
  onSwitch,
  onDelete,
  onCleanup,
  onClose,
}: {
  sessions: ChatSession[];
  currentId: string | null;
  onSwitch: (id: string) => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
  onCleanup: () => void;
  onClose: () => void;
}) {
  const emptyCount = sessions.filter((s) => s.message_count <= 2).length;
  return (
    <div className="absolute top-0 right-0 bottom-0 w-72 bg-bg-secondary border-l border-border z-10 flex flex-col shadow-lg">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <div className="text-sm font-medium text-fg">历史对话</div>
        <button
          onClick={onClose}
          className="p-1 text-fg-muted hover:text-fg transition"
          title="关闭"
        >
          <X size={14} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="p-4 text-xs text-fg-muted text-center">暂无历史对话</div>
        ) : (
          sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => onSwitch(s.id)}
              className={`group px-3 py-2.5 border-b border-border cursor-pointer transition flex items-start gap-2 ${
                s.id === currentId
                  ? "bg-bg-tertiary"
                  : "hover:bg-bg-tertiary"
              }`}
            >
              <MessageSquare
                size={14}
                className={`mt-0.5 shrink-0 ${
                  s.id === currentId ? "text-accent" : "text-fg-muted"
                }`}
              />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-fg truncate">{s.label}</div>
                <div className="text-[10px] text-fg-muted mt-0.5 flex items-center gap-2">
                  <span>{s.message_count} 条消息</span>
                  <span>·</span>
                  <span>{formatRelativeTime(s.last_active_at)}</span>
                </div>
              </div>
              <button
                onClick={(e) => onDelete(s.id, e)}
                className="opacity-0 group-hover:opacity-100 p-1 text-fg-muted hover:text-danger transition"
                title="删除"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))
        )}
      </div>
      {emptyCount > 0 && (
        <div className="border-t border-border p-2 bg-bg">
          <button
            onClick={onCleanup}
            className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-xs text-fg-muted hover:text-danger hover:bg-bg-tertiary rounded transition"
            title="删除 2 条消息以内的空对话"
          >
            <Eraser size={11} />
            清理 {emptyCount} 个空对话
          </button>
        </div>
      )}
    </div>
  );
}

function formatRelativeTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "刚刚";
    if (diffMin < 60) return `${diffMin} 分钟前`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr} 小时前`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 7) return `${diffDay} 天前`;
    return d.toLocaleDateString("zh-CN");
  } catch {
    return iso;
  }
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