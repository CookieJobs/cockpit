"use client";

/**
 * /achievements — 成就库 (2026-07-28 v2 立项目层级)。
 *
 * 旧版 (v1): 一级 = 按日期分组, 每个成就挂一个 project 徽章 — 项目维度看不见
 * 新版 (v2): 一级 = 按项目分组 (project card), 二级 = 按日期分组
 *   - 用户能一眼看清"我在哪些项目上有沉淀"
 *   - 复用 projectEmoji 跟 /today 风格一致
 *   - 跟 /today 项目的"已沉淀 N · 7 天内" 子区呼应, 但这里是全量视图
 *
 * 排序: 项目按 ready 数 desc (最近沉淀最多的项目最显眼)
 * 折叠: localStorage 持久化每个项目的展开/收起, 默认全部展开
 */
import useSWR from "swr";
import { api, type Achievement, type CVStatus, projectEmoji } from "@/lib/api";
import { computeStats, ratioToPct, gradeRatio, verbDistribution } from "@/lib/achievement-stats";
import {
  ArrowLeft,
  CheckCircle2,
  Circle,
  AlertCircle,
  Edit2,
  Undo2,
  Filter,
  ChevronDown,
  Archive,
  BarChart3,
  ListTree,
  Clock,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type StatusFilter = "all" | "needs_data" | "pending" | "ready";
// v0.4.1 立: 视图模式 — 按项目分组 vs 按时间倒序
type ViewMode = "project" | "timeline";

// 项目级聚合
interface ProjectGroup {
  project: string; // 项目名 (snapshot)
  project_id: string | null; // 一些成就是孤儿的 (project 被删了), id 为 null
  ready: number;
  pending: number;
  needs_data: number;
  total: number;
  items: Achievement[]; // 全部, 在内部再按日期分组
}

const COLLAPSED_KEY = "cockpit_achievements_collapsed_projects";
// v0.4.1 立: 视图模式持久化 key
const VIEW_MODE_KEY = "cockpit_achievements_view_mode";

export default function AchievementsPage() {
  const [filter, setFilter] = useState<StatusFilter>("all");
  // v0.4.1 立: 视图模式 (localStorage 持久化)
  const [viewMode, setViewMode] = useState<ViewMode>("project");
  useEffect(() => {
    try {
      const stored = localStorage.getItem(VIEW_MODE_KEY);
      if (stored === "project" || stored === "timeline") setViewMode(stored);
    } catch {
      /* ignore */
    }
  }, []);
  const updateViewMode = (m: ViewMode) => {
    setViewMode(m);
    try {
      localStorage.setItem(VIEW_MODE_KEY, m);
    } catch {
      /* ignore */
    }
  };
  const { data: items, mutate } = useSWR<Achievement[]>(
    ["/api/achievements", filter],
    () => (filter === "all" ? api.listAchievements() : api.listAchievements({ cv_status: filter as CVStatus }))
  );

  // 折叠状态 — 哪些 project 是收起的
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    try {
      const stored = localStorage.getItem(COLLAPSED_KEY);
      if (stored) setCollapsed(new Set(JSON.parse(stored)));
    } catch {
      /* ignore */
    }
  }, []);
  const toggleProject = (key: string) => {
    setCollapsed((cur) => {
      const next = new Set(cur);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      try {
        localStorage.setItem(COLLAPSED_KEY, JSON.stringify(Array.from(next)));
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  // ===== 按项目聚合 =====
  const projectGroups = useMemo<ProjectGroup[]>(() => {
    const map = new Map<string, ProjectGroup>();
    for (const a of items || []) {
      // group key: project name (id 可能为空, 用 name 作主键)
      const key = a.project || "(未命名项目)";
      let g = map.get(key);
      if (!g) {
        g = {
          project: a.project || "(未命名项目)",
          project_id: a.project_id || null,
          ready: 0,
          pending: 0,
          needs_data: 0,
          total: 0,
          items: [],
        };
        map.set(key, g);
      }
      g.items.push(a);
      g.total += 1;
      if (a.cv_status === "ready") g.ready += 1;
      else if (a.cv_status === "needs_data") g.needs_data += 1;
      else g.pending += 1;
    }
    // 排序: ready 数 desc, 然后 total desc, 然后 project 名 asc
    return Array.from(map.values()).sort((a, b) => {
      if (b.ready !== a.ready) return b.ready - a.ready;
      if (b.total !== a.total) return b.total - a.total;
      return a.project.localeCompare(b.project);
    });
  }, [items]);

  return (
    <div className="min-h-screen bg-bg text-fg">
      <div className="max-w-4xl mx-auto p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-fg-muted hover:text-fg transition"
            >
              <ArrowLeft size={18} />
            </Link>
            <h1 className="text-2xl font-semibold">成就库</h1>
            {/* 统计: 项目数 + 总数 */}
            <span className="text-sm text-fg-muted">
              {projectGroups.length} 个项目 · 共 {items?.length || 0} 项
            </span>
          </div>
        </div>

        {/* v0.3.5 立: 沉淀质量卡片 (顶部固定, 跨过滤态) — 3 个核心指标 + v0.4.3 动词分布展开 */}
        {items && items.length > 0 && (
          <div className="rounded-lg border border-border bg-bg-secondary px-4 py-3 mb-4">
            <div className="flex items-center gap-2 mb-2.5">
              <BarChart3 size={13} className="text-accent" />
              <span className="text-[12px] text-fg-secondary font-medium">沉淀质量</span>
              <span className="text-[10.5px] text-fg-muted/80">· v0.3.5 / v0.4.3</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {(() => {
                const stats = computeStats(items);
                return (
                  <>
                    <StatBar
                      label="ready 比例"
                      value={`${ratioToPct(stats.ready_ratio)}%`}
                      detail={`${stats.ready} / ${stats.total}`}
                      grade={gradeRatio(stats.ready_ratio)}
                    />
                    <StatBar
                      label="量化率"
                      value={`${ratioToPct(stats.quantify_ratio)}%`}
                      detail={`${stats.quantify_count} 条含量化`}
                      grade={gradeRatio(stats.quantify_ratio)}
                    />
                    <StatBar
                      label="强动词比例"
                      value={`${ratioToPct(stats.strong_verb_ratio)}%`}
                      detail={`${stats.strong_verb_count} 条以强动词开头`}
                      grade={gradeRatio(stats.strong_verb_ratio)}
                    />
                  </>
                );
              })()}
            </div>
            {/* v0.4.3 立: 动词分布展开 — 看到底是"主导"多还是"设计"多 */}
            {(() => {
              const dist = verbDistribution(items);
              if (dist.length === 0) return null;
              const maxCount = Math.max(...dist.map((d) => d.count), 1);
              return (
                <details className="mt-3 group">
                  <summary className="text-[11px] text-fg-muted hover:text-fg cursor-pointer flex items-center gap-1 select-none">
                    <ChevronDown
                      size={11}
                      className="transition-transform group-open:rotate-180"
                    />
                    动词分布 ({dist.length} 种, 共 {dist.reduce((s, d) => s + d.count, 0)} 条)
                  </summary>
                  <div className="mt-2.5 space-y-1.5">
                    {dist.map((d) => (
                      <div key={d.verb} className="flex items-center gap-2 text-[11.5px]">
                        <span className="text-fg-muted w-12 text-right font-mono flex-shrink-0">
                          {d.verb}
                        </span>
                        <div className="flex-1 h-3 bg-bg/50 rounded-sm overflow-hidden border border-border/40">
                          <div
                            className="h-full bg-accent/60 transition-all"
                            style={{ width: `${(d.count / maxCount) * 100}%` }}
                          />
                        </div>
                        <span className="text-fg-secondary font-mono flex-shrink-0 w-8 text-right">
                          {d.count}
                        </span>
                      </div>
                    ))}
                  </div>
                </details>
              );
            })()}
          </div>
        )}

        {/* v0.4.1 立: 视图模式 toggle (按项目 / 按时间) + 状态过滤 */}
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          {/* 视图模式 toggle */}
          <div className="flex items-center gap-1.5 text-sm">
            <span className="text-[11px] text-fg-muted mr-1">视图</span>
            {([
              { k: "project", label: "按项目", icon: ListTree },
              { k: "timeline", label: "按时间", icon: Clock },
            ] as { k: ViewMode; label: string; icon: typeof ListTree }[]).map((it) => (
              <button
                key={it.k}
                onClick={() => updateViewMode(it.k)}
                className={`text-[11.5px] px-2.5 py-1 rounded transition flex items-center gap-1 ${
                  viewMode === it.k
                    ? "bg-accent/15 text-accent border border-accent/30"
                    : "text-fg-muted hover:text-fg border border-transparent hover:bg-bg-tertiary"
                }`}
                title={
                  it.k === "project"
                    ? "按项目分组看, 适合『我在哪些项目上有沉淀』"
                    : "按时间倒序拉平, 适合『最近干了啥』"
                }
              >
                <it.icon size={11} />
                {it.label}
              </button>
            ))}
          </div>

          {/* 状态过滤 — 让 needs_data 中间态可被发现 + 批量升级 */}
          <div className="flex items-center gap-2 text-sm">
            <Filter size={14} className="text-fg-muted" />
            {([
              { k: "all", label: "全部" },
              { k: "needs_data", label: "📊 还差数据" },
              { k: "pending", label: "⏳ 草稿" },
              { k: "ready", label: "✅ ready" },
            ] as { k: StatusFilter; label: string }[]).map((it) => (
              <button
                key={it.k}
                onClick={() => setFilter(it.k)}
                className={`px-2.5 py-1 rounded text-[12px] transition ${
                  filter === it.k
                    ? "bg-accent/15 text-accent"
                    : "text-fg-muted hover:text-fg hover:bg-bg-tertiary"
                }`}
              >
                {it.label}
              </button>
            ))}
          </div>
        </div>

        {/* v0.4.1 立: 按时间倒序拉平视图 (跨项目) */}
        {viewMode === "timeline" && items && items.length > 0 && (
          <TimelineView items={items} mutate={mutate} />
        )}

        {projectGroups.length === 0 ? (
          <div className="rounded-lg border border-border bg-bg-secondary p-8 text-center space-y-3">
            <div className="text-[28px]">🎯</div>
            <div className="text-[15px] text-fg-secondary font-medium">
              还没有成就 — 完成第一个任务，自动沉淀到成就库
            </div>
            <div className="text-[13px] text-fg-muted">
              完成后弹窗会帮你把"动作"翻译成"成就陈述"，未来写周报/述职时直接取用
            </div>
            <div className="flex items-center justify-center gap-2 pt-1">
              <Link
                href="/"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20 transition"
              >
                打开看板
              </Link>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {projectGroups.map((g) => {
              const key = g.project;
              const isCollapsed = collapsed.has(key);
              return (
                <ProjectSection
                  key={key}
                  group={g}
                  collapsed={isCollapsed}
                  onToggle={() => toggleProject(key)}
                  onMutate={mutate}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ===== Project Section =====

function ProjectSection({
  group,
  collapsed,
  onToggle,
  onMutate,
}: {
  group: ProjectGroup;
  collapsed: boolean;
  onToggle: () => void;
  onMutate: () => void;
}) {
  // 按日期分组 (二级)
  const dateGroups: Record<string, Achievement[]> = {};
  for (const a of group.items) {
    dateGroups[a.date] = dateGroups[a.date] || [];
    dateGroups[a.date].push(a);
  }

  return (
    <div className="rounded-xl border border-border bg-bg-secondary overflow-hidden">
      {/* Header — 项目级别 */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-bg-tertiary/40 transition text-left"
      >
        <span className="text-[18px] flex-shrink-0">{projectEmoji(group.project_id || group.project)}</span>
        <span className="flex-1 min-w-0">
          <span className="font-semibold text-fg truncate block">{group.project}</span>
          <span className="text-[11px] text-fg-muted tabular-nums">
            {group.total} 项
            {group.ready > 0 && (
              <span className="text-success ml-1.5">✅ {group.ready}</span>
            )}
            {group.needs_data > 0 && (
              <span className="text-warning ml-1.5">📊 {group.needs_data}</span>
            )}
            {group.pending > 0 && (
              <span className="text-fg-muted ml-1.5">⏳ {group.pending}</span>
            )}
          </span>
        </span>
        <ChevronDown
          size={14}
          className={`text-fg-muted transition-transform flex-shrink-0 ${collapsed ? "" : "rotate-180"}`}
        />
      </button>

      {/* Body — 按日期分组的成就列表 (展开时) */}
      {!collapsed && (
        <div className="border-t border-border px-3 py-3 space-y-4">
          {Object.entries(dateGroups)
            .sort(([a], [b]) => b.localeCompare(a))
            .map(([date, list]) => (
              <div key={date}>
                <h2 className="text-[11px] font-semibold text-fg-muted uppercase tracking-[0.08em] mb-2 px-1">
                  {date}
                  <span className="ml-2 text-fg-secondary tabular-nums font-normal normal-case tracking-normal">
                    {list.length}
                  </span>
                </h2>
                <div className="space-y-2">
                  {list.map((a) => (
                    <AchievementItem key={a.id} a={a} onMutate={onMutate} />
                  ))}
                </div>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

// ===== Achievement Item =====

function AchievementItem({
  a,
  onMutate,
}: {
  a: Achievement;
  onMutate: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editCv, setEditCv] = useState("");

  const startEdit = () => {
    setEditCv(a.cv);
    setEditing(true);
  };
  const saveEdit = async () => {
    await api.updateAchievement(a.id, { cv: editCv });
    setEditing(false);
    onMutate();
  };
  const undo = async () => {
    if (!confirm("撤销这个成就？任务会恢复到进行中状态。")) return;
    await api.undoAchievement(a.id);
    onMutate();
  };

  return (
    <div className="rounded-lg border border-border bg-bg p-3 hover:border-border-hover transition">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            {a.cv_status === "ready" ? (
              <CheckCircle2 size={13} className="text-success flex-shrink-0" />
            ) : a.cv_status === "needs_data" ? (
              <AlertCircle size={13} className="text-warning flex-shrink-0" />
            ) : (
              <Circle size={13} className="text-fg-muted flex-shrink-0" />
            )}
            <h3 className="font-semibold text-fg text-[14px] truncate">{a.title}</h3>
            {a.cv_status === "needs_data" && (
              <Link
                href={`/achievements/follow-up?focus=${a.id}`}
                className="text-[10px] px-1.5 py-0.5 rounded bg-warning/15 text-warning font-medium"
                title="补全追问后会自动进入 ready"
              >
                📊 还差数据 · 去补全
              </Link>
            )}
            {a.cv_status === "pending" && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-fg-muted/15 text-fg-muted font-medium">
                ⏳ 草稿
              </span>
            )}
          </div>
          {editing ? (
            <div className="mt-2 space-y-2">
              <textarea
                value={editCv}
                onChange={(e) => setEditCv(e.target.value)}
                rows={3}
                className="w-full bg-bg-secondary border border-border rounded px-2 py-1.5 text-sm text-fg focus:outline-none focus:border-accent"
              />
              <div className="flex gap-2">
                <button
                  onClick={saveEdit}
                  className="text-xs px-3 py-1 bg-accent text-bg rounded hover:bg-accent-hover"
                >
                  保存
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="text-xs px-3 py-1 bg-bg-tertiary text-fg-secondary rounded"
                >
                  取消
                </button>
              </div>
            </div>
          ) : (
            <>
              {a.cv && (
                <p className="text-sm text-fg-secondary mt-1">{a.cv}</p>
              )}
              {a.outcome && (
                <p className="text-xs text-fg-muted mt-1">结果：{a.outcome}</p>
              )}
              {a.reflection && (
                <p className="text-xs text-fg-muted mt-1">复盘：{a.reflection}</p>
              )}
            </>
          )}
        </div>
        {!editing && (
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={startEdit}
              className="p-1.5 text-fg-muted hover:text-fg transition"
              title="编辑 CV"
            >
              <Edit2 size={13} />
            </button>
            <button
              onClick={undo}
              className="p-1.5 text-fg-muted hover:text-danger transition"
              title="撤销"
            >
              <Undo2 size={13} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// v0.3.5 立: 统计指标条 — 沉淀质量卡片用
function StatBar({
  label,
  value,
  detail,
  grade,
}: {
  label: string;
  value: string;
  detail: string;
  grade: { label: string; color: string };
}) {
  return (
    <div className="rounded-md bg-bg/50 border border-border px-3 py-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] text-fg-muted">{label}</span>
        <span className={`text-[10px] font-medium ${grade.color}`}>{grade.label}</span>
      </div>
      <div className="text-[18px] font-semibold text-fg leading-tight">{value}</div>
      <div className="text-[10.5px] text-fg-muted mt-0.5">{detail}</div>
    </div>
  );
}

// v0.4.1 立: 按时间倒序拉平视图 — 跨项目按 date desc 展示所有成就
// 复用 AchievementCard 渲染 (跟 /cv 视图风格一致, 简单卡片 + 项目 emoji + cv)
function TimelineView({
  items,
  mutate,
}: {
  items: Achievement[];
  mutate: () => void;
}) {
  // 按日期 desc 排 (新→旧)
  const sorted = useMemo(
    () => [...items].sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0)),
    [items],
  );

  return (
    <div className="space-y-1.5">
      {sorted.map((a) => (
        <AchievementCard key={a.id} achievement={a} mutate={mutate} />
      ))}
    </div>
  );
}

// v0.4.1 立: 单条成就卡 — 复用给 timeline 视图 (跟 /cv 卡片风格一致)
function AchievementCard({
  achievement: a,
  mutate,
}: {
  achievement: Achievement;
  mutate: () => void;
}) {
  // inline edit cv 状态
  const [editing, setEditing] = useState(false);
  const [cvText, setCvText] = useState(a.cv);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setCvText(a.cv);
  }, [a.cv]);

  const startEdit = () => {
    setEditing(true);
  };
  const cancelEdit = () => {
    setCvText(a.cv);
    setEditing(false);
  };
  const save = async () => {
    if (cvText === a.cv) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await api.updateAchievement(a.id, { cv: cvText });
      mutate();
      setEditing(false);
    } catch (e) {
      alert(`保存失败: ${e instanceof Error ? e.message : e}`);
    } finally {
      setSaving(false);
    }
  };

  const undo = async () => {
    if (!confirm(`撤销「${a.title}」的沉淀？任务会恢复到进行中。`)) return;
    try {
      await api.undoAchievement(a.id);
      mutate();
    } catch (e) {
      alert(`撤销失败: ${e instanceof Error ? e.message : e}`);
    }
  };

  // 状态指示器
  const statusBadge = (() => {
    if (a.cv_status === "ready")
      return { icon: CheckCircle2, label: "ready", color: "text-success" };
    if (a.cv_status === "needs_data")
      return { icon: AlertCircle, label: "差数据", color: "text-warning" };
    return { icon: Circle, label: "草稿", color: "text-fg-muted" };
  })();
  const StatusIcon = statusBadge.icon;

  return (
    <div className="rounded-md border border-border bg-bg-secondary p-3 hover:border-accent/30 transition">
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          <span className="text-[12px] flex-shrink-0 opacity-70">
            {projectEmoji(a.project_id)}
          </span>
          <span className="text-[13px] font-medium text-fg truncate">{a.title}</span>
          <span className={`text-[10.5px] flex items-center gap-0.5 ${statusBadge.color} flex-shrink-0`}>
            <StatusIcon size={10} />
            {statusBadge.label}
          </span>
        </div>
        <span className="text-[10.5px] text-fg-muted flex-shrink-0 font-mono">
          {a.date}
        </span>
      </div>
      <div className="text-[11px] text-fg-muted mb-1.5 truncate">
        {a.project}
      </div>
      {editing ? (
        <div className="space-y-1.5">
          <textarea
            value={cvText}
            onChange={(e) => setCvText(e.target.value)}
            rows={2}
            className="w-full bg-bg border border-accent/40 rounded-md px-2 py-1.5 text-[12.5px] text-fg-secondary focus:outline-none focus:border-accent resize-none"
          />
          <div className="flex items-center gap-1.5">
            <button
              onClick={save}
              disabled={saving}
              className="text-[11px] px-2 py-1 rounded bg-accent/20 text-accent hover:bg-accent/30 disabled:opacity-40"
            >
              {saving ? "保存中..." : "保存"}
            </button>
            <button
              onClick={cancelEdit}
              disabled={saving}
              className="text-[11px] px-2 py-1 rounded text-fg-muted hover:text-fg"
            >
              取消
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-start justify-between gap-2">
          <div className="text-[12.5px] text-fg-secondary leading-relaxed flex-1">
            {a.cv || <span className="italic text-fg-muted/70">(无 cv 文本)</span>}
          </div>
          <div className="flex items-center gap-0.5 flex-shrink-0">
            <button
              onClick={startEdit}
              className="p-1 text-fg-muted hover:text-fg transition"
              title="编辑 CV"
            >
              <Edit2 size={12} />
            </button>
            <button
              onClick={undo}
              className="p-1 text-fg-muted hover:text-danger transition"
              title="撤销沉淀"
            >
              <Undo2 size={12} />
            </button>
          </div>
        </div>
      )}
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
  );
}
