"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { api, type Snapshot, type Project, type Task, statusIcon, dueColor, dueLabel } from "@/lib/api";
import { Check, Trash2, ChevronRight, Plus, CheckSquare, Square, X, Edit2, Settings } from "lucide-react";
import { ChatWindow } from "./ChatWindow";
import Link from "next/link";

export function MainBoard({ refreshKey }: { refreshKey: number }) {
  const { data: snapshot, mutate: refreshSnapshot } = useSWR<Snapshot>(
    "/api/snapshot",
    () => api.getSnapshot()
  );
  const { data: llmStatus } = useSWR("/api/llm/status", () => api.llmStatus(), {
    refreshInterval: 30000,
  });

  useEffect(() => {
    refreshSnapshot();
  }, [refreshKey, refreshSnapshot]);

  const refresh = () => {
    refreshSnapshot();
  };

  const readyCount = snapshot?.counts.achievementsReady ?? 0;
  const pendingCount = snapshot?.counts.achievementsPending ?? 0;
  const focusCount = snapshot?.focus.length ?? 0;

  return (
    <div className="flex h-screen bg-bg">
      {/* 左栏：项目 + 任务 */}
      <div className="w-[34%] border-r border-border flex flex-col bg-bg-secondary">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h1 className="text-lg font-semibold text-fg">拾光</h1>
          <div className="flex items-center gap-3">
            {/* LLM 状态徽章 */}
            {llmStatus && (
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded ${
                  llmStatus.available
                    ? "bg-success/10 text-success"
                    : "bg-fg-muted/10 text-fg-muted"
                }`}
                title={llmStatus.available ? `LLM: ${llmStatus.model}` : "无 LLM，使用关键词模式"}
              >
                {llmStatus.available ? "● LLM" : "○ 关键词"}
              </span>
            )}
            <Link
              href="/achievements"
              className="text-xs text-fg-secondary hover:text-fg transition"
            >
              成就
            </Link>
            <Link
              href="/settings"
              className="text-fg-muted hover:text-fg transition"
              title="设置"
            >
              <Settings size={14} />
            </Link>
          </div>
        </div>

        {/* 累计计数 */}
        <div className="px-4 py-2 border-b border-border flex items-center gap-3 text-xs text-fg-secondary">
          <span>本期已沉淀 <strong className="text-accent">{readyCount}</strong> 条成就</span>
          {pendingCount > 0 && (
            <span className="text-fg-muted">· <strong className="text-warning">{pendingCount}</strong> 条待补</span>
          )}
          {snapshot && focusCount > 0 && (
            <span className="text-fg-muted">· {focusCount} 项待办</span>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {snapshot && (
            <>
              <FocusSection snapshot={snapshot} onChange={refresh} />
              <ProjectsSection snapshot={snapshot} onChange={refresh} />
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
  const dueCls = dueColor(item.due);
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
        <span className={`text-xs flex-shrink-0 ${item.blocked ? "" : priorityColor}`}>
          {item.blocked ? "🚧" : "▸"}
        </span>
      )}
      <span className="flex-1 truncate text-fg">{item.title}</span>
      {item.due && (
        <span className={`text-xs flex-shrink-0 text-${dueCls}`}>
          {dueLabel(item.due)}
        </span>
      )}
    </div>
  );
}

function ProjectsSection({
  snapshot,
  onChange,
}: {
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
        {snapshot.projects.length === 0 && (
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
  const [expanded, setExpanded] = useState(false);
  const [newChecklistText, setNewChecklistText] = useState("");

  const priorityDot =
    task.priority === "高"
      ? "bg-danger"
      : task.priority === "中"
      ? "bg-warning"
      : "bg-fg-muted";

  const dueCls = dueColor(task.due);

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
    <div className="group border-b border-border last:border-b-0">
      <div
        className={`flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-bg-tertiary transition ${
          task.draft ? "bg-accent/5" : ""
        }`}
      >
        {/* 状态图标（单击切换/完成）*/}
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (!confirming) {
              setConfirming(true);
              setTimeout(() => setConfirming(false), 2000);
            } else {
              complete();
            }
          }}
          className={`text-xs w-4 flex-shrink-0 ${
            confirming ? "text-success" : "text-fg-muted hover:text-fg"
          }`}
          title="单击：标记完成"
        >
          {confirming ? "✓" : statusIcon(task.status)}
        </button>
        <span className={`w-1.5 h-1.5 rounded-full ${priorityDot} flex-shrink-0`} />

        <button
          onClick={() => setExpanded((e) => !e)}
          className="flex-1 text-left truncate flex items-center gap-1.5"
        >
          <span
            className={`truncate ${task.blocked ? "line-through text-fg-muted" : "text-fg"}`}
          >
            {task.title}
          </span>
          {task.draft && (
            <span className="text-[10px] px-1 py-0 rounded bg-accent/20 text-accent flex-shrink-0">
              草稿
            </span>
          )}
          {task.blocked && (
            <span className="text-[10px] px-1 py-0 rounded bg-warning/20 text-warning flex-shrink-0">
              阻塞
            </span>
          )}
        </button>

        {task.due && (
          <span className={`text-[10px] flex-shrink-0 text-${dueCls}`}>
            {dueLabel(task.due)}
          </span>
        )}

        {totalCount > 0 && (
          <span className="text-[10px] text-fg-muted flex-shrink-0">
            {doneCount}/{totalCount}
          </span>
        )}

        {task.next_action && (
          <span className="text-[10px] text-fg-muted truncate max-w-[120px]" title={task.next_action}>
            ▸ {task.next_action}
          </span>
        )}

        <button
          onClick={remove}
          className="opacity-0 group-hover:opacity-100 text-fg-muted hover:text-danger transition"
        >
          <Trash2 size={12} />
        </button>
      </div>

      {expanded && (
        <div className="px-3 py-2 bg-bg/50 text-xs space-y-1">
          {task.checklist.length > 0 && (
            <div className="space-y-0.5 mb-2">
              {task.checklist.map((item, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 group/item px-1 py-0.5 rounded hover:bg-bg-tertiary transition"
                >
                  <button onClick={() => toggleChecklistItem(i)} className="flex-shrink-0">
                    {item.done ? (
                      <CheckSquare size={12} className="text-success" />
                    ) : (
                      <Square size={12} className="text-fg-muted" />
                    )}
                  </button>
                  <span
                    className={`flex-1 truncate ${item.done ? "line-through text-fg-muted" : "text-fg"}`}
                  >
                    {item.text}
                  </span>
                  <button
                    onClick={() => removeChecklistItem(i)}
                    className="opacity-0 group-hover/item:opacity-100 text-fg-muted hover:text-danger"
                  >
                    <X size={10} />
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
            className="flex items-center gap-1"
          >
            <input
              value={newChecklistText}
              onChange={(e) => setNewChecklistText(e.target.value)}
              placeholder="添加子项..."
              className="flex-1 bg-bg border border-border rounded px-2 py-0.5 text-[11px] text-fg placeholder-fg-muted focus:outline-none focus:border-accent"
            />
            <button
              type="submit"
              disabled={!newChecklistText.trim()}
              className="p-1 text-fg-muted hover:text-fg disabled:opacity-30"
            >
              <Plus size={11} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
