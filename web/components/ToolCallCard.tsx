"use client";

import { useState } from "react";
import { Wrench, Check, X, ChevronDown, ChevronUp, Loader2 } from "lucide-react";

/**
 * 工具调用卡片（流式 chat 用）。
 * 状态机：calling → done / error
 * 默认展开 args + result，让用户看到 AI 调了啥、返回了啥。
 * 用户可点击 header 折叠/展开。
 */
export type ToolCallState = {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  ok?: boolean;
  status: "calling" | "done" | "error";
};

export function ToolCallCard({ tc }: { tc: ToolCallState }) {
  const [expanded, setExpanded] = useState(true);

  // 状态徽标
  // 修于 2026-07-17: 加 whitespace-nowrap, 防止 header 被挤窄时"完成"被汉字逐字断行成两列
  let StatusBadge: React.ReactNode;
  if (tc.status === "calling") {
    StatusBadge = (
      <span className="ml-auto flex items-center gap-1 text-fg-muted text-[10px] whitespace-nowrap shrink-0">
        <Loader2 size={10} className="animate-spin" />
        调用中
      </span>
    );
  } else if (tc.status === "done") {
    StatusBadge = (
      <span className="ml-auto flex items-center gap-1 text-green-400 text-[10px] whitespace-nowrap shrink-0">
        <Check size={10} />
        完成
      </span>
    );
  } else {
    StatusBadge = (
      <span className="ml-auto flex items-center gap-1 text-red-400 text-[10px] whitespace-nowrap shrink-0">
        <X size={10} />
        失败
      </span>
    );
  }

  return (
    <div className="rounded-md border border-border bg-bg-tertiary text-xs overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-2.5 py-1.5 hover:bg-bg-secondary transition text-left"
      >
        <Wrench size={11} className="text-fg-muted shrink-0" />
        <span className="font-mono text-fg-secondary shrink-0">{tc.name}</span>
        {/* 摘要段 flex-1 min-w-0 吃掉中间所有空间, 给 StatusBadge 让位 */}
        <span className="text-fg-muted truncate text-[10px] flex-1 min-w-0">
          {summarizeArgs(tc.args)}
        </span>
        {StatusBadge}
        {expanded ? (
          <ChevronUp size={11} className="text-fg-muted shrink-0 ml-1" />
        ) : (
          <ChevronDown size={11} className="text-fg-muted shrink-0 ml-1" />
        )}
      </button>
      {expanded && (
        <div className="px-2.5 pb-2 space-y-1.5 border-t border-border/40 pt-1.5">
          <div>
            <div className="text-fg-muted text-[10px] mb-0.5">参数</div>
            <pre className="text-[11px] text-fg-secondary bg-bg/60 p-1.5 rounded overflow-x-auto whitespace-pre-wrap break-all">
              {formatJson(tc.args)}
            </pre>
          </div>
          {tc.result !== undefined && (
            <div>
              <div className="text-fg-muted text-[10px] mb-0.5">结果</div>
              <pre className="text-[11px] text-fg-secondary bg-bg/60 p-1.5 rounded overflow-x-auto max-h-40 overflow-y-auto whitespace-pre-wrap break-all">
                {prettyResult(tc.result)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function summarizeArgs(args: Record<string, unknown>): string {
  // 取前 2 个 key 拼成简短摘要
  const keys = Object.keys(args);
  if (keys.length === 0) return "()";
  const parts: string[] = [];
  for (const k of keys.slice(0, 2)) {
    const v = args[k];
    let s: string;
    if (typeof v === "string") s = v;
    else s = JSON.stringify(v);
    if (s.length > 24) s = s.slice(0, 22) + "…";
    parts.push(`${k}=${s}`);
  }
  if (keys.length > 2) parts.push("…");
  return "(" + parts.join(", ") + ")";
}

function formatJson(args: Record<string, unknown>): string {
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
}

function prettyResult(raw: string): string {
  // 后端 tool 结果是 JSON 字符串，尝试 pretty print
  if (!raw) return "";
  try {
    const parsed = JSON.parse(raw);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return raw;
  }
}
