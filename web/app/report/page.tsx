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
import {
  ArrowLeft,
  Sparkles,
  Copy,
  Download,
  ArrowUpCircle,
  Check,
  Edit3,
  Eye,
  Filter,
  Calendar,
  AlertCircle,
} from "lucide-react";
import { api, type Achievement, type CVStatus } from "@/lib/api";
import { TIME_RANGES, TEMPLATES, generateReport, type TemplateKind } from "@/lib/templates";

export default function ReportPage() {
  // 顶部选择
  const [rangeKey, setRangeKey] = useState(TIME_RANGES[0].key);
  const [templateKey, setTemplateKey] = useState<TemplateKind>("product_weekly");

  const range = useMemo(
    () => TIME_RANGES.find((r) => r.key === rangeKey) || TIME_RANGES[0],
    [rangeKey]
  );
  const template = useMemo(
    () => TEMPLATES.find((t) => t.key === templateKey) || TEMPLATES[0],
    [templateKey]
  );

  // 拉这段时间内所有成就（含 needs_data / pending, 述职模板会自动过滤 ready）
  const { data: items, mutate } = useSWR<Achievement[]>(
    ["/api/achievements", range.since()],
    () => api.listAchievements({ since: range.since() })
  );

  // 升级 needs_data/pending → ready
  const upgrade = async (a: Achievement) => {
    await api.updateAchievement(a.id, { cv_status: "ready" });
    mutate();
  };

  // 生成报告
  const report = useMemo(() => {
    if (!items) return null;
    return generateReport(items, range, template);
  }, [items, range, template]);

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
  const pendingItems = (items || []).filter(
    (a) => a.cv_status !== "ready"
  );
  const needsDataItems = pendingItems.filter(
    (a) => a.cv_status === "needs_data"
  );
  const pendingOnly = pendingItems.filter(
    (a) => a.cv_status === "pending"
  );

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
              <div className="text-[12px] text-fg-muted mt-0.5">
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

        {/* 时间范围 + 模板选择 */}
        <div className="rounded-lg border border-border bg-bg-secondary p-4 mb-4">
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
                    className={`px-3 py-1.5 rounded text-[12px] transition ${
                      r.key === rangeKey
                        ? "bg-accent/15 text-accent border border-accent/40"
                        : "bg-bg border border-border text-fg-secondary hover:text-fg hover:border-border-hover"
                    }`}
                    title={r.description}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
              <div className="text-[11px] text-fg-muted mt-1.5">
                {range.since()} ~ {range.until()} · {range.description}
              </div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.1em] text-fg-muted font-semibold mb-2">
                模板
              </div>
              <div className="flex gap-1.5 flex-wrap">
                {TEMPLATES.map((t) => (
                  <button
                    key={t.key}
                    onClick={() => setTemplateKey(t.key)}
                    className={`px-3 py-1.5 rounded text-[12px] transition ${
                      t.key === templateKey
                        ? "bg-accent/15 text-accent border border-accent/40"
                        : "bg-bg border border-border text-fg-secondary hover:text-fg hover:border-border-hover"
                    }`}
                    title={t.description}
                  >
                    {t.emoji} {t.label}
                  </button>
                ))}
              </div>
              <div className="text-[11px] text-fg-muted mt-1.5">
                {template.description}
              </div>
            </div>
          </div>
        </div>

        {/* 主体两栏 */}
        <div className="grid grid-cols-12 gap-4">
          {/* 左侧 40%: 待补成就 + 升级入口 */}
          <div className="col-span-5 space-y-3">
            <PendingCard
              title="📊 还差数据"
              hint="cv 已写但承认不全 — 写述职前一键升级"
              items={needsDataItems}
              onUpgrade={upgrade}
              emptyText="没有还差数据的成就 ✨"
              accent="warning"
            />
            <PendingCard
              title="⏳ 草稿"
              hint="当时没写完 — 建议先补 cv 再升 ready"
              items={pendingOnly}
              onUpgrade={upgrade}
              emptyText="没有草稿项"
              accent="muted"
            />
            {/* 报告内数据统计 */}
            {report && (
              <div className="rounded-lg border border-border bg-bg-secondary p-3 text-[12px] text-fg-muted">
                <div className="flex items-center gap-2 mb-1">
                  <Filter size={11} />
                  <span className="font-semibold text-fg-secondary">本次报告</span>
                </div>
                <div>
                  使用 {report.usedAchievements.length} 条成就
                  {template.key === "review_quarterly" && (
                    <span className="ml-1">(述职只取 ready, 其他状态先升级)</span>
                  )}
                </div>
                {report.projectOrder.length > 0 && (
                  <div className="mt-1">
                    覆盖 {report.projectOrder.length} 个项目: {report.projectOrder.join("、")}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 右侧 60%: 报告预览 / 编辑 */}
          <div className="col-span-7">
            <div className="rounded-lg border border-border bg-bg-secondary overflow-hidden flex flex-col" style={{ minHeight: 480 }}>
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
                    className="text-[12px] px-2.5 py-1 rounded bg-accent text-black hover:bg-accent-hover transition flex items-center gap-1.5 disabled:opacity-40"
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
  onUpgrade,
  emptyText,
  accent,
}: {
  title: string;
  hint: string;
  items: Achievement[];
  onUpgrade: (a: Achievement) => void;
  emptyText: string;
  accent: "warning" | "muted";
}) {
  const ringColor = accent === "warning" ? "border-warning/30" : "border-border";
  const titleColor = accent === "warning" ? "text-warning" : "text-fg-secondary";
  return (
    <div className={`rounded-lg border ${ringColor} bg-bg-secondary p-3`}>
      <div className="flex items-center justify-between mb-2">
        <div className={`text-[13px] font-semibold ${titleColor} flex items-center gap-1.5`}>
          {title}
          <span className="text-[11px] text-fg-muted font-normal">
            {items.length}
          </span>
        </div>
      </div>
      <div className="text-[11px] text-fg-muted mb-2">{hint}</div>
      {items.length === 0 ? (
        <div className="text-[12px] text-fg-muted py-3 text-center">
          {emptyText}
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
                  <div className="text-[12px] text-fg truncate font-medium">
                    {a.title}
                  </div>
                  <div className="text-[11px] text-fg-muted mt-0.5 flex items-center gap-1.5">
                    <span className="truncate">{a.project}</span>
                    {a.cv_status === "needs_data" && (
                      <span className="text-warning flex-shrink-0">📊</span>
                    )}
                  </div>
                  {a.cv && (
                    <div className="text-[11px] text-fg-secondary mt-1 line-clamp-2">
                      {a.cv}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => onUpgrade(a)}
                  className="text-[10px] px-1.5 py-0.5 bg-success/10 text-success rounded hover:bg-success/20 transition flex items-center gap-0.5 flex-shrink-0 opacity-60 group-hover:opacity-100"
                  title="升级为 ready"
                >
                  <ArrowUpCircle size={10} />
                  升 ready
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
