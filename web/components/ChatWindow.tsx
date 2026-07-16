"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { api, type ChatResponse, type ChatHistoryMessage, type ChatSession } from "@/lib/api";
import { renderMarkdown } from "./Markdown";
import { ToolCallCard, type ToolCallState } from "./ToolCallCard";
import {
  Send,
  Sparkles,
  Plus,
  History,
  Trash2,
  MessageSquare,
  X,
  Eraser,
  Eye,
  EyeOff,
  Brain,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

const SESSION_STORAGE_KEY = "cockpit_session_id";
const SHOW_COT_STORAGE_KEY = "cockpit_show_cot";

type Message = {
  id: string;
  role: "user" | "agent";
  // 新流式消息：events 按 LLM 实际产出顺序（text 段 + tool 块交错）
  // 老消息（历史 session 加载）没有 events 字段，渲染时回退到 content+toolCalls
  events?: AgentEventItem[];
  // 老消息兼容：text 全文 + tool 列表（历史持久化格式）
  content?: string;
  toolCalls?: ToolCallState[];
  cotBlocks?: string[]; // 完整 think 块原文（仅本轮 session 流式时拿到；历史不存）
  streaming?: boolean; // agent 消息：是否正在流式
  usedLLM?: boolean;
  timestamp: number;
};

// 流式事件项：按时间序累积。text 段会被相邻 text 事件合并（减少 list 项数）。
export type AgentEventItem =
  | { kind: "text"; content: string }
  | { kind: "tool"; tc: ToolCallState };

/**
 * 纯函数：把一个 SSE 事件应用到 events 数组，返回新数组。
 * - text delta：合并到最后一个 text 事件（没有则 push 新 text）
 * - tool_start：append 新 tool 事件（status: calling）
 * - tool_end：找到对应 tool 事件，update tc 的 result/ok/status
 * - 其它事件（start/cot/end/error）：events 数组不动
 *
 * 抽出来做 pure function 方便 unit test（不依赖 React state）。
 */
export function applyStreamEvent(
  events: AgentEventItem[],
  event: { type: string; data: any }
): AgentEventItem[] {
  if (event.type === "text") {
    const delta = event.data?.delta ?? "";
    if (!delta) return events;
    const last = events[events.length - 1];
    if (last && last.kind === "text") {
      const updated = [...events];
      updated[updated.length - 1] = { ...last, content: last.content + delta };
      return updated;
    }
    return [...events, { kind: "text", content: delta }];
  }
  if (event.type === "tool_start") {
    return [
      ...events,
      {
        kind: "tool",
        tc: {
          id: event.data.id,
          name: event.data.name,
          args: event.data.args || {},
          status: "calling",
        },
      },
    ];
  }
  if (event.type === "tool_end") {
    return events.map((e) =>
      e.kind === "tool" && e.tc.id === event.data.id
        ? {
            ...e,
            tc: {
              ...e.tc,
              result: event.data.result,
              ok: event.data.ok,
              status: event.data.ok ? "done" : "error",
            },
          }
        : e
    );
  }
  return events; // start / cot / end / error 不动 events 数组
}

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

// CoT 开关：纯前端状态（localStorage），不持久化到 db。
// 默认 false（隐藏 CoT）。打开后会在 agent 消息下方渲染可折叠的
// 思维链块（仅本轮 session 流式时有数据，历史消息不存 CoT）。
function getShowCot(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(SHOW_COT_STORAGE_KEY) === "true";
}

function setShowCot(v: boolean): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(SHOW_COT_STORAGE_KEY, v ? "true" : "false");
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
    // 历史消息：tool_calls 是 summary（无 result）
    toolCalls: m.tool_calls?.map((tc) => ({
      id: tc.id || `hist-${tc.name}`,
      name: tc.name,
      args: tc.args,
      status: "done" as const,
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
      return stripThinkBlocks(texts.join(""));
    }
  } catch {
    // ignore
  }
  return stripThinkBlocks(jsonStr);
}

// 兜底剥离 LLM CoT 思维链块（<think>...</think> / <thinking>...</thinking>
// / <reasoning>...</reasoning>）。后端 chat_engine 已经在 response 入口
// strip 过一次了，但旧 session 持久化的消息可能还含 think 块 —— 这里
// 再做一次 defense-in-depth 避免历史消息里残留 CoT 显示给用户。
// 逻辑与后端 _THINK_BLOCK_RE 保持一致。
const THINK_BLOCK_RE = /<\s*(?:think|thinking|reasoning)\b[^>]*>.*?<\s*\/\s*(?:think|thinking|reasoning)\s*>/gis;

function stripThinkBlocks(text: string): string {
  if (!text) return text;
  return text.replace(THINK_BLOCK_RE, " ").trim();
}

export function ChatWindow({ onAction }: { onAction?: () => void }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [showCot, setShowCotState] = useState<boolean>(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 初始化 CoT 开关（localStorage → state）
  useEffect(() => {
    setShowCotState(getShowCot());
  }, []);

  const toggleShowCot = useCallback(() => {
    setShowCotState((v) => {
      const next = !v;
      setShowCot(next);
      return next;
    });
  }, []);

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
                "你好！我是Cockpit 🤖\n\n可以试试说「我现在该干啥」「添加任务 XXX」「修 bug 完成了」\n\n带 ● LLM 徽章时我用 LLM 理解，无徽章时用关键词模式。\n对话已自动保存，刷新页面不会丢失～",
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
            content: "你好！我是Cockpit 🤖（离线模式，对话不持久化）",
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
    // 预创建 streaming agent message：events 数组按 LLM 实际产出顺序累积
    // （text 段 + tool 块交错），流式过程中光标始终在最后一个 text 事件末尾
    const agentMsgId = `a-${Date.now()}`;
    const agentMsg: Message = {
      id: agentMsgId,
      role: "agent",
      events: [],
      streaming: true,
      timestamp: Date.now(),
    };
    setMessages((m) => [...m, userMsg, agentMsg]);
    setInput("");
    setLoading(true);

    // 工具函数：找到当前 agent message 并 patch
    const patchAgent = (patch: (m: Message) => Message) => {
      setMessages((msgs) =>
        msgs.map((m) => (m.id === agentMsgId ? patch(m) : m))
      );
    };

    try {
      await api.chatStream(trimmed, sessionId, (event) => {
        if (event.type === "text" || event.type === "tool_start" || event.type === "tool_end") {
          // 用纯函数 applyStreamEvent 累积 events
          patchAgent((m) => ({
            ...m,
            events: applyStreamEvent(m.events || [], event),
          }));
        } else if (event.type === "end") {
          patchAgent((m) => ({
            ...m,
            streaming: false,
            usedLLM: true,
            cotBlocks: event.data.cot_blocks || undefined,
          }));
        } else if (event.type === "error") {
          // 错误：append 到最后一个 text 事件（或 push 新 text）
          const errMsg = `❌ ${event.data.message}`;
          patchAgent((m) => {
            const events = m.events || [];
            const last = events[events.length - 1];
            if (last && last.kind === "text") {
              const updated = [...events];
              updated[updated.length - 1] = {
                ...last,
                content: last.content + (last.content ? "\n\n" : "") + errMsg,
              };
              return { ...m, events: updated, streaming: false };
            }
            return {
              ...m,
              events: [...events, { kind: "text", content: errMsg }],
              streaming: false,
            };
          });
        }
        // 'start' / 'cot' 事件：暂不处理（cot 由 API 层捕获后放 end.cot_blocks）
      });
      if (onAction) onAction();
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      patchAgent((m) => {
        const events = m.events || [];
        const last = events[events.length - 1];
        const errText = `❌ 错误：${errMsg}`;
        if (last && last.kind === "text") {
          const updated = [...events];
          updated[updated.length - 1] = {
            ...last,
            content: last.content + (last.content ? "\n\n" : "") + errText,
          };
          return { ...m, events: updated, streaming: false };
        }
        return {
          ...m,
          events: [...events, { kind: "text", content: errText }],
          streaming: false,
        };
      });
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
            onClick={toggleShowCot}
            className={`text-xs px-2 py-1 border border-border rounded transition flex items-center gap-1 ${
              showCot
                ? "bg-accent/20 text-accent border-accent/40"
                : "bg-bg-secondary text-fg-secondary hover:border-border-hover hover:text-fg"
            }`}
            title={showCot ? "隐藏 AI 思维链" : "显示 AI 思维链"}
          >
            {showCot ? <Eye size={11} /> : <EyeOff size={11} />}
            CoT
          </button>
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
              <div
                className={`rounded-lg px-4 py-2.5 ${
                  m.role === "user"
                    ? "bg-accent text-black"
                    : "bg-bg-secondary border border-border text-fg"
                }`}
              >
                {m.role === "agent" ? (
                  <AgentMessageContent
                    message={m}
                    showCot={showCot}
                  />
                ) : (
                  <div className="text-sm whitespace-pre-wrap">{m.content}</div>
                )}
              </div>
              {m.role === "agent" && m.usedLLM !== undefined && !m.streaming && (
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

/**
 * Agent 消息内容：
 * - 新流式消息（有 events 字段）：按事件时间序渲染（text 段 + tool 块
 *   交错），流式期间最后一个 text 段末尾带闪烁光标
 * - 老消息（无 events 字段，回退到 content + toolCalls 分离格式）：
 *   tool 列表在上 + text 一次性 markdown 渲染
 * - CoT 折叠块：仅 showCot && cotBlocks.length > 0 时显示
 */
function AgentMessageContent({
  message,
  showCot,
}: {
  message: Message;
  showCot: boolean;
}) {
  const hasEvents = message.events && message.events.length > 0;

  if (hasEvents) {
    return (
      <EventsView
        events={message.events!}
        streaming={!!message.streaming}
        showCot={showCot}
        cotBlocks={message.cotBlocks}
      />
    );
  }

  // 退化路径：老消息（content + toolCalls 分离）
  const text = message.content || (message.toolCalls?.length ? "✅ 已执行" : "（无响应）");
  return (
    <div className="space-y-2">
      {message.toolCalls && message.toolCalls.length > 0 && (
        <div className="space-y-1">
          {message.toolCalls.map((tc) => (
            <ToolCallCard key={tc.id} tc={tc} />
          ))}
        </div>
      )}
      <div className="markdown text-sm">{renderMarkdown(text)}</div>
      {showCot && message.cotBlocks && message.cotBlocks.length > 0 && (
        <CotBlock blocks={message.cotBlocks} />
      )}
    </div>
  );
}

/**
 * EventsView：按事件时间序渲染（text 段 + tool 块交错）
 * - streaming 期间：text 用纯文本（不跑 markdown） + 最后一段末尾闪烁光标
 * - 结束后：text 段跑 markdown 渲染
 * - tool 卡按 ToolCallCard 默认展开
 */
function EventsView({
  events,
  streaming,
  showCot,
  cotBlocks,
}: {
  events: AgentEventItem[];
  streaming: boolean;
  showCot: boolean;
  cotBlocks?: string[];
}) {
  if (events.length === 0) {
    return (
      <div className="text-sm text-fg-muted">
        {streaming ? "思考中…" : "（无响应）"}
      </div>
    );
  }
  // 找最后一个 text 事件索引（光标只放这里）
  const lastTextIdx = (() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].kind === "text") return i;
    }
    return -1;
  })();

  return (
    <div className="space-y-2">
      {events.map((e, i) => {
        if (e.kind === "text") {
          const isLastText = i === lastTextIdx;
          if (streaming && isLastText) {
            return (
              <div key={`text-${i}`} className="text-sm whitespace-pre-wrap">
                {e.content}
                <span className="cursor-blink">▍</span>
              </div>
            );
          }
          // 非流式 OR 非最后 text 段：跑 markdown
          return (
            <div key={`text-${i}`} className="markdown text-sm">
              {renderMarkdown(e.content)}
            </div>
          );
        }
        // tool 块
        return <ToolCallCard key={`tool-${e.tc.id}`} tc={e.tc} />;
      })}
      {showCot && cotBlocks && cotBlocks.length > 0 && (
        <CotBlock blocks={cotBlocks} />
      )}
    </div>
  );
}

/**
 * CoT 折叠块：默认折叠，点击 header 展开。带 Brain 图标。
 * 每个 think 块（`<think>...</think>`）独立一个折叠区。
 */
function CotBlock({ blocks }: { blocks: string[] }) {
  const [expanded, setExpanded] = useState(false);
  // 内部把 think 标签剥掉再展示（标签本身是结构标记）
  const cleaned = blocks.map((b) => b.replace(/^<think>\s*/i, "").replace(/\s*<\/think>\s*$/i, ""));
  return (
    <div className="rounded-md border border-border/50 bg-bg-tertiary/40 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-2.5 py-1.5 text-[11px] text-fg-muted hover:text-fg-secondary hover:bg-bg-tertiary/60 transition text-left"
      >
        <Brain size={11} className="shrink-0" />
        <span>AI 思维链</span>
        <span className="text-fg-muted/60">({blocks.length} 块)</span>
        <span className="ml-auto">
          {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
        </span>
      </button>
      {expanded && (
        <div className="border-t border-border/40 px-2.5 py-2 space-y-2">
          {cleaned.map((text, i) => (
            <pre
              key={i}
              className="text-[11px] text-fg-muted whitespace-pre-wrap break-words leading-relaxed italic"
            >
              {text}
            </pre>
          ))}
        </div>
      )}
    </div>
  );
}