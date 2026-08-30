"use client";

/**
 * /report — 周报/述职 workspace（2026-07-20 立）。
 *
 * 设计目标（参考 PRD 场景 4-5）：
 * - 5 分钟搞定周报/述职, 不是 30 分钟翻成就库
 * - 时间范围 + 模板选好, 立刻出 markdown
 * - 升级入口放在左侧, 一键把 needs_data/pending 升 ready
 * - 编辑模式: v1 用 textarea 全局编辑（v2 升级到 chip 级别）
 * - 输出: 复制 markdown / 下载 .md
 *
 * 不调 LLM (v1):
 * - 模板结构在前端 lib/templates.ts 定义
 * - 用户拿到骨架后手动补血肉（业务决策、对比、影响数字等）
 * - v2 LLM 润色: 用户改完文本后点"AI 润色" → 调 chat_engine 提建议
 */

import { useState, useMemo, useRef } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Sparkles,
  Copy,
  Download,
  Check,
  Edit3,
  Eye,
  Filter,
  Calendar,
  AlertCircle,
} from "lucide-react";
import { api, type Achievement, type OutputType } from "@/lib/api";
import { TIME_RANGES } from "@/lib/templates";
import { getVisualTone } from "@/lib/visual-system";
import { DataState } from "@/components/DataState";

const OUTPUT_TYPES: OutputType[] = ["weekly", "monthly", "review", "cv"];
const OUTPUT_META: Record<OutputType, { label: string; emoji: string; description: string }> = {
  weekly: { label: "周报", emoji: "📊", description: "已完成、风险/阻塞与下周计划" },
  monthly: { label: "月度总结", emoji: "🗓️", description: "关键成果、项目进展、问题与下月重点" },
  review: { label: "述职材料", emoji: "🏆", description: "核心成果、行动、证据与复盘" },
  cv: { label: "CV", emoji: "📄", description: "按项目归纳全部可直接使用的成果" },
};

export default function ReportPage() {
  const searchParams = useSearchParams();
  // Query parameters make the former /cv route a compatibility redirect, while
  // normal report visits retain their existing weekly-product defaults.
  const requestedRange = searchParams.get("range");
  const requestedType = searchParams.get("type");
  const [rangeKey, setRangeKey] = useState(() =>
    TIME_RANGES.some((range) => range.key === requestedRange) ? requestedRange! : "this_week"
  );
  const [templateKey, setTemplateKey] = useState<OutputType>(() =>
    OUTPUT_TYPES.includes(requestedType as OutputType)
      ? requestedType as OutputType
      : "weekly"
  );

  const range = useMemo(
    () => TIME_RANGES.find((r) => r.key === rangeKey) || TIME_RANGES[1],
    [rangeKey]
  );
  const template = OUTPUT_META[templateKey];
  // Formal markdown is composed server-side through the shared ready-only boundary.
  const { data: report, error: reportError, isLoading: reportLoading, mutate: refreshReport } = useSWR(
    ["/api/outputs/compose", templateKey, range.since(), range.until()],
    () => api.composeOutput({ type: templateKey, since: range.since(), until: range.until() })
  );
  const { data: recoveryItems, error: recoveryError, isLoading: recoveryLoading, mutate: refreshRecovery } = useSWR<Achievement[]>(
    ["/api/achievements", range.since(), "recovery"],
    () => api.listAchievements({ since: range.since() })
  );

  // 编辑模式
  const [editing, setEditing] = useState(false);
  const [editedMarkdown, setEditedMarkdown] = useState("");
  const displayMarkdown =
    editing ? editedMarkdown : report?.markdown || "";

  // 复制 / 下载
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(displayMarkdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const downloadMd = () => {
    const filename = `${template.label}-${range.since()}_${range.until()}.md`;
    const blob = new Blob([displayMarkdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  // 待补成就（左侧升级区）— 选中的时间范围内, 状态非 ready 的
  const pendingItems = (recoveryItems || []).filter(
    (a) => a.cv_status !== "ready"
  );
  const needsDataItems = pendingItems.filter(
    (a) => a.cv_status === "needs_data"
  );
  const pendingOnly = pendingItems.filter(
    (a) => a.cv_status === "pending"
  );

  // v0.3.2 立: 拉 follow-up 追问待补条目 (跨时间范围, 写周报时主动调出).
  // 跟 /api/reminders/pending 同源 — 跟主页 FollowUpReminder 共享.
  // 跟 pendingItems 区别: pendingItems 包含所有非 ready (含 pending);
  // 追问待补只含"有 follow_up_questions 且 cv_status != ready" 的.
  const { data: followUps } = useSWR<{ items: Achievement[]; total: number }>(
    "/api/reminders/pending",
    () => api.listPendingFollowUps({ limit: 10 }),
    { refreshInterval: 60000 },
  );

  if (reportLoading || recoveryLoading || reportError || recoveryError) {
    return <DataState loading={reportLoading || recoveryLoading} error={reportError || recoveryError} onRetry={() => { refreshReport(); refreshRecovery(); }} />;
  }

  return (
    <div className="min-h-screen bg-bg text-fg">
      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-fg-muted hover:text-fg transition"
            >
              <ArrowLeft size={18} />
            </Link>
            <div>
              <h1 className="text-[20px] font-semibold flex items-center gap-2">
                <Sparkles size={16} className="text-accent" />
                周报/述职 workspace
              </h1>
              <div className="text-[13px] text-fg-muted mt-0.5">
                5 分钟搞定, 不是 30 分钟翻成就库
              </div>
            </div>
          </div>
          <Link
            href="/achievements"
            className="text-[12px] text-fg-muted hover:text-fg transition flex items-center gap-1.5"
          >
            <Calendar size={12} />
            成就库
          </Link>
        </div>

        {/* v0.3.2 立: 补全追问 section — 写周报时主动调出"还有 N 条待补追问" */}
        {followUps && followUps.total > 0 && (
          <div className="rounded-lg border border-info/30 bg-info/5 p-3.5 mb-4">
            <div className="flex items-center justify-between mb-2.5">
              <div className="flex items-center gap-1.5 text-[13px] font-medium text-info">
                <AlertCircle size={13} />
                还有 {followUps.total} 条成就在等你补全追问
                <span className="text-[10.5px] text-fg-muted font-normal ml-1">· 写周报前补完, cv 立刻 ready</span>
              </div>
              <Link
                href="/achievements/follow-up"
                className="text-[11.5px] text-info hover:text-info/80 transition flex items-center gap-1"
              >
                <Sparkles size={11} />
                一键去补全
              </Link>
            </div>
            <div className="space-y-1.5 max-h-[140px] overflow-y-auto pr-1">
              {followUps.items.map((a) => (
                <Link
                  key={a.id}
                  href={`/achievements/follow-up?focus=${a.id}`}
                  className="flex items-start gap-2 rounded-md bg-bg/60 border border-border/50 px-2.5 py-2 hover:border-info/40 hover:bg-info/10 transition"
                >
                  <span className="text-[10.5px] text-fg-muted font-mono flex-shrink-0 mt-0.5">
                    {a.date}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] text-fg-secondary truncate">
                      {a.title}
                    </div>
                    {a.follow_up_questions.length > 0 && (
                      <div className="text-[10.5px] text-fg-muted mt-0.5 truncate">
                        💬 {a.follow_up_questions[0]}
                        {a.follow_up_questions.length > 1 && ` 等 ${a.follow_up_questions.length} 个追问`}
                      </div>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* 时间范围 + 模板选择 — 2026-08-23 v2 改: 玻璃卡 */}
        <div className="glass rounded-glass p-4 mb-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.1em] text-fg-muted font-semibold mb-2">
                时间范围
              </div>
              <div className="flex gap-1.5 flex-wrap">
                {TIME_RANGES.map((r) => (
                  <button
                    key={r.key}
                    onClick={() => setRangeKey(r.key)}
                    className={`px-3 py-1.5 rounded text-[13px] transition ${
                      r.key === rangeKey
                        ? "bg-accent/10 text-accent border border-accent/40"
                        : "bg-bg border border-border text-fg-secondary hover:text-fg hover:border-border-hover"
                    }`}
                    title={r.description}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
              <div className="text-[13px] text-fg-muted mt-1.5">
                {range.since()} ~ {range.until()} · {range.description}
              </div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.1em] text-fg-muted font-semibold mb-2">
                模板
              </div>
              <div className="flex gap-1.5 flex-wrap">
                {OUTPUT_TYPES.map((outputType) => {
                  const t = OUTPUT_META[outputType];
                  return (
                  <button
                    key={outputType}
                    onClick={() => setTemplateKey(outputType)}
                    className={`px-3 py-1.5 rounded text-[13px] transition ${
                      outputType === templateKey
                        ? "bg-accent/10 text-accent border border-accent/40"
                        : "bg-bg border border-border text-fg-secondary hover:text-fg hover:border-border-hover"
                    }`}
                    title={t.description}
                  >
                    {t.emoji} {t.label}
                  </button>
                  );
                })}
              </div>
              <div className="text-[13px] text-fg-muted mt-1.5">
                {template.description}
              </div>
            </div>
          </div>
        </div>

        {/* 主体两栏 */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
          {/* 左侧 40%: 待补成就 + 升级入口 */}
          <div className="col-span-1 space-y-3 md:col-span-5">
            <PendingCard
              title="📊 还差数据"
              hint="cv 已写但证据不全 — 补充数据后才会进入报告"
              items={needsDataItems}
              emptyText="没有还差数据的成就 ✨"
              accent="warning"
            />
            <PendingCard
              title="⏳ 草稿"
              hint="当时没写完 — 先补全再进入报告"
              items={pendingOnly}
              emptyText="没有草稿项"
              accent="muted"
            />
            {/* 报告内数据统计 */}
            {report && (
              <div className="glass rounded-glass p-3 text-[13px] text-fg-muted">
                <div className="flex items-center gap-2 mb-1">
                  <Filter size={11} />
                  <span className="font-semibold text-fg-secondary">本次报告</span>
                </div>
                <div>
                  使用 <span data-testid="report-value-count" className="font-semibold tabular-nums text-asset">{report.ready_achievement_count}</span> 条成就
                  {templateKey === "review" && (
                    <span className="ml-1">(述职只取 ready, 其他状态先升级)</span>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 右侧 60%: 报告预览 / 编辑 */}
          <div className="col-span-1 md:col-span-7">
            <div className="glass rounded-glass overflow-hidden flex flex-col" style={{ minHeight: 480 }}>
              {/* 工具条 */}
              <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-bg-tertiary/30">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      if (editing) {
                        // 退出编辑模式 — 保留改动（不重置, 用户可继续点编辑切回）
                      }
                      setEditing(!editing);
                    }}
                    className="text-[12px] px-2 py-1 rounded text-fg-muted hover:text-fg hover:bg-bg-tertiary transition flex items-center gap-1.5"
                    title="切换预览/编辑"
                  >
                    {editing ? <Eye size={12} /> : <Edit3 size={12} />}
                    {editing ? "预览" : "编辑"}
                  </button>
                  {editing && (
                    <span className="text-[11px] text-fg-muted">
                      改完点"预览"切回查看
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={copy}
                    disabled={!displayMarkdown}
                    className="text-[12px] px-2.5 py-1 rounded bg-bg hover:bg-bg-tertiary text-fg-secondary hover:text-fg transition flex items-center gap-1.5 disabled:opacity-40"
                  >
                    {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
                    {copied ? "已复制" : "复制"}
                  </button>
                  <button
                    onClick={downloadMd}
                    disabled={!displayMarkdown}
                    className="text-[12px] px-2.5 py-1 rounded bg-accent text-bg hover:bg-accent-hover transition flex items-center gap-1.5 disabled:opacity-40"
                  >
                    <Download size={12} />
                    下载 .md
                  </button>
                </div>
              </div>

              {/* 报告内容 */}
              {editing ? (
                <textarea
                  value={editedMarkdown}
                  onChange={(e) => setEditedMarkdown(e.target.value)}
                  onFocus={() => {
                    // 第一次进入编辑模式时, 同步当前 markdown
                    if (!editedMarkdown && report) setEditedMarkdown(report.markdown);
                  }}
                  className="flex-1 w-full bg-bg-secondary p-4 text-[13px] text-fg font-mono leading-relaxed resize-none focus:outline-none border-0"
                  placeholder="选择时间范围和模板后, 这里会生成报告"
                />
              ) : (
                <pre className="flex-1 p-4 text-[13px] text-fg-secondary font-mono leading-relaxed whitespace-pre-wrap overflow-auto">
                  {displayMarkdown || (
                    <span className="text-fg-muted">
                      选择时间范围和模板, 这里会生成报告。
                      {"\n\n"}提示:
                      {"\n"}· 述职材料只用 ready 成就 — 左侧先升级
                      {"\n"}· 模板只能改结构, 血肉得自己加（业务决策/对比/影响数字）
                    </span>
                  )}
                </pre>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PendingCard({
  title,
  hint,
  items,
  emptyText,
  accent,
}: {
  title: string;
  hint: string;
  items: Achievement[];
  emptyText: string;
  accent: "warning" | "muted";
}) {
  const roleTreatment = accent === "warning" ? getVisualTone("warning") : "border border-border text-fg-secondary";
  return (
    <div className={`rounded-lg ${roleTreatment} ${accent === "muted" ? "bg-bg-secondary" : ""} p-3`}>
      <div className="flex items-center justify-between mb-2">
        <div className="text-[13px] font-semibold flex items-center gap-1.5">
          {title}
          <span className="text-[11px] text-fg-muted font-normal">
            {items.length}
          </span>
        </div>
      </div>
      <div className="text-[13px] text-fg-muted mb-2">{hint}</div>
      {items.length === 0 ? (
        <div data-testid="report-recovery-summary" className="rounded-md border border-border/70 bg-bg px-3 py-2.5 text-[13px] text-fg-muted">
          {emptyText} <span className="text-fg-secondary">现在可以直接专注于报告内容。</span>
        </div>
      ) : (
        <div className="space-y-1.5 max-h-[260px] overflow-y-auto">
          {items.map((a) => (
            <div
              key={a.id}
              className="rounded border border-border/60 bg-bg-tertiary/30 px-2.5 py-2 group"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] text-fg truncate font-medium">
                    {a.title}
                  </div>
                  <div className="text-[11px] text-fg-muted mt-0.5 flex items-center gap-1.5">
                    <span className="truncate">{a.project}</span>
                    {a.cv_status === "needs_data" && (
                      <span className="text-warning flex-shrink-0">📊</span>
                    )}
                  </div>
                  {a.cv && (
                    <div className="text-[13px] text-fg-secondary mt-1 line-clamp-2">
                      {a.cv}
                    </div>
                  )}
                </div>
                <Link
                  href={`/achievements/follow-up?focus=${a.id}`}
                  className="text-[10px] px-1.5 py-0.5 bg-info/10 text-info rounded hover:bg-info/20 transition flex-shrink-0"
                  title="补全证据"
                >
                  去补全
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
