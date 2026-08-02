"use client";

/**
 * FollowUpReminder — 顶栏"待补追问" 徽章 (2026-08-01 立)
 *
 * 拉 /api/reminders/pending, 显示 "待补追问 N", 点跳转 /achievements/follow-up。
 * - 没追问时徽章不显示 (total=0)
 * - 用 useSWR 30s 拉一次 (跟 llmStatus 一样)
 * - 严格 readonly: 只是提醒入口, 补全逻辑在 /achievements/follow-up 页
 *
 * 哲学: lesson #22 立 — "完成沉淀 LLM 追问 + 周月提醒" 的"提醒" 入口。
 * 提醒之后, 用户去 follow-up 页补全, 补全后 cv_status 自动升级 ready (后端
 * storage.answer_follow_ups)。
 */

import useSWR from "swr";
import Link from "next/link";
import { api, type Achievement } from "@/lib/api";
import { FileQuestion } from "lucide-react";

interface ReminderPayload {
  items: Achievement[];
  total: number;
}

export function FollowUpReminder() {
  const { data } = useSWR<ReminderPayload>(
    "/api/reminders/pending",
    () => api.listPendingFollowUps({ limit: 50 }) as Promise<ReminderPayload>,
    { refreshInterval: 30000 },
  );

  if (!data || data.total === 0) return null;

  return (
    <Link
      href="/achievements/follow-up"
      className="inline-flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded-full font-medium bg-warning/10 text-warning hover:bg-warning/20 transition"
      title={`有 ${data.total} 个成就待补追问 — 补全后 cv_status 自动升级 ready`}
    >
      <FileQuestion size={11} />
      待补追问 {data.total}
    </Link>
  );
}
