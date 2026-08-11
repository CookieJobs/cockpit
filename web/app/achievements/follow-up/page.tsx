"use client";

/**
 * /achievements/follow-up — 补全追问页 (2026-08-01 立)
 *
 * 设计思路（lesson #22 立）：
 * - 拉 /api/reminders/pending 拿待补追问的成就列表 (Achievement[], 跟 /api/achievements 同 schema)
 * - 每条成就展开 follow_up_questions 列表，每行一个 input
 * - 已答的 input 预填 (从 follow_up_answers 读)
 * - 保存调 api.answerFollowUps(id, answers) — 后端自动升级 cv_status=ready
 * - 答完的成就从列表移除 (mutate 重拉, 后端已 ready 不会再返)
 *
 * 跟 /achievements 区别:
 * - /achievements 是"看 + 编辑 cv" 的全量视图
 * - /follow-up 是"补全追问" 的专项入口 (从 FollowUpReminder 徽章跳过来)
 *
 * 哲学: "完成即沉淀" 哲学的兑现 (lesson #22)。polish 拿到的 follow_up_questions
 * 当时没补, 现在一次性补完 — 补全后 cv_status 升级 ready, 周报/述职/未来 PR 都能用。
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { ArrowLeft, Sparkles, Save, Loader2, CheckCircle2 } from "lucide-react";
import { api, type Achievement } from "@/lib/api";

export default function FollowUpPage() {
  const { data, mutate, isLoading } = useSWR<{ items: Achievement[]; total: number }>(
    "/api/reminders/pending",
    () => api.listPendingFollowUps({ limit: 50 }) as Promise<{ items: Achievement[]; total: number }>,
    { refreshInterval: 30000 },
  );

  // 每个成就的本地答案 (key: achievement_id, value: {q_idx: answer})
  const [drafts, setDrafts] = useState<Record<string, Record<string, string>>>({});
  // 保存中状态
  const [savingId, setSavingId] = useState<string | null>(null);
  // 保存完的 (id, 短暂显示 ✓ 后从列表移除)
  const [justSaved, setJustSaved] = useState<Set<string>>(new Set());

  // 初始化 drafts (用后端 answers 预填)
  useEffect(() => {
    if (!data?.items) return;
    const initial: Record<string, Record<string, string>> = {};
    for (const item of data.items) {
      initial[item.id] = { ...(item.follow_up_answers || {}) };
    }
    setDrafts(initial);
  }, [data?.items]);

  const items = data?.items ?? [];

  const setAnswer = (aid: string, qIdx: number, val: string) => {
    setDrafts((cur) => ({
      ...cur,
      [aid]: { ...(cur[aid] || {}), [String(qIdx)]: val },
    }));
  };

  const isAllAnswered = (item: Achievement) => {
    const draft = drafts[item.id] || {};
    return item.follow_up_questions.every((_, i) => (draft[String(i)] || "").trim().length > 0);
  };

  // 算 days_since_complete (Achievement 没这字段, 前端从 date 算)
  const daysSince = (dateStr: string) => {
    const completed = new Date(dateStr);
    const today = new Date();
    return Math.floor((today.getTime() - completed.getTime()) / 86400000);
  };

  const save = async (item: Achievement) => {
    const draft = drafts[item.id] || {};
    // 只提交非空答案 (后端 answer_follow_ups 接受任意 dict, 跳过空答案避免污染)
    const cleanAnswers: Record<string, string> = {};
    for (const [k, v] of Object.entries(draft)) {
      if (v.trim()) cleanAnswers[k] = v.trim();
    }
    setSavingId(item.id);
    try {
      await api.answerFollowUps(item.id, cleanAnswers);
      setJustSaved((cur) => new Set(cur).add(item.id));
      // 1.5s 后从本地列表移除 (后端 cv_status 升级后, mutate 重拉就不会再返)
      setTimeout(() => {
        mutate();
        setJustSaved((cur) => {
          const next = new Set(cur);
          next.delete(item.id);
          return next;
        });
      }, 1500);
    } catch (err) {
      alert("保存失败: " + (err instanceof Error ? err.message : err));
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="min-h-screen bg-bg text-fg">
      <div className="max-w-3xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <Link
            href="/"
            className="text-fg-muted hover:text-fg transition flex items-center gap-1.5 text-[13px]"
          >
            <ArrowLeft size={14} />
            回到看板
          </Link>
          <Link
            href="/achievements"
            className="text-fg-muted hover:text-accent transition flex items-center gap-1.5 text-[13px]"
          >
            <Sparkles size={14} />
            成就库
          </Link>
        </div>

        {/* Title */}
        <div className="mb-6">
          <h1 className="text-[24px] font-bold text-fg leading-tight">
            📝 补全追问
          </h1>
          <div className="text-[14px] text-fg-secondary mt-1">
            {items.length > 0
              ? `共 ${items.length} 个成就待补追问 — 补全后 cv_status 自动升级 ready`
              : "目前没有待补追问的成就 🎉"}
          </div>
          <div className="text-[12px] text-fg-muted mt-2">
            完成时 LLM 主动追问的"数据支撑" (e.g. 上线后 DAU / 用户反馈) —
            现在补全, 未来写周报/述职直接用。
          </div>
        </div>

        {/* 列表 */}
        {isLoading ? (
          <div className="text-center text-fg-muted py-12">
            <Loader2 className="animate-spin mx-auto mb-2" size={20} />
            加载中…
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-border bg-bg-secondary p-8 text-center space-y-3">
            <div className="text-[28px]">✨</div>
            <div className="text-[15px] text-fg-secondary font-medium">
              没有待补追问
            </div>
            <div className="text-[13px] text-fg-muted">
              完成新任务时, LLM 会根据任务类型主动追问 1-3 个问题
              <br />
              (e.g. "上线后 DAU 涨了多少?" / "用户反馈如何?")
            </div>
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20 transition"
            >
              打开看板
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((item) => {
              const draft = drafts[item.id] || {};
              const allAnswered = isAllAnswered(item);
              const saved = justSaved.has(item.id);
              const days = daysSince(item.date);
              return (
                <div
                  key={item.id}
                  className={`rounded-lg border bg-bg-secondary p-4 space-y-3 transition ${
                    saved ? "border-success/40 bg-success/5" : "border-border"
                  }`}
                >
                  {/* 头部: 标题 + 项目 + 完成于 */}
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {saved ? (
                        <CheckCircle2 size={14} className="text-success flex-shrink-0" />
                      ) : (
                        <span className="text-[14px] flex-shrink-0">📝</span>
                      )}
                      <span
                        className={`text-[14px] font-semibold truncate ${
                          saved ? "text-success line-through" : "text-fg"
                        }`}
                      >
                        {item.title}
                      </span>
                    </div>
                    <div className="text-[11px] text-fg-muted mt-1 flex items-center gap-2 flex-wrap">
                      <span>{item.project}</span>
                      <span>·</span>
                      <span>完成于 {item.date}</span>
                      <span>·</span>
                      <span className="text-warning">
                        已 {days} 天
                      </span>
                    </div>
                  </div>

                  {/* questions 列表 */}
                  <div className="space-y-2.5 pl-1">
                    {item.follow_up_questions.map((q, i) => {
                      const ans = draft[String(i)] || "";
                      return (
                        <div key={i}>
                          <label className="text-[12px] text-fg-secondary block mb-1">
                            <span className="text-accent font-mono mr-1">Q{i + 1}.</span>
                            {q}
                          </label>
                          <input
                            type="text"
                            value={ans}
                            onChange={(e) => setAnswer(item.id, i, e.target.value)}
                            placeholder="补全答案…"
                            disabled={saved}
                            className="w-full bg-bg border border-border rounded px-2.5 py-1.5 text-[13px] text-fg placeholder:text-fg-muted focus:outline-none focus:border-accent disabled:opacity-50"
                          />
                        </div>
                      );
                    })}
                  </div>

                  {/* 保存按钮 */}
                  <div className="flex items-center justify-end gap-2 pt-1">
                    {saved ? (
                      <span className="text-[12px] text-success font-medium">
                        ✓ 已保存 — cv_status 升级 ready
                      </span>
                    ) : (
                      <button
                        onClick={() => save(item)}
                        disabled={!allAnswered || savingId === item.id}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium bg-accent text-bg hover:bg-accent-hover transition disabled:opacity-40 disabled:cursor-not-allowed"
                        title={allAnswered ? "保存并升级 cv_status" : "答完所有追问才能保存"}
                      >
                        {savingId === item.id ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Save size={12} />
                        )}
                        保存并升级 ready
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
