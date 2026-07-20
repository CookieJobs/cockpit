"use client";

/**
 * useChatStream — chat streaming state machine hook (2026-07-20 立)。
 *
 * 背景：ChatWindow 869 行有 100+ 行是 SSE 流式状态机（send 函数 + patchAgent
 * 闭包 + 错误处理），跟 UI 渲染混在一起。改 chat 行为要翻整个文件。
 *
 * 这个 hook 把"流式状态"从 ChatWindow 抽出来：
 * - 拥有 messages 状态
 * - send(text) 处理 user/agent 创建 + SSE 事件累积 + 错误恢复
 * - setHistory(msgs) 加载历史 session（替换当前消息列表）
 * - clear() 清空（开始新 session）
 *
 * 依赖的纯函数 applyStreamEvent 已在 ChatWindow.tsx 里 export，
 * 复用之（已用 unit test 覆盖, 见 test_chat_stream_apply_event.py 后续可加）。
 */

import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import { applyStreamEvent, type AgentEventItem } from "@/components/ChatWindow";
import type { ToolCallState } from "@/components/ToolCallCard";

// 跟 ChatWindow 里的 Message 类型保持一致 — 不重复定义, 避免 drift
export type ChatMessage = {
  id: string;
  role: "user" | "agent";
  events?: AgentEventItem[];
  content?: string;
  toolCalls?: ToolCallState[];
  cotBlocks?: string[];
  streaming?: boolean;
  usedLLM?: boolean;
  timestamp: number;
};

export interface UseChatStreamOptions {
  sessionId: string | null;
  onComplete?: (usedLLM: boolean) => void;
}

export function useChatStream({ sessionId, onComplete }: UseChatStreamOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  /**
   * 发送一条消息，触发流式响应。
   * 副作用：push user + agent(stub) 到 messages, 累计 events, 完成时调 onComplete。
   */
  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !sessionId) return;

      const userMsg: ChatMessage = {
        id: `u-${Date.now()}`,
        role: "user",
        content: trimmed,
        timestamp: Date.now(),
      };
      const agentMsgId = `a-${Date.now()}`;
      const agentMsg: ChatMessage = {
        id: agentMsgId,
        role: "agent",
        events: [],
        streaming: true,
        timestamp: Date.now(),
      };
      setMessages((m) => [...m, userMsg, agentMsg]);
      setLoading(true);

      // 闭包工具: 找到当前 agent message 并 patch
      const patchAgent = (patch: (m: ChatMessage) => ChatMessage) => {
        setMessages((msgs) =>
          msgs.map((m) => (m.id === agentMsgId ? patch(m) : m))
        );
      };

      // 把"错误文本"塞进 events 数组的 helper
      const appendError = (m: ChatMessage, errText: string): ChatMessage => {
        const events = m.events || [];
        const last = events[events.length - 1];
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
      };

      let usedLLM = false;

      try {
        await api.chatStream(trimmed, sessionId, (event) => {
          if (
            event.type === "text" ||
            event.type === "tool_start" ||
            event.type === "tool_end"
          ) {
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
            usedLLM = true;
          } else if (event.type === "error") {
            patchAgent((m) => appendError(m, `❌ ${event.data.message}`));
          }
          // 'start' / 'cot' 事件：暂不处理（cot 由 end.cot_blocks 统一携带）
        });
      } catch (e: unknown) {
        const errMsg = e instanceof Error ? e.message : String(e);
        patchAgent((m) => appendError(m, `❌ 错误：${errMsg}`));
      } finally {
        setLoading(false);
        if (onComplete) onComplete(usedLLM);
      }
    },
    [sessionId, onComplete]
  );

  /**
   * 用历史 session 的消息列表替换当前 messages（切换 session 时调用）。
   */
  const setHistory = useCallback((msgs: ChatMessage[]) => {
    setMessages(msgs);
  }, []);

  /**
   * 清空 messages（新对话）。
   */
  const clear = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, loading, send, setHistory, clear };
}
