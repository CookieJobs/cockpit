"use client";

import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import useSWR from "swr";
import { api, type Snapshot, type Project, type Task, type Achievement, type TaskStatus, statusIcon, dueColor, dueLabel, taskAgeDays, projectEmoji, relativeDate, daysAgoISO, type Priority, PRIORITY_BADGE_STYLES } from "@/lib/api";
import { Check, Trash2, ChevronRight, ChevronDown, Plus, CheckSquare, Square, X, Edit2, Settings, Calendar, Flag, MessageSquare, PanelRightOpen, Undo2, Archive, ArchiveRestore, Sparkles } from "lucide-react";
import { ChatWindow } from "./ChatWindow";
import { CompleteTaskModal } from "./CompleteTaskModal";
import { usePopover, usePopoverPosition } from "./Popover";
import Link from "next/link";

const CHAT_COLLAPSED_KEY = "cockpit_chat_collapsed";

export function MainBoard({ refreshKey }: { refreshKey: number }) {
  const { data: snapshot, mutate: refreshSnapshot } = useSWR<Snapshot>(
    "/api/snapshot",
    () => api.getSnapshot()
  );
  const { data: llmStatus } = useSWR("/api/llm/status", () => api.llmStatus(), {
    refreshInterval: 30000,
  });

  // 对话栏默认展开;用户可收起,状态持久化到 localStorage
  const [chatOpen, setChatOpen] = useState<boolean>(true);
  useEffect(() => {
    try {
      const stored = localStorage.getItem(CHAT_COLLAPSED_KEY);
      if (stored === "1") setChatOpen(false);
    } catch {
      /* SSR / 隐私模式无 localStorage,忽略 */
    }
  }, []);
  const toggleChat = () => {
    setChatOpen((v) => {
      const next = !v;
      try {
        localStorage.setItem(CHAT_COLLAPSED_KEY, next ? "0" : "1");
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  useEffect(() => {
    refreshSnapshot();
  }, [refreshKey, refreshSnapshot]);

  const refresh = () => {
    refreshSnapshot();
  };

  // 完成任务弹窗的 state：哪个 task 正在被"完成"
  // 接受 Pick<Task, "id" | "title">，focus 卡片（FocusItem）也满足最小接口，
  // 但同样支持完整 Task 对象
  const [completingTask, setCompletingTask] = useState<Pick<Task, "id" | "title"> | null>(null);

  // "今天已完成" 折叠区展开状态（跨刷新保留）
  const [doneExpanded, setDoneExpanded] = useState(false);

  const readyCount = snapshot?.counts.achievementsReady ?? 0;
  const pendingCount = snapshot?.counts.achievementsPending ?? 0;
  const focusCount = snapshot?.focus.length ?? 0;
  const doneTodayCount = snapshot?.done_today.length ?? 0;

  return (
    <div className="flex h-screen bg-bg">
      {/* 左栏:项目 + 任务 — 主视图,占主空间 */}
      <div className="flex-1 min-w-0 border-r border-border flex flex-col bg-bg-secondary">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <h1 className="text-[17px] font-semibold text-fg tracking-tight">
            Cockpit
          </h1>
          <div className="flex items-center gap-3">
            {/* LLM 状态徽章 */}
            {llmStatus && (
              <span
                className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                  llmStatus.available
                    ? "bg-success/10 text-success"
                    : "bg-fg-muted/10 text-fg-muted"
                }`}
                title={llmStatus.available ? `LLM: ${llmStatus.model}` : "无 LLM,使用关键词模式"}
              >
                {llmStatus.available
                  ? `● ${llmStatus.model || "?"}`
                  : "○ 关键词"}
              </span>
            )}
            <Link
              href="/today"
              className="text-[12px] text-fg-secondary hover:text-fg transition px-2 py-1 rounded hover:bg-bg-tertiary"
              title="晨间 ritual：聚焦今天要做的"
            >
              今天
            </Link>
            <Link
              href="/report"
              className="text-[12px] text-fg-secondary hover:text-fg transition px-2 py-1 rounded hover:bg-bg-tertiary flex items-center gap-1"
              title="周报/述职 workspace"
            >
              <Sparkles size={11} />
              写周报
            </Link>
            <Link
              href="/achievements"
              className="text-[12px] text-fg-secondary hover:text-fg transition px-2 py-1 rounded hover:bg-bg-tertiary"
            >
              成就
            </Link>
            <Link
              href="/settings"
              className="text-fg-muted hover:text-fg transition p-1.5 rounded hover:bg-bg-tertiary"
              title="设置"
            >
              <Settings size={14} />
            </Link>
          </div>
        </div>

        {/* 累计计数 */}
        <div className="px-5 py-3 border-b border-border flex items-center gap-4 text-[12px] text-fg-secondary">
          <span>
            本期已沉淀{" "}
            <strong className="text-accent font-semibold tabular-nums">
              {readyCount}
            </strong>{" "}
            条成就
          </span>
          {pendingCount > 0 && (
            <span className="text-fg-muted">
              ·{" "}
              <strong className="text-warning font-semibold tabular-nums">
                {pendingCount}
              </strong>{" "}
              条待补
            </span>
          )}
          {snapshot && focusCount > 0 && (
            <span className="text-fg-muted">
              ·{" "}
              <strong className="text-fg font-semibold tabular-nums">
                {focusCount}
              </strong>{" "}
              项待办
            </span>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-5 space-y-6">
          {snapshot && (
            <>
              <FocusSection
                snapshot={snapshot}
                onChange={refresh}
                onRequestComplete={(t) => setCompletingTask(t)}
              />
              <ProjectsSection
                snapshot={snapshot}
                onChange={refresh}
                onRequestComplete={(t) => setCompletingTask(t)}
              />
              <DoneTodaySection
                items={snapshot.done_today}
                expanded={doneExpanded}
                onToggle={() => setDoneExpanded((e) => !e)}
                onChange={refresh}
              />
            </>
          )}
        </div>
      </div>

      {/* 完成任务弹窗 - 4 字段沉淀 (outcome / cv / reflection / cv_status) */}
      {completingTask && (
        <CompleteTaskModal
          task={completingTask}
          onClose={() => setCompletingTask(null)}
          onSave={async (data) => {
            await api.completeTask(completingTask.id, data);
            setCompletingTask(null);
            refresh();
          }}
        />
      )}

      {/* 右栏:对话窗口 - 折叠态:44px 窄条;展开态:w-[35%] 侧栏 */}
      {chatOpen ? (
        <div className="w-[35%] min-w-[360px] max-w-[640px] flex flex-col">
          <ChatWindow onAction={refresh} onCollapse={() => toggleChat()} />
        </div>
      ) : (
        <button
          onClick={() => toggleChat()}
          className="w-11 flex-shrink-0 border-l border-border bg-bg-secondary hover:bg-bg-tertiary transition flex flex-col items-center justify-start pt-4 gap-3 text-fg-muted hover:text-fg group"
          title="展开对话"
        >
          <PanelRightOpen size={16} />
          <span
            className="text-[10px] tracking-wider"
            style={{ writingMode: "vertical-rl" }}
          >
            展开对话
          </span>
          <MessageSquare size={12} className="mt-2 opacity-50 group-hover:opacity-100" />
        </button>
      )}
    </div>
  );
}

function SectionHeader({
  title,
  count,
  right,
}: {
  title: string;
  count?: number;
  right?: React.ReactNode;
}) {
  return (
    <div className="px-1 mb-2 flex items-center justify-between">
      <h2 className="text-[11px] uppercase tracking-[0.12em] text-fg-muted font-semibold">
        {title}
        {count !== undefined && (
          <span className="ml-2 text-fg-secondary tabular-nums">{count}</span>
        )}
      </h2>
      {right}
    </div>
  );
}

function FocusSection({
  snapshot,
  onChange,
  onRequestComplete,
}: {
  snapshot: Snapshot;
  onChange: () => void;
  onRequestComplete: (task: Pick<Task, "id" | "title">) => void;
}) {
  if (snapshot.focus.length === 0) {
    return (
      <div>
        <SectionHeader title="今日聚焦" count={0} />
        <div className="px-1 py-6 text-center text-[13px] text-fg-muted">
          所有任务都已收尾
        </div>
      </div>
    );
  }
  return (
    <div>
      <SectionHeader title="今日聚焦" count={snapshot.focus.length} />
      <div className="space-y-0.5">
        {snapshot.focus.map((item) => (
          <FocusItem
            key={item.id}
            item={item}
            onRequestComplete={() => onRequestComplete(item)}
          />
        ))}
      </div>
    </div>
  );
}

function FocusItem({
  item,
  onRequestComplete,
}: {
  item: Snapshot["focus"][number];
  onRequestComplete: () => void;
}) {
  const [hover, setHover] = useState(false);

  // 2026-07-23 v2 改造: 删左侧色条, 改用 P0/P1/P2/P3 badge 跟 TaskRow / FocusRow 三处统一。
  //   之前色条 + badge 双编码 = MainBoard 内部割裂 (顶部 FocusItem 色条 vs 下方 TaskRow badge),
  //   改 badge only 跟 TaskRow 1:1 一致, 用户在 MainBoard 页面任何位置看到的优先级都一样。
  //   FocusItem 是只读展示 (无 priority 编辑入口), 所以 badge 是 <span> 不是 <button>
  //   (跟 FocusRow 行为一致; TaskRow 因为是 PriorityMenu trigger, 才是 button 可点)。
  //   阻塞 = opacity-70 整行变暗, 不再单独给 badge 上 fg-muted/60 (跟 TaskRow 阻塞行为一致)。

  const dueCls = dueColor(item.due);
  const dueTextColor =
    dueCls === "danger"
      ? "text-danger"
      : dueCls === "warning"
      ? "text-warning"
      : dueCls === "accent"
      ? "text-accent"
      : "text-fg-muted";

  return (
    <div
      className={`group flex flex-col gap-0.5 rounded-lg pl-3 pr-3 py-2.5 cursor-pointer hover:bg-bg-tertiary/60 transition ${
        item.blocked ? "opacity-70" : ""
      }`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onRequestComplete}
    >
      <div className="flex items-center gap-3">
        {/* P0/P1/P2/P3 badge - 跟 TaskRow / FocusRow 三处统一, 软底色 + 同色描边 + font-mono */}
        <span
          className={`inline-flex items-center justify-center h-5 px-1.5 rounded
            border text-[10px] font-mono font-semibold leading-none tracking-tight
            flex-shrink-0 select-none
            ${PRIORITY_BADGE_STYLES[item.priority]}`}
          title={`优先级: ${item.priority}${item.blocked ? " · 阻塞" : ""}`}
        >
          {item.priority}
        </span>

        {/* 状态按钮:默认空心字符,hover 显示对勾 */}
        <button
          className="w-5 h-5 flex items-center justify-center flex-shrink-0 text-fg-muted hover:text-success transition"
          title="标记完成（弹出 4 字段沉淀弹窗）"
        >
          {hover ? (
            <Check size={14} className="text-success" strokeWidth={2.5} />
          ) : (
            <span className="text-[15px] leading-none">
              {item.blocked ? "🚧" : "○"}
            </span>
          )}
        </button>

        {/* 标题 */}
        <span
          className={`flex-1 truncate text-[15px] font-medium ${
            item.blocked ? "text-fg-secondary line-through" : "text-fg"
          }`}
        >
          {item.title}
        </span>

        {/* due 标签 - 永远右对齐,突出颜色 */}
        {item.due && (
          <span className={`text-[12px] tabular-nums font-medium flex-shrink-0 ${dueTextColor}`}>
            {dueLabel(item.due)}
          </span>
        )}
      </div>
    </div>
  );
}

function DoneTodaySection({
  items,
  expanded,
  onToggle,
  onChange,
}: {
  items: NonNullable<Snapshot["done_today"]>;
  expanded: boolean;
  onToggle: () => void;
  onChange: () => void;
}) {
  // 折叠区（继承自 task-cockpit dashboard.html 的 done-section）：
  // - 头部 summary 显示计数 + 折叠箭头
  // - 展开后列出今天的成就，给即时成就感
  // - 每条带撤销按钮（误标完成可一键回退到进行中）
  if (!items || items.length === 0) return null;

  return (
    <div>
      <div
        className="rounded-lg border border-border bg-bg-secondary/50 overflow-hidden"
        onClick={onToggle}
      >
        <div className="px-3 py-2.5 flex items-center justify-between cursor-pointer hover:bg-bg-tertiary/40 transition select-none">
          <div className="flex items-center gap-2">
            <ChevronRight
              size={12}
              strokeWidth={2}
              className={`text-fg-muted transition-transform flex-shrink-0 ${
                expanded ? "rotate-90" : ""
              }`}
            />
            <span className="text-[11px] uppercase tracking-[0.1em] text-fg-muted font-semibold">
              ✅ 今天已完成
            </span>
            <span className="text-[11px] text-fg-secondary tabular-nums">
              {items.length}
            </span>
          </div>
          <span className="text-[10px] text-fg-muted/60">
            {expanded ? "收起" : "展开"}
          </span>
        </div>

        {expanded && (
          <div className="border-t border-border/40 divide-y divide-border/30">
            {items.map((a) => (
              <div key={a.id} className="px-3 py-2.5 group/item">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Check size={12} className="text-success flex-shrink-0" strokeWidth={2.5} />
                      <span className="text-[13px] text-fg truncate">{a.title}</span>
                      {a.cv_status === "pending" && (
                        <span className="text-[10px] px-1.5 py-0 rounded bg-warning/20 text-warning font-medium flex-shrink-0">
                          CV 待补
                        </span>
                      )}
                    </div>
                    {(a.cv || a.outcome) && (
                      <div className="text-[12px] text-fg-secondary mt-1 line-clamp-2">
                        {a.cv || a.outcome}
                      </div>
                    )}
                    <div className="text-[10px] text-fg-muted mt-1">
                      {a.project}
                    </div>
                  </div>
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      if (!confirm(`撤销「${a.title}」的完成状态？任务会恢复到进行中。`)) return;
                      await api.undoAchievement(a.id);
                      onChange();
                    }}
                    className="opacity-0 group-hover/item:opacity-100 text-fg-muted hover:text-danger transition p-1 rounded hover:bg-bg-tertiary flex-shrink-0"
                    title="撤销（恢复任务到进行中）"
                  >
                    <Undo2 size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ProjectsSection({
  snapshot,
  onChange,
  onRequestComplete,
}: {
  snapshot: Snapshot;
  onChange: () => void;
  onRequestComplete: (task: Task) => void;
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [newProjectName, setNewProjectName] = useState("");
  const [showInput, setShowInput] = useState(false);
  // 已归档项目开关 + 数据（默认隐藏，开了之后单独显示在下方）
  const [showArchived, setShowArchived] = useState(false);
  const { data: allProjects, mutate: refreshArchived } = useSWR<Project[]>(
    showArchived ? "/api/projects?include_archived=true" : null,
    () => api.listProjects(true)
  );
  const archivedProjects = (allProjects || []).filter(
    (p) => p.archived && !snapshot.projects.some((sp) => sp.id === p.id)
  );

  const createProject = async () => {
    if (!newProjectName.trim()) return;
    await api.createProject(newProjectName.trim());
    setNewProjectName("");
    setShowInput(false);
    onChange();
  };

  const restoreProject = async (id: string) => {
    await api.updateProject(id, { archived: false });
    refreshArchived();
    onChange();
  };

  return (
    <div>
      <SectionHeader
        title="项目"
        count={snapshot.projects.length}
        right={
          <div className="flex items-center gap-2">
            {archivedProjects.length > 0 && (
              <button
                onClick={() => setShowArchived((s) => !s)}
                className="text-[12px] text-fg-muted hover:text-fg transition flex items-center gap-1 px-2 py-0.5 rounded hover:bg-bg-tertiary"
                title="显示已归档项目"
              >
                <Archive size={12} />
                {showArchived ? "隐藏" : "已归档"} {archivedProjects.length}
              </button>
            )}
            <button
              onClick={() => setShowInput((s) => !s)}
              className="text-[12px] text-fg-muted hover:text-fg transition flex items-center gap-1 px-2 py-0.5 rounded hover:bg-bg-tertiary"
              title="新建项目"
            >
              <Plus size={12} />
              新建
            </button>
          </div>
        }
      />
      {showInput && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createProject();
          }}
          className="px-1 mb-2"
        >
          <input
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            placeholder="项目名..."
            autoFocus
            className="w-full bg-bg-secondary border border-border rounded-md px-3 py-2 text-[14px] text-fg placeholder-fg-muted focus:outline-none focus:border-accent"
          />
        </form>
      )}
      <div className="space-y-1.5">
        {snapshot.projects.map((p) => (
          <ProjectCard
            key={p.id || p.name}
            project={p}
            expanded={expanded[p.id || p.name] || false}
            onToggle={() =>
              setExpanded((e) => ({ ...e, [p.id || p.name]: !e[p.id || p.name] }))
            }
            onChange={onChange}
            onRequestComplete={onRequestComplete}
          />
        ))}
        {snapshot.projects.length === 0 && (
          <div className="text-[13px] text-fg-muted px-3 py-4 text-center">
            还没有项目。点上面的"新建"开始一个。
          </div>
        )}
      </div>

      {/* 已归档项目（默认折叠，2026-07-20 立）*/}
      {showArchived && archivedProjects.length > 0 && (
        <div className="mt-4 pt-3 border-t border-border/40">
          <div className="text-[11px] uppercase tracking-[0.1em] text-fg-muted font-semibold px-2 mb-2">
            已归档
          </div>
          <div className="space-y-1.5">
            {archivedProjects.map((p) => (
              <div
                key={p.id}
                className="rounded-xl bg-bg-tertiary/20 border border-border/40 px-3 py-2 flex items-center gap-2"
              >
                <span className="text-[14px] flex-shrink-0 opacity-60">
                  {projectEmoji(p.id)}
                </span>
                <span className="flex-1 text-[14px] text-fg-muted truncate">
                  {p.name}
                </span>
                <button
                  onClick={() => restoreProject(p.id)}
                  className="text-[11px] text-fg-muted hover:text-accent transition flex items-center gap-1 px-2 py-1 rounded hover:bg-bg-tertiary"
                  title="恢复项目"
                >
                  <ArchiveRestore size={12} />
                  恢复
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ProjectCard({
  project,
  expanded,
  onToggle,
  onChange,
  onRequestComplete,
}: {
  project: Snapshot["projects"][number];
  expanded: boolean;
  onToggle: () => void;
  onChange: () => void;
  onRequestComplete: (task: Task) => void;
}) {
  const taskCount = project.tasks.length;
  const [editingName, setEditingName] = useState(false);
  const [editingDesc, setEditingDesc] = useState(false);
  const [descText, setDescText] = useState(project.description);
  const [hovering, setHovering] = useState(false);
  const [addingTask, setAddingTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [addingBusy, setAddingBusy] = useState(false);

  // 同步后端 description 变化到本地编辑 buffer
  useEffect(() => {
    setDescText(project.description);
  }, [project.description]);

  const saveDesc = async () => {
    setEditingDesc(false);
    if (!project.id) return;
    if (descText === project.description) return;
    await api.updateProject(project.id, { description: descText });
    onChange();
  };

  const cancelDesc = () => {
    setDescText(project.description);
    setEditingDesc(false);
  };

  const updateName = async (newName: string) => {
    setEditingName(false);
    const trimmed = newName.trim();
    if (!project.id || !trimmed || trimmed === project.name) return;
    await api.updateProject(project.id, { name: trimmed });
    onChange();
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!project.id) return;
    if (!confirm(`确定删除项目「${project.name}」?\n\n该操作会同时删除项目下所有任务。`)) {
      return;
    }
    await api.deleteProject(project.id);
    onChange();
  };

  // 归档项目（2026-07-20 立）— 不删数据, 把项目从主列表移到"已归档" 区
  const handleArchive = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!project.id) return;
    if (!confirm(`归档项目「${project.name}」?\n\n项目会从主列表移到"已归档"区, 任务数据保留, 可随时恢复。`)) {
      return;
    }
    await api.updateProject(project.id, { archived: true });
    onChange();
  };

  const submitNewTask = async () => {
    const title = newTaskTitle.trim();
    if (!title || !project.id || addingBusy) return;
    setAddingBusy(true);
    try {
      await api.createTask({ project: project.id, title });
      setNewTaskTitle("");
      setAddingTask(false);
      onChange();
    } catch (e) {
      // 失败时保留输入,方便用户重试
      console.error("Failed to add task:", e);
    } finally {
      setAddingBusy(false);
    }
  };

  const doneCount = project.tasks.filter(
    (t) => t.status === "已完成"
  ).length;

  // 项目内"近期已沉淀"子区 (2026-07-22 立, 方案A):
  //   项目卡片里只显示 active tasks 看不到"刚干完的",
  //   这里拉最近 7 天的成就 (按 project.name 过滤, 复用 storage.list_achievements),
  //   折叠子区跟看板底部 "今天已完成" 一个套路, undo 按钮也复用。
  //   只在项目展开时 fetch (SWR key 守门), 没数据就完全隐藏。
  //   窗口 (7 天) 改成 30 / 全量只改一个常量 + 后端 since 参数。
  const PROJECT_ACH_WINDOW_DAYS = 7;
  const [achievementsOpen, setAchievementsOpen] = useState(true);
  const { data: projectAchievements, mutate: refreshProjectAchievements } = useSWR<Achievement[]>(
    expanded && project.id
      ? `/api/achievements?project=${encodeURIComponent(project.name)}&since=${daysAgoISO(PROJECT_ACH_WINDOW_DAYS)}`
      : null,
    () => api.listAchievements({
      project: project.name,
      since: daysAgoISO(PROJECT_ACH_WINDOW_DAYS),
    }),
    { revalidateOnFocus: false }
  );

  const undoAchievement = async (aid: string) => {
    if (!confirm("撤销这个成就？任务会恢复到任务列表。")) return;
    await api.undoAchievement(aid);
    refreshProjectAchievements();
    onChange();
  };

  return (
    <div
      className={`rounded-xl overflow-hidden transition-all ${
        expanded
          ? "bg-bg-tertiary/40 ring-1 ring-accent/50 border border-accent/30"
          : "bg-bg-tertiary/30 border border-transparent"
      }`}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <div className="group px-3 pt-2.5 pb-1.5 hover:bg-bg-tertiary/60 transition">
        {/* 标题行:chevron + name + count + 操作按钮 */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={onToggle}
            className="flex items-center gap-2.5 flex-1 min-w-0"
          >
            <ChevronRight
              size={14}
              strokeWidth={2}
              className={`text-fg-muted transition-transform flex-shrink-0 ${
                expanded ? "rotate-90" : ""
              }`}
            />
            {editingName ? (
              <input
                type="text"
                defaultValue={project.name}
                autoFocus
                onBlur={(e) => updateName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    updateName((e.target as HTMLInputElement).value);
                  }
                  if (e.key === "Escape") {
                    e.preventDefault();
                    setEditingName(false);
                  }
                }}
                onClick={(e) => e.stopPropagation()}
                onDoubleClick={(e) => e.stopPropagation()}
                className="flex-1 bg-bg border border-accent rounded-md px-2 py-1 text-[15px] text-fg focus:outline-none"
              />
            ) : (
              <span
                onDoubleClick={(e) => {
                  e.stopPropagation();
                  if (project.id) setEditingName(true);
                }}
                className="flex-1 text-left text-[15px] font-medium text-fg truncate flex items-center gap-1.5"
                title="双击编辑名称"
              >
                <span className="text-[15px] flex-shrink-0">
                  {projectEmoji(project.id)}
                </span>
                {project.name}
              </span>
            )}
            {taskCount > 0 ? (
              <span className="text-[12px] text-fg-secondary tabular-nums flex-shrink-0">
                <span className={doneCount === taskCount ? "text-success" : "text-fg-secondary"}>
                  {doneCount}
                </span>
                <span className="text-fg-muted">/{taskCount}</span>
              </span>
            ) : (
              <span className="text-[12px] text-fg-muted flex-shrink-0">0</span>
            )}
          </button>
          {project.id && !editingName && (
            <div className="flex items-center gap-0.5 flex-shrink-0 opacity-40 group-hover:opacity-100 transition-opacity">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingName(true);
                }}
                className="text-fg-muted hover:text-fg transition p-1 rounded hover:bg-bg-secondary"
                title="编辑项目名称"
              >
                <Edit2 size={12} />
              </button>
              <button
                onClick={handleArchive}
                className="text-fg-muted hover:text-warning transition p-1 rounded hover:bg-bg-secondary"
                title="归档项目（任务数据保留, 可恢复）"
              >
                <Archive size={12} />
              </button>
              <button
                onClick={handleDelete}
                className="text-fg-muted hover:text-danger transition p-1 rounded hover:bg-bg-secondary"
                title="删除项目"
              >
                <Trash2 size={12} />
              </button>
            </div>
          )}
        </div>
        {/* description 行:折叠也始终可见,点入可编辑 */}
        {project.id && !editingName && (
          <div className="pl-[22px] mt-1 pr-1">
            {editingDesc ? (
              <div>
                <textarea
                  autoFocus
                  value={descText}
                  onChange={(e) => setDescText(e.target.value)}
                  onBlur={saveDesc}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      e.preventDefault();
                      saveDesc();
                    }
                    if (e.key === "Escape") {
                      e.preventDefault();
                      cancelDesc();
                    }
                  }}
                  placeholder="项目目标 / 描述..."
                  rows={2}
                  className="w-full bg-bg border border-accent rounded px-2 py-1 text-[12px] leading-relaxed text-fg placeholder-fg-muted resize-none focus:outline-none"
                />
                <div className="flex items-center gap-2 mt-1 text-[10px] text-fg-muted">
                  <span>⌘+Enter 保存 · Esc 取消</span>
                </div>
              </div>
            ) : (
              <div
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingDesc(true);
                }}
                className="group/desc text-[12px] leading-relaxed text-fg-secondary truncate cursor-text hover:text-fg min-h-[1.25em] -mx-1 px-1 rounded hover:bg-bg-tertiary/40"
                title={project.description || "点击添加项目描述"}
              >
                {project.description || (
                  <span className="text-fg-muted italic">+ 添加项目描述</span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
      {expanded && (
        <div className="px-2 pb-2 pt-1 bg-bg-tertiary/20 border-t border-border/40">
          <div className="space-y-0.5">
            {project.tasks.map((t) => (
              <TaskRow key={t.id} task={t} onChange={onChange} onRequestComplete={onRequestComplete} />
            ))}
            {project.tasks.length === 0 && !addingTask && (
              <div className="px-3 py-3 text-[13px] text-fg-muted text-center">
                项目下还没有任务 — 在下面加一个
              </div>
            )}
          </div>
          {/* 添加任务 - 默认占位按钮,点击展开 input */}
          <div className="mt-1.5 px-1.5">
            {addingTask ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  submitNewTask();
                }}
                className="flex items-center gap-2"
              >
                <input
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") {
                      e.preventDefault();
                      setAddingTask(false);
                      setNewTaskTitle("");
                    }
                  }}
                  placeholder="任务名... (Enter 添加,Esc 取消)"
                  autoFocus
                  disabled={addingBusy}
                  className="flex-1 bg-bg border border-border focus:border-accent rounded-md px-2.5 py-1.5 text-[14px] text-fg placeholder-fg-muted focus:outline-none disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={!newTaskTitle.trim() || addingBusy}
                  className="px-2.5 py-1.5 bg-accent text-black text-[13px] font-medium rounded-md hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  添加
                </button>
              </form>
            ) : (
              <button
                onClick={() => setAddingTask(true)}
                className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-[13px] text-fg-muted hover:text-fg rounded-md hover:bg-bg-tertiary/60 transition text-left"
              >
                <Plus size={13} />
                添加任务
              </button>
            )}
          </div>

          {/* 项目内"近期已沉淀"子区 (2026-07-22 立, 方案A)
              只在 (展开 + 有数据) 时显示, 7 天窗口由 PROJECT_ACH_WINDOW_DAYS 控制
              视觉对齐 DoneTodaySection: 折叠头 + check + title + 相对时间 + hover undo */}
          {expanded && projectAchievements && projectAchievements.length > 0 && (
            <div className="mt-2 mx-1.5 rounded-md border border-border/30 bg-bg-tertiary/30 overflow-hidden">
              <button
                onClick={() => setAchievementsOpen((o) => !o)}
                className="w-full px-2.5 py-1.5 flex items-center gap-1.5 text-left hover:bg-bg-tertiary/60 transition"
              >
                <ChevronRight
                  size={11}
                  strokeWidth={2}
                  className={`text-fg-muted transition-transform flex-shrink-0 ${
                    achievementsOpen ? "rotate-90" : ""
                  }`}
                />
                <span className="text-[10px] uppercase tracking-[0.1em] text-fg-muted font-semibold">
                  ✓ 已沉淀
                </span>
                <span className="text-[11px] text-fg-secondary tabular-nums">
                  {projectAchievements.length}
                </span>
                <span className="text-[10px] text-fg-muted/60">
                  · {PROJECT_ACH_WINDOW_DAYS} 天内
                </span>
                <span className="ml-auto text-[10px] text-fg-muted/60">
                  {achievementsOpen ? "收起" : "展开"}
                </span>
              </button>
              {achievementsOpen && (
                <div className="border-t border-border/30 divide-y divide-border/20">
                  {projectAchievements.map((a) => (
                    <div
                      key={a.id}
                      className="px-2.5 py-1.5 flex items-center gap-2 group/item hover:bg-bg-tertiary/40 transition"
                    >
                      <Check size={11} className="text-success flex-shrink-0" strokeWidth={2.5} />
                      <span className="flex-1 truncate text-[12px] text-fg-secondary">
                        {a.title}
                      </span>
                      {a.cv_status === "pending" && (
                        <span className="text-[9px] px-1 py-0 rounded bg-warning/20 text-warning font-medium flex-shrink-0">
                          CV 待补
                        </span>
                      )}
                      <span className="text-[10px] text-fg-muted/70 flex-shrink-0 tabular-nums">
                        {relativeDate(a.date)}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          undoAchievement(a.id);
                        }}
                        className="opacity-0 group-hover/item:opacity-100 text-fg-muted hover:text-danger transition p-0.5 rounded flex-shrink-0"
                        title="撤销（恢复任务到任务列表）"
                      >
                        <Undo2 size={10} />
                      </button>
                    </div>
                  ))}
                  {projectAchievements.length >= 5 && (
                    <Link
                      href={`/achievements?project=${encodeURIComponent(project.name)}`}
                      className="block px-2.5 py-1.5 text-[10px] text-fg-muted hover:text-accent transition"
                    >
                      查看全部 →
                    </Link>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TaskRow({
  task,
  onChange,
  onRequestComplete,
}: {
  task: Task;
  onChange: () => void;
  onRequestComplete: (task: Task) => void;
}) {
  const [hover, setHover] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [newChecklistText, setNewChecklistText] = useState("");

  const updateTitle = async (newTitle: string) => {
    setEditingTitle(false);
    const trimmed = newTitle.trim();
    if (!trimmed || trimmed === task.title) return;
    await api.updateTask(task.id, { title: trimmed });
    onChange();
  };

  const priorityDot =
    task.priority === "P0"
      ? "bg-danger"
      : task.priority === "P1"
      ? "bg-warning"
      : task.priority === "P2"
      ? "bg-info"
      : "bg-fg-muted";

  const dueCls = dueColor(task.due);

  // 状态机 linear 切 (v2, 2026-07-17):
  //   未开始 ↔ 进行中  — 通过 StatusMenu 下拉切换 (PATCH status)
  //   完成 (任意状态)   — 通过 StatusMenu"完成 ✨" 项 / 整行 click / (已删) hover ✅
  //                     弹 4 字段 modal
  // 已沉淀 task 在 storage 层已被删除, 看板永远看不到"已完成" 状态,
  // 所以下拉里 status 只有 2 个有效选项 + 1 个"完成" 触发器 = 3 行
  const updateStatus = async (s: Exclude<TaskStatus, "已完成">) => {
    await api.updateTask(task.id, { status: s });
    onChange();
  };

  const requestComplete = () => {
    onRequestComplete(task);
  };

  // 展开/收起 (整行 click 已是"完成",展开走显式 chevron 避免冲突)
  const toggleExpand = (e: React.MouseEvent) => {
    e.stopPropagation();
    setExpanded((v) => !v);
  };

  const remove = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("确定删除这个任务?")) {
      await api.deleteTask(task.id);
      onChange();
    }
  };

  const updatePriority = async (p: Priority) => {
    await api.updateTask(task.id, { priority: p });
    onChange();
  };

  const updateDue = async (date: string | null) => {
    await api.updateTask(task.id, { due: date });
    onChange();
  };

  // (2026-07-22) 通用 inline-edit 助手 — blocked / draft 等"语义性 meta" 字段
  // 跟 priority / due 一样走 PATCH + SWR revalidate, 不做乐观更新 (跟现有 inline edit 一致)
  // 入口统一在 StatusMenu popover 末尾, 不在第二行 meta 徽章上加 click (避免双入口)
  const updateField = async (field: "blocked" | "draft", value: boolean) => {
    await api.updateTask(task.id, { [field]: value });
    onChange();
  };

  const addChecklistItem = async () => {
    if (!newChecklistText.trim()) return;
    await api.checklistAdd(task.id, newChecklistText.trim());
    setNewChecklistText("");
    onChange();
  };

  const toggleChecklistItem = async (index: number) => {
    await api.checklistToggle(task.id, index);
    onChange();
  };

  const removeChecklistItem = async (index: number) => {
    await api.checklistRemove(task.id, index);
    onChange();
  };

  const doneCount = task.checklist.filter((c) => c.done).length;
  const totalCount = task.checklist.length;

  return (
    <div
      className={`group/row rounded-lg hover:bg-bg-tertiary/60 transition ${
        task.draft ? "bg-accent/5 hover:bg-accent/10" : ""
      }`}
    >
      {/* 第一行:主信息 - 色点编码 + 标题 + due + hover 出现 controls
          整行 = 展开/收起详情 (task-cockpit 原版)
          重构 2026-07-21 v2: 推翻 v1 "整行 click = 完成" 决策。
            v1 决策 (2026-07-17) 是为了解决 lesson #4 "完成路径堵死",但代价是
            整行 90% 空白点中也算 "用户操作" → 弹完成 modal, 反直觉。
            现在用 2 个显式完成入口替代:
              ① StatusMenu 色点 popover 里的 "完成 ✨" 项
              ② hover 第一行时出现的 ✅ 按钮
            整行 click = toggleExpanded, 跟 task-cockpit 原版一致,
            跟用户认知一致 (整行 = 展开, 空白 = 也能展开但没意外 modal)。 */}
      <div
        className={`group/row flex items-center gap-1.5 px-2.5 py-2 cursor-pointer`}
        onClick={(e) => {
          // 状态点 / 优先级点 / due / hover 按钮 都已 e.stopPropagation,
          // 这里只处理"点中标题区或空白" — toggle 展开/收起
          if (editingTitle) return;
          toggleExpand(e);
        }}
      >
        {/* 优先级色点 button (纯色点, click 弹下拉切换) — 2026-07-22 移到最左,
            之前状态/优先级两个色点都堆在标题左边, 跟标题间隔明显不够。
            现在优先级独占最左位置, 标题左对齐, 视觉上更"工整"。 */}
        <div onClick={(e) => e.stopPropagation()}>
          <PriorityMenu priority={task.priority} onChange={updatePriority} />
        </div>

        {/* 标题 */}
        <div className="flex-1 min-w-0 flex items-center gap-2 ml-1">
          {editingTitle ? (
            <input
              type="text"
              defaultValue={task.title}
              autoFocus
              onBlur={(e) => updateTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  updateTitle((e.target as HTMLInputElement).value);
                }
                if (e.key === "Escape") {
                  e.preventDefault();
                  setEditingTitle(false);
                }
              }}
              onClick={(e) => e.stopPropagation()}
              onDoubleClick={(e) => e.stopPropagation()}
              className="flex-1 bg-bg border border-accent rounded-md px-2 py-1 text-[15px] text-fg focus:outline-none"
            />
          ) : (
            <span
              onDoubleClick={(e) => {
                e.stopPropagation();
                setEditingTitle(true);
              }}
              className={`truncate text-[15px] ${
                task.status === "已完成"
                  ? "text-fg-muted line-through"
                  : task.blocked
                  ? "text-fg-secondary"
                  : "text-fg font-medium"
              }`}
              title="双击编辑名称"
            >
              {task.title}
            </span>
          )}
        </div>

        {/* 状态融合指示器 (2026-07-22 挪到右侧, 标题之后 / due 之前)
            同一个 trigger button 多形态: 阻塞 → 🚧, 草稿 → 📝, 否则 → 短进度条
            跟 due 形成"右栏" — 视觉上从右到左扫: 状态+阻塞/草稿 / due / 展开 / hover 按钮 */}
        <div onClick={(e) => e.stopPropagation()}>
          <StatusMenu
            status={task.status}
            blocked={task.blocked}
            draft={task.draft}
            onChange={updateStatus}
            onComplete={requestComplete}
            onToggleBlocked={() => updateField("blocked", !task.blocked)}
            onToggleDraft={() => updateField("draft", !task.draft)}
          />
        </div>

        {/* due 编辑器 - 永远右对齐 */}
        <div onClick={(e) => e.stopPropagation()}>
          <DueEditor due={task.due} dueCls={dueCls} onChange={updateDue} />
        </div>

        {/* 展开状态指示器 (always 可见, 不是 button):
            折叠时 → 灰色 ▸, 展开时 → 旋转 90° + accent 色
            跟整行 click 同步, 不再是独立 button (v2 设计) */}
        <span
          className={`w-4 h-5 flex items-center justify-center flex-shrink-0 transition ${
            expanded ? "text-accent rotate-90" : "text-fg-muted/40"
          }`}
          title={expanded ? "已展开" : "点击行展开详情"}
        >
          <ChevronRight size={12} strokeWidth={2} />
        </span>

        {/* 完成 ✅ hover 按钮 (v2 加回, 2026-07-21):
            这次理由跟 v1 删时不同 — 整行 click 改成展开 (不再重复),
            ✅ 按钮是"完成" 唯一显式可见入口之一 (另一个是 StatusMenu popover)。
            视觉去重, 不会跟整行 click 误触。 */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            requestComplete();
          }}
          className="opacity-0 group-hover/row:opacity-100 w-5 h-5 flex items-center justify-center flex-shrink-0 text-fg-muted hover:text-success hover:bg-bg-tertiary rounded transition"
          title="标记完成 (弹窗填结果 / CV)"
        >
          <Check size={13} strokeWidth={2.5} />
        </button>

        {/* 删除按钮 - hover 第一行时显示 */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            remove(e);
          }}
          className="opacity-0 group-hover/row:opacity-100 w-5 h-5 flex items-center justify-center flex-shrink-0 text-fg-muted hover:text-danger hover:bg-bg-tertiary rounded transition"
          title="删除任务"
        >
          <Trash2 size={12} />
        </button>
      </div>

      {/* 第二行:meta — 只显示离散事件标签, 不再放 PriorityMenu 文字版
          2026-07-21 重构: priority 已经在第一行色点表示, 不需要第二行再写"高/中/低"
          2026-07-22 v3: 删掉「草稿/阻塞」徽章 — 它们已经从第二行上移到第一行右侧
          的状态融合指示器表达 (StatusMenu trigger 根据 blocked/draft 切换 🚧/📝/横条),
          跟第一行右侧的 due 一起形成「状态 + 截止 + 展开 + 按钮」紧凑右栏。
          第二行只剩 checklist 进度 + "挂了N天" 提示, 纯事件性 meta。 */}
      {(totalCount > 0 || taskAgeDays(task.created_at) >= 2) && (
        <div className="flex items-center gap-3 pl-3 pr-3 pb-1.5 text-[12px] text-fg-muted">
          {/* checklist 进度 */}
          {totalCount > 0 && (
            <span className="tabular-nums">
              ☑ {doneCount}/{totalCount}
            </span>
          )}

          {/* 任务"挂起 N 天" 提示 (继承自 task-cockpit taskAge) */}
          {task.status !== "已完成" && taskAgeDays(task.created_at) >= 2 && (
            <span className="text-fg-muted/70" title={`创建于 ${task.created_at}`}>
              挂了 {taskAgeDays(task.created_at)} 天
            </span>
          )}
        </div>
      )}

      {expanded && (
        <div className="px-3 pb-3 pt-1 pl-[42px] space-y-2 border-t border-border/30 mt-1">
          <DescriptionEditor
            taskId={task.id}
            description={task.description}
            onChange={onChange}
          />
          {task.checklist.length > 0 && (
            <div className="space-y-0.5">
              {task.checklist.map((item, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 group/item px-1 py-1 rounded hover:bg-bg-tertiary/60 transition"
                >
                  <button onClick={() => toggleChecklistItem(i)} className="flex-shrink-0">
                    {item.done ? (
                      <CheckSquare size={13} className="text-success" />
                    ) : (
                      <Square size={13} className="text-fg-muted" />
                    )}
                  </button>
                  <span
                    className={`flex-1 truncate text-[13px] ${
                      item.done ? "line-through text-fg-muted" : "text-fg"
                    }`}
                  >
                    {item.text}
                  </span>
                  <button
                    onClick={() => removeChecklistItem(i)}
                    className="opacity-0 group-hover/item:opacity-100 text-fg-muted hover:text-danger p-0.5"
                  >
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              addChecklistItem();
            }}
            className="flex items-center gap-1.5"
          >
            <input
              value={newChecklistText}
              onChange={(e) => setNewChecklistText(e.target.value)}
              placeholder="添加子项..."
              className="flex-1 bg-bg-secondary border border-border rounded-md px-2.5 py-1 text-[13px] text-fg placeholder-fg-muted focus:outline-none focus:border-accent"
            />
            <button
              type="submit"
              disabled={!newChecklistText.trim()}
              className="p-1.5 text-fg-muted hover:text-fg disabled:opacity-30 transition"
            >
              <Plus size={13} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}


// ===== Inline 编辑组件 =====


function PriorityMenu({
  priority,
  onChange,
}: {
  priority: Priority;
  onChange: (p: Priority) => void;
}) {
  // (2026-07-22 v2 重构): 优先级从 3 档 (高/中/低) 升级到 4 档 (P0/P1/P2/P3),
  //   触发 button 也从"8x8 纯色点" 重做成"软底色 + 文字 P0/P1/P2/P3" 的 badge 形态。
  // 理由:
  //   1. 用户报"现在 8x8 色点看不出是优先级, 跟 StatusMenu 短横条区分度低"。
  //   2. 旧版"高/中/低" 文字粒度太粗 — 3 档分不开"紧急/高/普通/不急" 的实际体感。
  //   3. 升 4 档 (P0/P1/P2/P3) 顺便跟业界 incident / 故障分级对齐, 沟通更精准。
  // 视觉设计:
  //   软底色 (color/15) + 同色描边 (color/30) + 同色文字 (color) + 圆角 4px
  //   P0 红 (最急) → P1 橙 → P2 琥珀 → P3 灰 (不急) — 颜色饱和度跟紧急度匹配
  //   hover brightness 提亮, open 状态 ring-accent — 跟 StatusMenu 视觉语言一致
  // (2026-07-22) 抽 usePopover: 跟 StatusMenu 共用 web/components/Popover.tsx 的 hook
  //   (click-outside / Esc / focus trigger / Portal+fixed 全部复用)
  //   旧版 trigger 是 8x8 纯色点无文字, 现在改 badge 有文字 — 不变量 #9 要重写
  //   (旧"无文字无 ChevronDown" 约束不再适用, 改为"必须有 P0/P1/P2/P3 文字 + 软底色")
  const pop = usePopover();
  // (2026-07-22) Portal + fixed 定位, 跟 StatusMenu 同根问题 — ProjectCard overflow-hidden
  //   裁切 absolute 定位的 popover。详见 StatusMenu 注释 + Popover.tsx usePopoverPosition。
  const pos = usePopoverPosition(pop.triggerRef, pop.open, { offsetY: 24 });
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div ref={pop.containerRef} className="relative flex-shrink-0">
      <button
        ref={pop.triggerRef}
        onClick={(e) => {
          e.stopPropagation();
          pop.toggle();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            pop.toggle();
          }
        }}
        className={`inline-flex items-center justify-center h-5 px-1.5 rounded
          border text-[10px] font-mono font-semibold leading-none tracking-tight
          transition select-none
          ${PRIORITY_BADGE_STYLES[priority]}
          ${pop.open ? "ring-1 ring-accent" : "hover:brightness-125"}`}
        title={`优先级: ${priority} (点击切换)`}
        aria-label={`优先级 ${priority}`}
        aria-haspopup="listbox"
        aria-expanded={pop.open}
      >
        {priority}
      </button>
      {pop.open && mounted && createPortal(
        <div
          ref={pop.popoverRef}
          style={{ position: "fixed", top: pos.top, left: pos.left, zIndex: pos.zIndex }}
          className="bg-bg-secondary border border-border rounded-md shadow-lg py-0.5 min-w-[140px]"
        >
          {(["P0", "P1", "P2", "P3"] as const).map((p) => (
            <button
              key={p}
              onClick={(e) => {
                e.stopPropagation();
                onChange(p);
                pop.close();
              }}
              className={`w-full text-left px-2 py-1.5 hover:bg-bg-tertiary text-xs flex items-center gap-2 ${
                p === priority ? "bg-bg-tertiary/50" : ""
              }`}
            >
              <span
                className={`inline-flex items-center justify-center h-5 px-1.5 rounded
                  border text-[10px] font-mono font-semibold leading-none tracking-tight
                  ${PRIORITY_BADGE_STYLES[p]}`}
              >
                {p}
              </span>
              <span className="text-fg-secondary text-[11px]">
                {PRIORITY_LABEL[p]}
              </span>
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  );
}


// 优先级 badge 样式: 见 lib/api.ts 的 PRIORITY_BADGE_STYLES (共享给 MainBoard TaskRow
//   和 /today FocusRow, 两边永远同步)。P2 蓝 220° 跟 P1 橙 30° 拉开 200° 区分。

// 优先级语义 helper (popover 列表里跟在 P0/P1/P2/P3 badge 后面, 帮助快速理解)
//   顺序 = 紧急度从高到低
const PRIORITY_LABEL: Record<Priority, string> = {
  P0: "紧急 / 最高",
  P1: "高 / 重要",
  P2: "普通 (默认)",
  P3: "不急",
};


function StatusMenu({
  status,
  blocked,
  draft,
  onChange,
  onComplete,
  onToggleBlocked,
  onToggleDraft,
}: {
  status: TaskStatus;
  blocked: boolean;
  draft: boolean;
  onChange: (s: Exclude<TaskStatus, "已完成">) => void;
  onComplete: () => void;
  onToggleBlocked: () => void;
  onToggleDraft: () => void;
}) {
  // (2026-07-21 重构 → 2026-07-21 v2 推翻): 用户反馈 StatusMenu 纯色点
  //   跟 PriorityMenu 色点形状都是圆形, 视觉太像不好区分。
  //   改"短进度条"形态 — 横向矩形 + 长度反映状态 (空 / 半满 / 满):
  //     未开始 = 0% (只有 track, 灰底)
  //     进行中 = 50% (accent 半填充)
  //     已完成 = 100% (success 全填充)
  //   优先级保留圆形, 形状对比立刻区分出"状态(横条) vs 优先级(圆点)"。
  //   popover 内容 "○ 未开始 / ◐ 进行中 / ─── / ✅ 完成 ✨" 不变 —
  //     颜色梯度 (灰 → accent → 绿) 也保持一致, 唯一改的是 icon 形态。
  // click 行为不变: hover 显示 bg 高亮, click 弹同一个 popover。
  // (2026-07-22 抽 usePopover): 跟 PriorityMenu 共用 web/components/Popover.tsx 的 hook,
  //   原内联 useState+useRef+click-outside+Esc ~30 行抽走, 行为 1:1 等价。
  const pop = usePopover();
  // (2026-07-22) Portal + fixed 定位: ProjectCard 的 overflow-hidden 会裁掉 absolute 定位的 popover
  //   (CSS 基础: overflow-hidden 无视 z-index 直接切超界内容)。Portal 渲染到 body 跳出去,
  //   position: fixed 相对视口定位, 配合 usePopoverPosition 跟随滚动/resize。
  // offsetY = 24 保持原 absolute top-6 (= 24px) 的视觉间距不变。
  const pos = usePopoverPosition(pop.triggerRef, pop.open, { offsetY: 24 });
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // 进度填充: 宽度按状态分档 + 颜色三档
  const fillWidth =
    status === "已完成" ? "w-full" : status === "进行中" ? "w-1/2" : "w-0";
  const fillColor =
    status === "已完成"
      ? "bg-success"
      : status === "进行中"
      ? "bg-accent"
      : "bg-fg-secondary";

  // 列表项: 未开始 / 进行中 (已完成 不可达 — 看板里 task 永远不显示, 因为完成即删除)
  // 加一个独立的'完成 ✨' 项作为主动完成入口, 弹 4 字段 modal
  //
  // icon 形态 (2026-07-21 跟外显同步): popover 里也用"短进度条"代替圆点/勾
  //   0% 空 (灰 track)  = 未开始
  //   50% 半 (accent)   = 进行中
  //   100% 满 (success) = 完成
  // 三项都用横条, 视觉上 100% 一致, 用户从外显到 popover 不会切换"心智模型"
  const items: { key: Exclude<TaskStatus, "已完成">; barWidth: string; barColor: string; label: string }[] = [
    { key: "未开始", barWidth: "w-0", barColor: "bg-fg-secondary", label: "未开始" },
    { key: "进行中", barWidth: "w-1/2", barColor: "bg-accent", label: "进行中" },
  ];
  const completeItem = { key: "完成", barWidth: "w-full", barColor: "bg-success", label: "完成" };

  // popover 里用的迷你横条: 14x4 跟外显同比例, 略小
  const Bar = ({ width, color }: { width: string; color: string }) => (
    <div className="w-3.5 h-1 rounded-full bg-fg-muted/50 overflow-hidden flex-shrink-0">
      <div className={`h-full rounded-full ${width} ${color}`} />
    </div>
  );

  return (
    <div ref={pop.containerRef} className="relative flex-shrink-0">
      <button
        ref={pop.triggerRef}
        onClick={(e) => {
          e.stopPropagation();
          pop.toggle();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            pop.toggle();
          }
        }}
        className={`w-5 h-5 flex items-center justify-center rounded transition ${
          pop.open ? "bg-bg-tertiary ring-1 ring-accent" : "hover:bg-bg-tertiary"
        }`}
        title={`状态: ${status}${blocked ? " · 阻塞" : ""}${draft ? " · 草稿" : ""} (点击切换)`}
        aria-label={`状态 ${status}${blocked ? " · 阻塞" : ""}${draft ? " · 草稿" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={pop.open}
      >
        {/* (2026-07-22 v3 重构): 状态融合 — 同一个 trigger button 表达
              「状态 + 阻塞/草稿」, 阻塞/草稿 覆盖 状态 (优先级: 阻塞 > 草稿 > 状态)
              进行中/未开始 (无修饰) → 短进度条 (16x4 + 长度按 status)
              进行中/未开始 + 阻塞   → 🚧 warning 色
              进行中/未开始 + 草稿   → 📝 accent 色
              阻塞 + 草稿          → 🚧 (阻塞优先)
            之前的 v2 设计里, 阻塞/草稿是第二行 meta 的独立徽章 — 跟第一行横条
              是「同一维度信息」, 但分散在两行 + 用两种视觉语言表达, 反直觉。
              融合后单组件多形态, 视觉更紧凑, 状态判断只扫一处。 */}
        {blocked ? (
          <span className="text-[13px] leading-none" aria-hidden>🚧</span>
        ) : draft ? (
          <span className="text-[13px] leading-none" aria-hidden>📝</span>
        ) : (
          <div className="w-4 h-1 rounded-full bg-fg-muted/50 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${fillWidth} ${fillColor}`}
            />
          </div>
        )}
      </button>
      {pop.open && mounted && createPortal(
        <div
          ref={pop.popoverRef}
          style={{ position: "fixed", top: pos.top, left: pos.left, zIndex: pos.zIndex }}
          className="bg-bg-secondary border border-border rounded-md shadow-lg py-0.5 min-w-[140px]"
          role="listbox"
        >
          {items.map((it) => {
            const isCurrent = it.key === status;
            return (
              <button
                key={it.key}
                role="option"
                aria-selected={isCurrent}
                onClick={(e) => {
                  e.stopPropagation();
                  if (!isCurrent) onChange(it.key);
                  pop.close();
                }}
                className={`w-full text-left px-2 py-1.5 hover:bg-bg-tertiary text-[12px] flex items-center gap-2 ${
                  isCurrent ? "text-accent" : "text-fg"
                }`}
              >
                <Bar width={it.barWidth} color={it.barColor} />
                <span>{it.label}</span>
                {isCurrent && (
                  <span className="ml-auto text-[10px] text-fg-muted">当前</span>
                )}
              </button>
            );
          })}
          {/* 分隔 + 完成项 (主动完成入口 — 弹 4 字段 modal)
              100% 满 success 绿条 + ✨ 提示"会弹窗" — icon 形态跟状态项一致 */}
          <div className="border-t border-border/60 my-0.5" />
          <button
            onClick={(e) => {
              e.stopPropagation();
              pop.close();
              onComplete();
            }}
            className="w-full text-left px-2 py-1.5 hover:bg-bg-tertiary text-[12px] flex items-center gap-2 text-success"
            title="点击弹窗填结果 / CV / 复盘"
          >
            <Bar width={completeItem.barWidth} color={completeItem.barColor} />
            <span>完成</span>
            <span className="ml-auto text-[11px]">✨</span>
          </button>

          {/* (2026-07-22) 阻塞/草稿 toggle — 跟 Agent 工具对齐,人手也能改这两个字段
              分隔线 + emoji + 文字 + 当前状态对勾,跟状态项/完成项同位同节奏
              点 toggle 立刻 PATCH,不需要弹窗 (跟优先级/状态 inline edit 同款) */}
          <div className="border-t border-border/60 my-0.5" />
          <button
            data-testid="statusmenu-toggle-blocked"
            onClick={(e) => {
              e.stopPropagation();
              pop.close();
              onToggleBlocked();
            }}
            className="w-full text-left px-2 py-1.5 hover:bg-bg-tertiary text-[12px] flex items-center gap-2 text-warning"
            title={blocked ? "点击解除阻塞" : "点击标记为阻塞 (被外部依赖/卡住)"}
          >
            <span className="w-3.5 text-center">🚧</span>
            <span>{blocked ? "解除阻塞" : "标记阻塞"}</span>
            {blocked && <span className="ml-auto text-[11px] text-fg-muted">✓</span>}
          </button>
          <button
            data-testid="statusmenu-toggle-draft"
            onClick={(e) => {
              e.stopPropagation();
              pop.close();
              onToggleDraft();
            }}
            className="w-full text-left px-2 py-1.5 hover:bg-bg-tertiary text-[12px] flex items-center gap-2 text-accent"
            title={draft ? "点击确认这条任务" : "点击标记为草稿 (待确认)"}
          >
            <span className="w-3.5 text-center">📝</span>
            <span>{draft ? "确认草稿" : "标记草稿"}</span>
            {draft && <span className="ml-auto text-[11px] text-fg-muted">✓</span>}
          </button>
        </div>,
        document.body
      )}
    </div>
  );
}


function DueEditor({
  due,
  dueCls,
  onChange,
}: {
  due: string | null;
  dueCls: "danger" | "warning" | "accent" | "muted";
  onChange: (date: string | null) => void;
}) {
  // v2 改造 (2026-07-22): 跟 StatusMenu / PriorityMenu 同根, 改 popover 模式。
  //
  // v1 (2026-07-17) 旧 DueEditor 有 2 个用户报告的 bug:
  //   bug 1: 无 due 的任务看不到任何设置入口
  //     - 旧触发 button 在无 due 时渲染 `📅` 但 class `opacity-0 group-hover:opacity-100`
  //     - 依赖整行 `group` class。v3 (2026-07-21) 把 group 重命名 `group/row`
  //       时漏改, 整行根本没有裸 `group` 父级, 📅 永远不显示。
  //   bug 2: 有 due 时只能改不能清
  //     - 旧是 `<input type="date">` 内联编辑, type=date 的 input 不能手动清空成空串,
  //       又没"清除" 按钮, 用户只能 PATCH {due: null}, 但后端 `if data.due is not None`
  //       把 None 静默吞掉 — 双层堵死。
  //
  // v2 设计:
  //   1. 触发 button **永远可见** (不再 opacity-0 + group-hover), 无 due 时显示
  //      `Calendar` icon + "截止" 文字 (text-fg-muted), hover 时 text-fg + bg 高亮
  //   2. 改 popover 模式: popover 内一个 date input (改值) + "清除截止日期" 红色按钮
  //   3. 走 usePopover + usePopoverPosition + createPortal (跟 StatusMenu 同款),
  //      跳出 ProjectCard overflow-hidden 裁切
  //   4. date input 选完日期立刻 PATCH + close (跟 StatusMenu 切状态同节奏)
  //   5. 清除按钮 → onChange(null) + close, 后端 storage 用 model_fields_set
  //      区分"未传" vs "传了 None" 真正清空 due (端点级测试在
  //      app/tests/test_api_patch_due_null.py)
  const pop = usePopover();
  const pos = usePopoverPosition(pop.triggerRef, pop.open, { offsetY: 24 });
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // 触发 button class: 有 due 时跟 dueCls 颜色, 无 due 时 fg-muted 永远可见
  const triggerClass = due
    ? `text-${dueCls}`
    : "text-fg-muted hover:text-fg";

  return (
    <div ref={pop.containerRef} className="relative flex-shrink-0">
      <button
        ref={pop.triggerRef}
        onClick={(e) => {
          e.stopPropagation();
          pop.toggle();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            pop.toggle();
          }
        }}
        className={`text-[11px] flex items-center gap-1 rounded transition px-1.5 py-0.5 ${
          pop.open ? "bg-bg-tertiary ring-1 ring-accent" : "hover:bg-bg-tertiary"
        } ${triggerClass}`}
        title={due ? `截止 ${dueLabel(due)} (点击修改或清除)` : "点击设置截止日期"}
        aria-label={due ? `截止日期 ${due}` : "设置截止日期"}
        aria-haspopup="dialog"
        aria-expanded={pop.open}
      >
        {due ? (
          <>
            <Calendar size={11} className="flex-shrink-0" />
            <span className="tabular-nums">{dueLabel(due)}</span>
          </>
        ) : (
          <>
            <Calendar size={11} className="flex-shrink-0" />
            <span>截止</span>
          </>
        )}
      </button>
      {pop.open && mounted && createPortal(
        <div
          ref={pop.popoverRef}
          style={{ position: "fixed", top: pos.top, left: pos.left, zIndex: pos.zIndex }}
          className="bg-bg-secondary border border-border rounded-md shadow-lg py-1.5 min-w-[220px]"
          role="dialog"
          aria-label="截止日期"
        >
          {/* 标题 (小字提示, 跟 StatusMenu 风格一致) */}
          <div className="px-2.5 pb-1 text-[11px] text-fg-muted">
            {due ? "修改截止日期" : "设置截止日期"}
          </div>

          {/* date input — 选完立刻 PATCH + close (跟 StatusMenu 切状态同节奏)
              defaultValue 而不是 value: 让用户可以"取消" 改回去, 不每次都强制提交
              onChange 触发时机: 用户点日历选了具体某天 */}
          <div className="px-2.5 pb-1.5">
            <input
              type="date"
              defaultValue={due || ""}
              autoFocus
              onChange={(e) => {
                const val = e.target.value;
                if (val && val !== due) {
                  onChange(val);
                  pop.close();
                }
              }}
              onKeyDown={(e) => {
                // Esc 走 usePopover 统一处理 (关闭 + focus 回到 trigger)
                // Enter 提交当前值
                if (e.key === "Enter") {
                  const val = (e.target as HTMLInputElement).value;
                  if (val && val !== due) onChange(val);
                  pop.close();
                }
              }}
              onClick={(e) => e.stopPropagation()}
              className="w-full bg-bg border border-border rounded px-2 py-1 text-[12px] text-fg focus:outline-none focus:border-accent"
            />
          </div>

          {/* 清除按钮 — 仅在已有 due 时显示, 红色 text-danger
              用户报告: "有截止时间时, 我便没有办法再将这个截止时间给去掉"
              修法: 显式"清除截止日期" 按钮, onClick → onChange(null) + close
              后端 storage 用 model_fields_set 区分"未传" vs "传了 None", 真清空 */}
          {due !== null && (
            <>
              <div className="border-t border-border/60 my-0.5" />
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onChange(null);
                  pop.close();
                }}
                className="w-full text-left px-2.5 py-1.5 hover:bg-bg-tertiary text-[12px] flex items-center gap-2 text-danger"
                title="清除截止日期 (PATCH due=null)"
              >
                <X size={12} />
                <span>清除截止日期</span>
              </button>
            </>
          )}
        </div>,
        document.body
      )}
    </div>
  );
}


function DescriptionEditor({
  taskId,
  description,
  onChange,
}: {
  taskId: string;
  description: string;
  onChange: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(description);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setText(description);
  }, [description]);

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.selectionStart = text.length;
    }
  }, [editing, text.length]);

  const save = async () => {
    setEditing(false);
    if (text === description) return;
    await api.updateTask(taskId, { description: text });
    onChange();
  };

  const cancel = () => {
    setText(description);
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="space-y-1">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save();
            if (e.key === "Escape") cancel();
          }}
          placeholder="任务详情 / 上下文..."
          rows={3}
          className="w-full bg-bg border border-border rounded px-2 py-1 text-xs text-fg placeholder-fg-muted resize-none focus:outline-none focus:border-accent"
        />
        <div className="flex items-center gap-2 text-[10px] text-fg-muted">
          <button onClick={save} className="px-2 py-0.5 bg-accent text-black rounded">
            保存
          </button>
          <button onClick={cancel} className="px-2 py-0.5 hover:text-fg">
            取消
          </button>
          <span className="ml-auto">⌘+Enter 保存 · Esc 取消</span>
        </div>
      </div>
    );
  }

  return (
    <div
      onClick={() => setEditing(true)}
      className="text-[13px] leading-relaxed text-fg-secondary whitespace-pre-wrap border-l-2 border-border pl-2 cursor-text hover:border-accent min-h-[1.5em]"
      title="点击编辑详情"
    >
      {description || (
        <span className="text-fg-muted italic">+ 添加详情</span>
      )}
    </div>
  );
}
