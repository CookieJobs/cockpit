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
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type StatusFilter = "all" | "needs_data" | "pending" | "ready";

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

export default function AchievementsPage() {
  const [filter, setFilter] = useState<StatusFilter>("all");
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

        {/* 状态过滤 — 让 needs_data 中间态可被发现 + 批量升级 */}
        <div className="flex items-center gap-2 mb-6 text-sm">
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

        {projectGroups.length === 0 ? (
          <div className="rounded-lg border border-border bg-bg-secondary p-8 text-center text-fg-muted">
            还没有成就。完成任务后会沉淀在这里 ✨
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
    await api.updateAchievement(a.id, { cv: editCv, cv_status: "ready" });
    setEditing(false);
    onMutate();
  };
  const upgrade = async () => {
    await api.updateAchievement(a.id, { cv_status: "ready" });
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
              <button
                onClick={upgrade}
                className="text-[10px] px-1.5 py-0.5 rounded bg-warning/15 text-warning hover:bg-warning/25 font-medium transition"
                title="补全数据后升级为 ready"
              >
                📊 还差数据 · 升级
              </button>
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
                  className="text-xs px-3 py-1 bg-accent text-black rounded hover:bg-accent-hover"
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
