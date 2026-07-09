"use client";

import useSWR from "swr";
import { api, type Snapshot, type Project, type Task } from "@/lib/api";
import { useState, useEffect } from "react";
import { Check, Trash2, ChevronRight, Plus } from "lucide-react";
import { ChatWindow } from "./ChatWindow";
import Link from "next/link";

export function MainBoard({ refreshKey }: { refreshKey: number }) {
  const { data: snapshot, mutate: refreshSnapshot } = useSWR<Snapshot>(
    "/api/snapshot",
    () => api.getSnapshot(),
    { refreshInterval: 0 }
  );
  const { data: projects } = useSWR<Project[]>("/api/projects", () =>
    api.listProjects()
  );

  useEffect(() => {
    refreshSnapshot();
  }, [refreshKey, refreshSnapshot]);

  const refresh = () => {
    refreshSnapshot();
  };

  return (
    <div className="flex h-screen bg-bg">
      {/* 左栏：项目 + 任务 */}
      <div className="w-[32%] border-r border-border flex flex-col bg-bg-secondary">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h1 className="text-lg font-semibold text-fg">拾光</h1>
          <Link
            href="/achievements"
            className="text-xs text-fg-secondary hover:text-fg transition"
          >
            成就库 →
          </Link>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {snapshot && (
            <>
              <FocusSection snapshot={snapshot} onChange={refresh} />
              <ProjectsSection
                projects={projects || []}
                snapshot={snapshot}
                onChange={refresh}
              />
            </>
          )}
        </div>
      </div>

      {/* 右栏：对话窗口 */}
      <div className="flex-1 flex flex-col">
        <ChatWindow onAction={refresh} />
      </div>
    </div>
  );
}

function FocusSection({
  snapshot,
  onChange,
}: {
  snapshot: Snapshot;
  onChange: () => void;
}) {
  if (snapshot.focus.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-bg p-4 text-sm text-fg-muted">
        🎉 当前没有待办任务
      </div>
    );
  }
  return (
    <div>
      <div className="px-2 mb-2 flex items-center justify-between">
        <h2 className="text-xs font-semibold text-fg-secondary uppercase tracking-wider">
          今日聚焦 · {snapshot.focus.length}
        </h2>
      </div>
      <div className="space-y-1">
        {snapshot.focus.map((item) => (
          <FocusItem
            key={item.id}
            item={item}
            onComplete={async () => {
              await api.completeTask(item.id, { cv: `完成「${item.title}」` });
              onChange();
            }}
          />
        ))}
      </div>
    </div>
  );
}

function FocusItem({
  item,
  onComplete,
}: {
  item: Snapshot["focus"][number];
  onComplete: () => void;
}) {
  const [hover, setHover] = useState(false);
  const priorityColor =
    item.priority === "高"
      ? "text-danger"
      : item.priority === "中"
      ? "text-warning"
      : "text-fg-muted";
  return (
    <div
      className={`group flex items-center gap-2 rounded-md px-2 py-2 text-sm transition cursor-pointer ${
        item.blocked ? "opacity-60" : "hover:bg-bg-tertiary"
      }`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onComplete}
    >
      {hover ? (
        <Check size={14} className="text-success flex-shrink-0" />
      ) : (
        <span
          className={`w-3.5 h-3.5 flex-shrink-0 ${priorityColor}`}
        >
          {item.blocked ? "🚧" : "▸"}
        </span>
      )}
      <span className="flex-1 truncate text-fg">{item.title}</span>
      {item.due && (
        <span className="text-xs text-fg-muted flex-shrink-0">{item.due}</span>
      )}
    </div>
  );
}

function ProjectsSection({
  projects,
  snapshot,
  onChange,
}: {
  projects: Project[];
  snapshot: Snapshot;
  onChange: () => void;
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [newProjectName, setNewProjectName] = useState("");
  const [showInput, setShowInput] = useState(false);

  const createProject = async () => {
    if (!newProjectName.trim()) return;
    await api.createProject(newProjectName.trim());
    setNewProjectName("");
    setShowInput(false);
    onChange();
  };

  return (
    <div>
      <div className="px-2 mb-2 flex items-center justify-between">
        <h2 className="text-xs font-semibold text-fg-secondary uppercase tracking-wider">
          项目
        </h2>
        <button
          onClick={() => setShowInput((s) => !s)}
          className="text-fg-muted hover:text-fg transition"
          title="新建项目"
        >
          <Plus size={14} />
        </button>
      </div>
      {showInput && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createProject();
          }}
          className="px-2 mb-2"
        >
          <input
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            placeholder="项目名..."
            autoFocus
            className="w-full bg-bg border border-border rounded px-2 py-1 text-sm text-fg placeholder-fg-muted focus:outline-none focus:border-accent"
          />
        </form>
      )}
      <div className="space-y-1">
        {snapshot.projects.map((p) => (
          <ProjectCard
            key={p.id || p.name}
            project={p}
            expanded={expanded[p.id || p.name] || false}
            onToggle={() =>
              setExpanded((e) => ({ ...e, [p.id || p.name]: !e[p.id || p.name] }))
            }
            onChange={onChange}
          />
        ))}
        {projects.length === 0 && (
          <div className="text-xs text-fg-muted px-2 py-2">
            还没有项目。点击 + 新建一个。
          </div>
        )}
      </div>
    </div>
  );
}

function ProjectCard({
  project,
  expanded,
  onToggle,
  onChange,
}: {
  project: Snapshot["projects"][number];
  expanded: boolean;
  onToggle: () => void;
  onChange: () => void;
}) {
  const taskCount = project.tasks.length;
  return (
    <div className="rounded-md bg-bg border border-border overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-bg-tertiary transition"
      >
        <ChevronRight
          size={12}
          className={`text-fg-muted transition-transform ${
            expanded ? "rotate-90" : ""
          }`}
        />
        <span className="flex-1 text-left text-sm text-fg truncate">
          {project.name}
        </span>
        <span className="text-xs text-fg-muted">{taskCount}</span>
      </button>
      {expanded && (
        <div className="border-t border-border bg-bg-secondary/50">
          {project.tasks.length === 0 ? (
            <div className="px-3 py-2 text-xs text-fg-muted">无任务</div>
          ) : (
            <div className="py-1">
              {project.tasks.map((t) => (
                <TaskRow key={t.id} task={t} onChange={onChange} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TaskRow({ task, onChange }: { task: Task; onChange: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const priorityDot =
    task.priority === "高"
      ? "bg-danger"
      : task.priority === "中"
      ? "bg-warning"
      : "bg-fg-muted";

  const complete = async () => {
    await api.completeTask(task.id, { cv: `完成「${task.title}」` });
    onChange();
  };

  const remove = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("确定删除这个任务？")) {
      await api.deleteTask(task.id);
      onChange();
    }
  };

  return (
    <div
      className={`group flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-bg-tertiary transition ${
        task.draft ? "bg-accent/5" : ""
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${priorityDot} flex-shrink-0`} />
      <span
        className={`flex-1 truncate ${task.blocked ? "line-through text-fg-muted" : "text-fg"}`}
        onClick={() => {
          if (!confirming) {
            setConfirming(true);
            setTimeout(() => setConfirming(false), 2000);
          } else {
            complete();
          }
        }}
        title="单击：标记完成"
      >
        {task.title}
        {task.draft && (
          <span className="ml-2 text-[10px] text-accent">草稿</span>
        )}
        {task.blocked && (
          <span className="ml-2 text-[10px] text-warning">阻塞</span>
        )}
      </span>
      <button
        onClick={remove}
        className="opacity-0 group-hover:opacity-100 text-fg-muted hover:text-danger transition"
      >
        <Trash2 size={12} />
      </button>
    </div>
  );
}
