"use client";

/**
 * /pr — PR 描述生成页 (2026-08-01 立)
 *
 * 端到端流程 (lesson #11 "成就二次加工" 用户决策):
 * 1. 选项目 (snapshot.projects)
 * 2. 选 N 条 ready 成就 (勾选) — 预选: localStorage `cockpit_pr_candidates`
 * 3. 选模板 (PR_Feature / PR_Bugfix / PR_Refactor)
 * 4. 点"生成 PR 描述" → 调 LLM
 * 5. 右侧出 4 段 markdown (背景/改动/影响/测试)
 * 6. 复制 / 下载 .md
 *
 * 跟 /report 区别:
 * - /report 是时间维度 (周/季度)
 * - /pr 是项目维度 (单 PR)
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { ArrowLeft, Sparkles, Copy, Download, Loader2, CheckCircle2, FileCode } from "lucide-react";
import { api, type Achievement } from "@/lib/api";
import { PR_TEMPLATES, type PRTemplateKind, generatePr } from "@/lib/pr";

const PR_CANDIDATES_KEY = "cockpit_pr_candidates";

export default function PrPage() {
  // 拉 snapshot (项目列表 + ready 成就 — 走 /api/achievements 单独拉 ready 更精确)
  const { data: allAchievements } = useSWR<Achievement[]>(
    "/api/achievements?cv_status=ready",
    () => api.listAchievements({ cv_status: "ready" }) as Promise<Achievement[]>,
    { refreshInterval: 60000 },
  );

  // 选中的项目 id (前端快照里有 projects, 但 achievements 不带 project_id 排序, 用成就聚合)
  const projects = useMemo(() => {
    if (!allAchievements) return [];
    const seen = new Set<string>();
    const result: Array<{ id: string; name: string; achievements: Achievement[] }> = [];
    for (const a of allAchievements) {
      if (seen.has(a.project_id)) {
        const p = result.find((r) => r.id === a.project_id);
        if (p) p.achievements.push(a);
        continue;
      }
      seen.add(a.project_id);
      result.push({ id: a.project_id, name: a.project, achievements: [a] });
    }
    return result;
  }, [allAchievements]);

  // 选中项目 + 选中成就
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  // 模板
  const [templateKind, setTemplateKind] = useState<PRTemplateKind>("PR_Feature");
  // 生成中
  const [generating, setGenerating] = useState(false);
  // 生成结果
  const [markdown, setMarkdown] = useState<string>("");
  // 复制状态
  const [copied, setCopied] = useState(false);

  // 默认选第一个项目
  useEffect(() => {
    if (!selectedProjectId && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 加载预选 (localStorage 累积的 PR 候选)
  useEffect(() => {
    try {
      const raw = localStorage.getItem(PR_CANDIDATES_KEY);
      if (!raw) return;
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) setSelectedIds(new Set(arr.filter((x) => typeof x === "string")));
    } catch {
      /* 隐私模式 */
    }
  }, []);

  // 同步 selectedIds 到 localStorage (用户在 /achievements 勾选时也累积)
  useEffect(() => {
    try {
      localStorage.setItem(PR_CANDIDATES_KEY, JSON.stringify(Array.from(selectedIds)));
    } catch {
      /* 忽略 */
    }
  }, [selectedIds]);

  const selectedProject = projects.find((p) => p.id === selectedProjectId) || null;
  const selectedAchievements: Achievement[] = useMemo(
    () => selectedProject?.achievements.filter((a) => selectedIds.has(a.id)) ?? [],
    [selectedProject, selectedIds],
  );

  const toggleAch = (id: string) => {
    setSelectedIds((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const generate = async () => {
    if (selectedAchievements.length === 0 || !selectedProject) return;
    setGenerating(true);
    try {
      const res = await generatePr({
        project: selectedProject.name,
        achievements: selectedAchievements,
        templateKind,
      });
      setMarkdown(res.markdown);
    } catch (err) {
      alert("生成失败: " + (err instanceof Error ? err.message : err));
    } finally {
      setGenerating(false);
    }
  };

  const copy = async () => {
    if (!markdown) return;
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const download = () => {
    if (!markdown || !selectedProject) return;
    const filename = `PR-${selectedProject.name}-${Date.now()}.md`;
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-bg text-fg">
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <Link
            href="/"
            className="text-fg-muted hover:text-fg transition flex items-center gap-1.5 text-[13px]"
          >
            <ArrowLeft size={14} />
            回到看板
          </Link>
          <div className="text-fg-muted text-[12px] flex items-center gap-1.5">
            <FileCode size={14} />
            PR 描述生成
          </div>
        </div>

        {/* Title */}
        <div className="mb-6">
          <h1 className="text-[24px] font-bold text-fg leading-tight flex items-center gap-2">
            <Sparkles className="text-accent" size={22} />
            从成就生成 PR 描述
          </h1>
          <div className="text-[13px] text-fg-secondary mt-1">
            选项目 → 选 ready 成就 → 选模板 → 4 段 markdown 直接贴 GitHub PR
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 左: 选择区 */}
          <div className="space-y-4">
            {/* 项目选择 */}
            <div>
              <label className="text-[12px] font-semibold text-fg-muted uppercase tracking-wider block mb-2">
                1. 项目
              </label>
              {projects.length === 0 ? (
                <div className="text-[12px] text-fg-muted px-3 py-2 rounded border border-border">
                  还没有 ready 成就 — 先在看板完成任务
                </div>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {projects.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => setSelectedProjectId(p.id)}
                      className={`text-[12px] px-2.5 py-1.5 rounded transition ${
                        selectedProjectId === p.id
                          ? "bg-accent/15 text-accent border border-accent/30"
                          : "bg-bg-tertiary text-fg-secondary hover:text-fg border border-transparent"
                      }`}
                    >
                      {p.name} <span className="text-fg-muted ml-1">({p.achievements.length})</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* 成就选择 (checkbox) */}
            {selectedProject && (
              <div>
                <label className="text-[12px] font-semibold text-fg-muted uppercase tracking-wider block mb-2">
                  2. 选 ready 成就 ({selectedIds.size} 选中)
                </label>
                {selectedProject.achievements.length === 0 ? (
                  <div className="text-[12px] text-fg-muted px-3 py-2 rounded border border-border">
                    该项目还没有 ready 成就
                  </div>
                ) : (
                  <div className="space-y-1.5 max-h-[280px] overflow-y-auto pr-1">
                    {selectedProject.achievements.map((a) => (
                      <label
                        key={a.id}
                        className={`flex items-start gap-2 px-2.5 py-1.5 rounded border cursor-pointer transition ${
                          selectedIds.has(a.id)
                            ? "border-accent/40 bg-accent/5"
                            : "border-border bg-bg-secondary hover:border-border-hover"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedIds.has(a.id)}
                          onChange={() => toggleAch(a.id)}
                          className="mt-1 flex-shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-[13px] text-fg truncate">
                            {a.title}
                          </div>
                          {a.cv && (
                            <div className="text-[11px] text-fg-muted mt-0.5 line-clamp-1">
                              {a.cv}
                            </div>
                          )}
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 模板选择 */}
            <div>
              <label className="text-[12px] font-semibold text-fg-muted uppercase tracking-wider block mb-2">
                3. 模板
              </label>
              <div className="space-y-1.5">
                {PR_TEMPLATES.map((t) => (
                  <label
                    key={t.key}
                    className={`flex items-start gap-2 px-2.5 py-1.5 rounded border cursor-pointer transition ${
                      templateKind === t.key
                        ? "border-accent/40 bg-accent/5"
                        : "border-border bg-bg-secondary hover:border-border-hover"
                    }`}
                  >
                    <input
                      type="radio"
                      name="pr-template"
                      checked={templateKind === t.key}
                      onChange={() => setTemplateKind(t.key)}
                      className="mt-1 flex-shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-[13px] text-fg flex items-center gap-1.5">
                        <span>{t.emoji}</span>
                        {t.label}
                      </div>
                      <div className="text-[11px] text-fg-muted">{t.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* 生成按钮 */}
            <button
              onClick={generate}
              disabled={generating || selectedAchievements.length === 0}
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-md text-[13px] font-semibold bg-accent text-black hover:bg-accent-hover transition disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {generating ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  生成中…
                </>
              ) : (
                <>
                  <Sparkles size={14} />
                  生成 PR 描述
                </>
              )}
            </button>
          </div>

          {/* 右: 结果区 */}
          <div>
            <label className="text-[12px] font-semibold text-fg-muted uppercase tracking-wider block mb-2">
              4. PR 描述 (可编辑)
            </label>
            {markdown ? (
              <div className="space-y-2">
                {/* 复制 + 下载 */}
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={copy}
                    className="text-[12px] px-2.5 py-1 rounded bg-bg hover:bg-bg-tertiary text-fg-secondary hover:text-fg transition flex items-center gap-1.5"
                  >
                    {copied ? <CheckCircle2 size={11} className="text-success" /> : <Copy size={11} />}
                    {copied ? "已复制" : "复制"}
                  </button>
                  <button
                    onClick={download}
                    className="text-[12px] px-2.5 py-1 rounded bg-bg hover:bg-bg-tertiary text-fg-secondary hover:text-fg transition flex items-center gap-1.5"
                  >
                    <Download size={11} />
                    下载 .md
                  </button>
                </div>
                <textarea
                  value={markdown}
                  onChange={(e) => setMarkdown(e.target.value)}
                  className="w-full h-[500px] bg-bg-secondary border border-border rounded p-3 text-[12px] text-fg font-mono leading-relaxed resize-y focus:outline-none focus:border-accent"
                  placeholder="(生成结果会显示在这里, 可编辑)"
                />
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-border bg-bg-secondary/30 p-8 text-center text-fg-muted text-[13px] h-[500px] flex flex-col items-center justify-center">
                <FileCode size={28} className="opacity-40 mb-2" />
                选项目 + 成就 + 模板
                <br />
                点"生成 PR 描述" 拿 4 段 markdown
                <br />
                <span className="text-[11px] text-fg-muted/60 mt-3">
                  LLM 不可用时会自动用模板填空, 不阻塞
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
