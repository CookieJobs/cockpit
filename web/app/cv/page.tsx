"use client";

/**
 * /cv — 跨项目 CV 视图 (2026-08-02 v0.4.2 立)
 *
 * 跟 /pr 区别:
 * - /pr 是项目维度 (单 PR 描述, 调 LLM 生成 4 段 markdown)
 * - /cv 是时间维度 (跨项目, 按时间倒序, 纯结构化展示 + 导出)
 *
 * 跟 /achievements 区别:
 * - /achievements 按项目分组, 看的是"我在哪些项目上有沉淀"
 * - /cv 按时间倒序, 看的是"我所有 ready 成就拉成一份简历" — 跨项目全局视图
 *
 * 跟 /report 区别:
 * - /report 是时间窗口过滤 (周/季度) + LLM 套模板
 * - /cv 是全量 ready 成就 + 纯 markdown 拼装 (不调 LLM)
 *
 * 哲学兑现 (GOAL.md 核心):
 *   一次沉淀 (成就库) → 多次输出 (CV / 周报 / 月报 / 年终 / PR 描述)
 *   /cv 是 v0.7 统一输出引擎的"基础版" — 只展示 + 导出, 不调 LLM
 *   v0.7 会复用 /cv 的数据流, 加 LLM 润色 + 多模板切换
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  ArrowLeft,
  Copy,
  Download,
  Check,
  Search,
  FileText,
  Calendar,
  Sparkles,
} from "lucide-react";
import { api, type Achievement, projectEmoji } from "@/lib/api";
import { generateCvMarkdown, type CvRangePreset } from "@/lib/cv-template";

export default function CvPage() {
  // ===== 拉 ready 成就 (跟 /pr 一样的端点) =====
  const { data: items, isLoading } = useSWR<Achievement[]>(
    "/api/achievements?cv_status=ready",
    () => api.listAchievements({ cv_status: "ready" }) as Promise<Achievement[]>,
    { refreshInterval: 60000 },
  );

  // ===== 状态 =====
  // 时间范围预设 (近 1 年 / 近 2 年 / 近 3 年 / 全部)
  const [rangePreset, setRangePreset] = useState<CvRangePreset>("all");
  // 搜索框 (匹配 title / project / cv 文本)
  const [search, setSearch] = useState("");
  // 复制反馈
  const [copied, setCopied] = useState(false);

  // ===== 过滤 =====
  const filtered = useMemo(() => {
    if (!items) return [];
    const since = (() => {
      if (rangePreset === "all") return null;
      const d = new Date();
      d.setFullYear(d.getFullYear() - Number(rangePreset.replace("y", "")));
      // 走本地时区 (lesson #19 — parseLocalDate 思路)
      d.setHours(0, 0, 0, 0);
      // 返 YYYY-MM-DD 字符串
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return `${y}-${m}-${day}`;
    })();
    const q = search.trim().toLowerCase();
    return items.filter((a) => {
      // 时间过滤
      if (since && a.date < since) return false;
      // 搜索匹配
      if (q) {
        const hay = `${a.title} ${a.project} ${a.cv}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [items, rangePreset, search]);

  // ===== 生成 markdown (用 lib/cv-template 复用) =====
  const markdown = useMemo(
    () => (filtered.length > 0 ? generateCvMarkdown(filtered) : ""),
    [filtered],
  );

  // ===== 复制 / 下载 =====
  const copy = async () => {
    if (!markdown) return;
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const download = () => {
    if (!markdown) return;
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cockpit-cv-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // 统计
  const totalReady = items?.length ?? 0;
  const showing = filtered.length;

  return (
    <div className="min-h-screen bg-bg text-fg">
      <div className="max-w-5xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-fg-muted hover:text-fg transition"
            >
              <ArrowLeft size={18} />
            </Link>
            <div className="flex items-center gap-2">
              <FileText size={18} className="text-accent" />
              <h1 className="text-[18px] font-semibold">跨项目 CV 视图</h1>
              <span className="text-[11px] text-fg-muted ml-1">
                v0.4.2 · 一次沉淀, 多次输出
              </span>
            </div>
          </div>
        </div>

        {/* 顶部: 范围预设 + 搜索 + 操作 */}
        <div className="bg-bg-secondary border border-border rounded-xl p-4 mb-4">
          <div className="flex flex-wrap items-center gap-3">
            {/* 范围预设 */}
            <div className="flex items-center gap-1.5 text-[12px] text-fg-muted">
              <Calendar size={12} />
              <span>范围</span>
            </div>
            {[
              { key: "1y", label: "近 1 年" },
              { key: "2y", label: "近 2 年" },
              { key: "3y", label: "近 3 年" },
              { key: "all", label: "全部" },
            ].map((opt) => (
              <button
                key={opt.key}
                type="button"
                onClick={() => setRangePreset(opt.key as CvRangePreset)}
                className={
                  "text-[11.5px] px-2.5 py-1 rounded transition " +
                  (rangePreset === opt.key
                    ? "bg-accent/15 text-accent border border-accent/30"
                    : "text-fg-muted hover:text-fg border border-transparent hover:bg-bg-tertiary")
                }
              >
                {opt.label}
              </button>
            ))}

            <div className="flex-1" />

            {/* 搜索 */}
            <div className="relative">
              <Search
                size={12}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-muted"
              />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索 title / project / cv 文本..."
                className="text-[12px] bg-bg border border-border rounded pl-7 pr-2 py-1 w-64 focus:outline-none focus:border-accent"
              />
            </div>

            {/* 复制 / 下载 */}
            <button
              type="button"
              onClick={copy}
              disabled={!markdown}
              className="text-[12px] px-2.5 py-1 rounded bg-accent/15 text-accent hover:bg-accent/25 disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-1"
              title="复制 markdown 到剪贴板"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? "已复制" : "复制"}
            </button>
            <button
              type="button"
              onClick={download}
              disabled={!markdown}
              className="text-[12px] px-2.5 py-1 rounded border border-border text-fg-secondary hover:text-fg hover:bg-bg-tertiary disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-1"
              title="下载为 .md 文件"
            >
              <Download size={12} />
              下载
            </button>
          </div>

          {/* 计数 */}
          <div className="mt-2.5 text-[11px] text-fg-muted flex items-center gap-3">
            <span>
              累计 ready: <span className="text-fg-secondary font-medium">{totalReady}</span>
            </span>
            <span>·</span>
            <span>
              当前展示: <span className="text-fg-secondary font-medium">{showing}</span>
            </span>
            {search && (
              <>
                <span>·</span>
                <span>
                  搜索: <span className="text-fg-secondary">"{search}"</span>
                </span>
              </>
            )}
          </div>
        </div>

        {/* 双栏: 左侧成就列表 / 右侧 markdown 预览 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* 左: 成就列表 (按时间倒序) */}
          <div className="bg-bg-secondary border border-border rounded-xl p-4">
            <div className="text-[12px] text-fg-muted font-medium mb-2.5 flex items-center gap-1.5">
              <Sparkles size={12} className="text-accent" />
              成就列表（按时间倒序）
            </div>
            {isLoading ? (
              <div className="text-[12px] text-fg-muted py-8 text-center">加载中...</div>
            ) : filtered.length === 0 ? (
              <div className="text-[12px] text-fg-muted py-8 text-center space-y-2">
                <div className="text-[20px]">📄</div>
                <div>
                  {totalReady === 0
                    ? "还没有 ready 成就 — 完成任务时把 cv_status 升级到 ready 吧"
                    : "当前过滤下没有匹配成就, 试试放宽范围或搜索词"}
                </div>
              </div>
            ) : (
              <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
                {filtered.map((a) => (
                  <div
                    key={a.id}
                    className="rounded-md border border-border bg-bg p-3 hover:border-accent/40 transition"
                  >
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <div className="flex items-center gap-1.5 min-w-0 flex-1">
                        <span className="text-[12px] flex-shrink-0 opacity-70">
                          {projectEmoji(a.project_id)}
                        </span>
                        <span className="text-[13px] font-medium text-fg truncate">
                          {a.title}
                        </span>
                      </div>
                      <span className="text-[10.5px] text-fg-muted flex-shrink-0 font-mono">
                        {a.date}
                      </span>
                    </div>
                    <div className="text-[11.5px] text-fg-muted mb-1.5 truncate">
                      {a.project}
                    </div>
                    <div className="text-[12.5px] text-fg-secondary leading-relaxed">
                      {a.cv}
                    </div>
                    {a.tags.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {a.tags.map((t) => (
                          <span
                            key={t}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-bg-tertiary text-fg-muted"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 右: markdown 预览 */}
          <div className="bg-bg-secondary border border-border rounded-xl p-4">
            <div className="text-[12px] text-fg-muted font-medium mb-2.5 flex items-center gap-1.5">
              <FileText size={12} className="text-accent" />
              Markdown 预览
            </div>
            {markdown ? (
              <pre className="text-[11.5px] text-fg-secondary font-mono whitespace-pre-wrap break-words leading-relaxed max-h-[70vh] overflow-y-auto pr-1">
                {markdown}
              </pre>
            ) : (
              <div className="text-[12px] text-fg-muted py-8 text-center">
                无内容预览
              </div>
            )}
          </div>
        </div>

        {/* 底部提示: v0.4.2 是基础版, v0.7 升级 */}
        <div className="mt-4 text-[11px] text-fg-muted/80 text-center">
          v0.4.2 基础版 · 纯结构化导出, 不调 LLM · v0.7 统一输出引擎会加 LLM 润色
        </div>
      </div>
    </div>
  );
}
