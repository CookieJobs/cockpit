"use client";

/**
 * /today — 晨间 ritual 页面（2026-07-20 立）。
 *
 * 设计思路（参考 PRD 场景 3"问局势" + dogfooding 痛点）：
 * - 用户每天打开浏览器第一件事看这个页面, 不用打开 chat 问 LLM "我今天该干啥"
 * - 顶部大日期 + greeting（周末/工作日变体）
 * - 中间 focus 5（最高优先级 5 个 task, 一键完成/状态切换）
 * - 底部 done_today 折叠区（已完成列表, 沉淀成就感）
 *
 * 跟 MainBoard 区别: MainBoard 是全功能看板, /today 是"晨间 30 秒决策"页。
 * 状态变更/完成走 MainBoard 同样的 4 字段 modal。
 */

import { useState, useEffect } from "react";
import useSWR from "swr";
import Link from "next/link";
import {
  ArrowLeft,
  Sparkles,
  ChevronDown,
  CheckCircle2,
  Calendar,
  Flag,
  MessageSquare,
} from "lucide-react";
import { api, type Snapshot, dueColor, dueLabel, projectEmoji, type Task } from "@/lib/api";
import { CompleteTaskModal } from "@/components/CompleteTaskModal";

const WEEKDAY_LABEL = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

function getGreeting(now: Date): string {
  const h = now.getHours();
  if (h < 6) return "深夜了";
  if (h < 11) return "早上好";
  if (h < 14) return "中午好";
  if (h < 18) return "下午好";
  if (h < 22) return "晚上好";
  return "夜深了";
}

export default function TodayPage() {
  const { data: snapshot, mutate } = useSWR<Snapshot>(
    "/api/snapshot",
    () => api.getSnapshot()
  );
  const [now, setNow] = useState<Date | null>(null);
  const [doneExpanded, setDoneExpanded] = useState(true);
  const [completingTask, setCompletingTask] = useState<Pick<Task, "id" | "title"> | null>(null);

  // 客户端 mount 后再 setDate, 避免 hydration mismatch
  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(t);
  }, []);

  const focus = snapshot?.focus ?? [];
  const doneToday = snapshot?.done_today ?? [];
  const isWeekend = now ? [0, 6].includes(now.getDay()) : false;

  return (
    <div className="min-h-screen bg-bg text-fg">
      <div className="max-w-3xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <Link
            href="/"
            className="text-fg-muted hover:text-fg transition flex items-center gap-1.5 text-[13px]"
          >
            <ArrowLeft size={14} />
            回到看板
          </Link>
          <Link
            href="/report"
            className="text-fg-muted hover:text-accent transition flex items-center gap-1.5 text-[13px]"
            title="打开周报/述职 workspace"
          >
            <Sparkles size={14} />
            写周报
          </Link>
        </div>

        {/* 大日期 + greeting */}
        <div className="mb-8">
          {now && (
            <>
              <div className="text-[13px] text-fg-muted uppercase tracking-[0.1em] font-semibold mb-1">
                {getGreeting(now)}{isWeekend && " · 周末"}
              </div>
              <h1 className="text-[40px] font-bold text-fg leading-tight tabular-nums">
                {now.getMonth() + 1}月{now.getDate()}日
              </h1>
              <div className="text-[14px] text-fg-secondary mt-1">
                {WEEKDAY_LABEL[now.getDay()]} ·{" "}
                <span className="text-fg-muted">
                  {now.getFullYear()}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Focus 5 — 最高优先级 5 个 task */}
        <section className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[15px] font-semibold text-fg flex items-center gap-2">
              <Flag size={14} className="text-accent" />
              今天聚焦
              <span className="text-[12px] text-fg-muted font-normal">
                {focus.length} 项
              </span>
            </h2>
            <Link
              href="/"
              className="text-[12px] text-fg-muted hover:text-fg transition"
            >
              看板 →
            </Link>
          </div>

          {focus.length === 0 ? (
            <div className="rounded-lg border border-border bg-bg-secondary p-8 text-center text-fg-muted">
              <Sparkles size={24} className="mx-auto mb-2 text-accent opacity-60" />
              <div className="text-[14px] text-fg-secondary">
                {isWeekend ? "周末, 给自己放个假 ☕" : "今天没有待办 — 在看板里加一个开始吧"}
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {focus.map((f, i) => (
                <FocusRow
                  key={f.id}
                  rank={i + 1}
                  focus={f}
                  onComplete={() => setCompletingTask({ id: f.id, title: f.title })}
                />
              ))}
            </div>
          )}
        </section>

        {/* Done today — 折叠 */}
        {doneToday.length > 0 && (
          <section>
            <button
              onClick={() => setDoneExpanded((e) => !e)}
              className="w-full flex items-center justify-between text-left group"
            >
              <h2 className="text-[15px] font-semibold text-fg-secondary group-hover:text-fg transition flex items-center gap-2">
                <CheckCircle2 size={14} className="text-success" />
                今天已完成
                <span className="text-[12px] text-fg-muted font-normal">
                  {doneToday.length} 项
                </span>
              </h2>
              <ChevronDown
                size={14}
                className={`text-fg-muted transition-transform ${
                  doneExpanded ? "" : "-rotate-90"
                }`}
              />
            </button>
            {doneExpanded && (
              <div className="mt-3 space-y-1.5">
                {doneToday.map((a) => (
                  <div
                    key={a.id}
                    className="rounded-md border border-border/40 bg-bg-secondary/50 px-3 py-2 flex items-center gap-2"
                  >
                    <CheckCircle2 size={12} className="text-success flex-shrink-0" />
                    <span className="text-[13px] text-fg-secondary flex-1 truncate">
                      {a.cv || a.title}
                    </span>
                    <span className="text-[11px] text-fg-muted flex-shrink-0">
                      {projectEmoji(a.project_id)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Footer — 统计 + 入口 */}
        {snapshot && (
          <div className="mt-10 pt-6 border-t border-border/40 text-[12px] text-fg-muted flex items-center gap-4">
            <span>
              本期 <strong className="text-accent">{snapshot.counts.achievementsReady}</strong> 条 ready
            </span>
            {snapshot.counts.achievementsPending > 0 && (
              <span>
                · <strong className="text-warning">{snapshot.counts.achievementsPending}</strong> 条待补
              </span>
            )}
            <span className="ml-auto flex items-center gap-3">
              <Link
                href="/achievements"
                className="hover:text-fg transition flex items-center gap-1"
              >
                <Calendar size={11} />
                成就库
              </Link>
              <Link href="/" className="hover:text-fg transition flex items-center gap-1">
                <MessageSquare size={11} />
                看板
              </Link>
            </span>
          </div>
        )}
      </div>

      {/* 完成任务 4 字段 modal */}
      {completingTask && (
        <CompleteTaskModal
          task={completingTask}
          onClose={() => setCompletingTask(null)}
          onSave={async (data) => {
            await api.completeTask(completingTask.id, data);
            setCompletingTask(null);
            mutate();
          }}
        />
      )}
    </div>
  );
}

function FocusRow({
  rank,
  focus,
  onComplete,
}: {
  rank: number;
  focus: Snapshot["focus"][number];
  onComplete: () => void;
}) {
  const dueCls = dueColor(focus.due);
  const dueText = dueLabel(focus.due);

  return (
    <div className="group flex items-center gap-3 rounded-lg border border-border bg-bg-secondary hover:border-border-hover hover:bg-bg-tertiary/40 transition px-4 py-3">
      <div className="text-[14px] font-semibold text-fg-muted tabular-nums w-6 flex-shrink-0">
        #{rank}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span
            className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
              focus.priority === "高"
                ? "bg-danger"
                : focus.priority === "中"
                ? "bg-warning"
                : "bg-fg-secondary"
            }`}
          />
          <div className="text-[14px] text-fg truncate font-medium">
            {focus.title}
          </div>
        </div>
        <div className="text-[11px] text-fg-muted mt-0.5 flex items-center gap-2">
          {focus.due && (
            <span className={`text-${dueCls}`}>
              {dueText}
            </span>
          )}
          {focus.blocked && (
            <span className="text-warning">⚠ 被阻塞</span>
          )}
        </div>
      </div>
      <button
        onClick={onComplete}
        className="opacity-0 group-hover:opacity-100 transition px-3 py-1 text-[12px] text-fg-muted hover:text-accent rounded border border-border hover:border-accent"
        title="完成 + 沉淀成就"
      >
        完成 ✨
      </button>
    </div>
  );
}
