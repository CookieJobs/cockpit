"use client";

import { useState, useEffect, useRef } from "react";
import useSWR from "swr";
import { api, type Snapshot, type Project, type Task, type TaskStatus, statusIcon, dueColor, dueLabel, taskAgeDays, projectEmoji, type Priority } from "@/lib/api";
import { Check, Trash2, ChevronRight, ChevronDown, Plus, CheckSquare, Square, X, Edit2, Settings, Calendar, Flag, MessageSquare, PanelRightOpen, Undo2, Archive, ArchiveRestore, Sparkles } from "lucide-react";
import { ChatWindow } from "./ChatWindow";
import { CompleteTaskModal } from "./CompleteTaskModal";
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

  // 左侧色条 - 颜色+形状双编码
  // 高:实心红 / 中:实心黄 / 低:实心灰 / 阻塞:斜纹感(用更深的灰)
  const priorityBar =
    item.blocked
      ? "bg-fg-muted/60"
      : item.priority === "高"
      ? "bg-danger"
      : item.priority === "中"
      ? "bg-warning"
      : "bg-fg-muted/30";

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
      className={`group relative flex flex-col gap-0.5 rounded-lg pl-4 pr-3 py-2.5 cursor-pointer hover:bg-bg-tertiary/60 transition ${
        item.blocked ? "opacity-70" : ""
      }`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onRequestComplete}
    >
      <div className="flex items-center gap-3">
        {/* 左侧色条 - 标识优先级 */}
        <div className={`absolute left-1 top-2.5 bottom-2.5 w-[3px] rounded-full ${priorityBar}`} />

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

  return (
    <div
      className="rounded-xl bg-bg-tertiary/30 overflow-hidden"
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
    task.priority === "高"
      ? "bg-danger"
      : task.priority === "中"
      ? "bg-warning"
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
        {/* 状态色点 button (纯色点, click 弹下拉切换) */}
        <div onClick={(e) => e.stopPropagation()}>
          <StatusMenu
            status={task.status}
            onChange={updateStatus}
            onComplete={requestComplete}
          />
        </div>

        {/* 优先级色点 button (纯色点, click 弹下拉切换) */}
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
          草稿/阻塞/checklist/age 仍保留, 它们是事件性 meta 不是常驻控件 */}
      {(task.draft || task.blocked || totalCount > 0 || taskAgeDays(task.created_at) >= 2) && (
        <div className="flex items-center gap-3 pl-3 pr-3 pb-1.5 text-[12px] text-fg-muted">
          {/* 草稿/阻塞标签 */}
          {task.draft && (
            <span className="px-1.5 py-0 rounded bg-accent/20 text-accent">
              草稿
            </span>
          )}
          {task.blocked && (
            <span className="px-1.5 py-0 rounded bg-warning/20 text-warning">
              阻塞
            </span>
          )}

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
  // (2026-07-21 重构): 任务行视觉去重,改纯色点 button 形态 —
  //   默认 8x8 色点(不显示 "高/中/低" 文字,不带 ▾ 箭头)
  //   hover 时显示 ring + bg 高亮,提示"可点"
  //   click 弹 popover,里面仍是 "● 高 / ● 中 / ● 低" 三行可选
  // 理由: 旧版 task 行有 4 个 ▾ 箭头(状态/priority/展开/due)上下叠,
  //   PriorityMenu 自身又占第二行 meta 区带 "● 高 ▾",视觉噪音爆炸。
  //   改后色点本身是 button,完成即状态切换,无文字无箭头。
  // 色点颜色 (lesson #1 教训: 低优先级色点必须可见):
  //   高 = bg-danger, 中 = bg-warning, 低 = bg-fg-secondary (#a0a0a0) 不再走 #666
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const dotColor =
    priority === "高"
      ? "bg-danger"
      : priority === "中"
      ? "bg-warning"
      : "bg-fg-secondary";

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Esc 关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  return (
    <div ref={ref} className="relative flex-shrink-0">
      <button
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen((o) => !o);
          }
        }}
        className={`w-5 h-5 flex items-center justify-center rounded transition ${
          open ? "bg-bg-tertiary ring-1 ring-accent" : "hover:bg-bg-tertiary"
        }`}
        title={`优先级: ${priority}(点击切换)`}
        aria-label={`优先级 ${priority}`}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className={`block w-2 h-2 rounded-full ${dotColor}`} />
      </button>
      {open && (
        <div className="absolute left-0 top-6 z-20 bg-bg-secondary border border-border rounded-md shadow-lg py-0.5 min-w-[80px]">
          {(["高", "中", "低"] as const).map((p) => (
            <button
              key={p}
              onClick={(e) => {
                e.stopPropagation();
                onChange(p);
                setOpen(false);
              }}
              className={`w-full text-left px-2 py-1 hover:bg-bg-tertiary text-xs flex items-center gap-1.5 ${
                p === priority ? "text-accent" : "text-fg"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  p === "高"
                    ? "bg-danger"
                    : p === "中"
                    ? "bg-warning"
                    : "bg-fg-secondary"
                }`}
              />
              {p}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}


function StatusMenu({
  status,
  onChange,
  onComplete,
}: {
  status: TaskStatus;
  onChange: (s: Exclude<TaskStatus, "已完成">) => void;
  onComplete: () => void;
}) {
  // (2026-07-21 重构): 跟 PriorityMenu 同步改纯色点 button 形态 —
  //   默认 10x10 圆点 (未开始=灰/进行中=accent/已完成=success 绿)
  //   hover 时显示 ring + bg 高亮,提示"可点"
  //   click 弹 popover: "○ 未开始 / ◐ 进行中 / ─── / ✅ 完成 ✨"
  //   完成是 action 不是 status, 仍保留在 popover 末尾
  // 理由: 旧版 task 第一行 "○ 未开始 ▾" 跟第二行 "● 高 ▾" 上下叠两个 ▾,
  //   加上 due 编辑器自己的 popover, 一个 task 行 3-4 个下拉箭头, 极乱。
  //   改成色点后视觉锚点只剩"2 个色点 + 标题 + due", 干净。
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // 色点 (代替原来的 "○" "◐" "●" 单字符, 视觉更稳)
  // 状态色梯度: 灰 → accent → 绿, 三档清晰
  const dotColor =
    status === "已完成"
      ? "bg-success"
      : status === "进行中"
      ? "bg-accent"
      : "bg-fg-secondary";

  // 点外面关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Esc 关闭 (基础可达性)
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  // 列表项: 未开始 / 进行中 (已完成 不可达 — 看板里 task 永远不显示, 因为完成即删除)
  // 加一个独立的'完成 ✨' 项作为主动完成入口, 弹 4 字段 modal
  const items: { key: Exclude<TaskStatus, "已完成">; dotCls: string; label: string }[] = [
    { key: "未开始", dotCls: "bg-fg-secondary", label: "未开始" },
    { key: "进行中", dotCls: "bg-accent", label: "进行中" },
  ];

  return (
    <div ref={ref} className="relative flex-shrink-0">
      <button
        ref={buttonRef}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen((o) => !o);
          }
        }}
        className={`w-5 h-5 flex items-center justify-center rounded transition ${
          open ? "bg-bg-tertiary ring-1 ring-accent" : "hover:bg-bg-tertiary"
        }`}
        title={`状态: ${status} (点击切换)`}
        aria-label={`状态 ${status}`}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className={`block w-2.5 h-2.5 rounded-full ${dotColor}`} />
      </button>
      {open && (
        <div
          className="absolute left-0 top-6 z-20 bg-bg-secondary border border-border rounded-md shadow-lg py-0.5 min-w-[140px]"
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
                  setOpen(false);
                  buttonRef.current?.focus();
                }}
                className={`w-full text-left px-2 py-1.5 hover:bg-bg-tertiary text-[12px] flex items-center gap-2 ${
                  isCurrent ? "text-accent" : "text-fg"
                }`}
              >
                <span className={`block w-2.5 h-2.5 rounded-full ${it.dotCls}`} />
                <span>{it.label}</span>
                {isCurrent && (
                  <span className="ml-auto text-[10px] text-fg-muted">当前</span>
                )}
              </button>
            );
          })}
          {/* 分隔 + 完成项 (主动完成入口 — 弹 4 字段 modal) */}
          <div className="border-t border-border/60 my-0.5" />
          <button
            onClick={(e) => {
              e.stopPropagation();
              setOpen(false);
              onComplete();
            }}
            className="w-full text-left px-2 py-1.5 hover:bg-bg-tertiary text-[12px] flex items-center gap-2 text-success"
            title="点击弹窗填结果 / CV / 复盘"
          >
            <Check size={11} strokeWidth={2.5} />
            <span>完成</span>
            <span className="ml-auto text-[11px]">✨</span>
          </button>
        </div>
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
  const [editing, setEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [editing]);

  const commit = (val: string) => {
    setEditing(false);
    if (val === "") {
      if (due !== null) onChange(null);
      return;
    }
    if (val !== due) onChange(val);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        type="date"
        defaultValue={due || ""}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit((e.target as HTMLInputElement).value);
          if (e.key === "Escape") setEditing(false);
        }}
        onClick={(e) => e.stopPropagation()}
        className="text-[10px] bg-bg border border-border rounded px-1 py-0.5 text-fg"
        style={{ width: "110px" }}
      />
    );
  }

  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        setEditing(true);
      }}
      className={`text-[10px] flex-shrink-0 text-${dueCls} hover:underline px-1`}
      title={due ? `截止:${due}(点击修改)` : "点击设置截止日期"}
    >
      {due ? dueLabel(due) : <span className="text-fg-muted opacity-0 group-hover:opacity-100">📅</span>}
    </button>
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
      className="text-fg-secondary whitespace-pre-wrap border-l-2 border-border pl-2 cursor-text hover:border-accent min-h-[1.5em]"
      title="点击编辑详情"
    >
      {description || (
        <span className="text-fg-muted italic">+ 添加详情</span>
      )}
    </div>
  );
}
