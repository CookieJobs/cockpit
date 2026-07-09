"use client";

import useSWR from "swr";
import { api, type Achievement } from "@/lib/api";
import { ArrowLeft, CheckCircle2, Circle, Edit2, Undo2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

export default function AchievementsPage() {
  const { data: items, mutate } = useSWR<Achievement[]>("/api/achievements", () =>
    api.listAchievements()
  );

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editCv, setEditCv] = useState("");

  const startEdit = (a: Achievement) => {
    setEditingId(a.id);
    setEditCv(a.cv);
  };

  const saveEdit = async () => {
    if (!editingId) return;
    await api.updateAchievement(editingId, { cv: editCv, cv_status: "ready" });
    setEditingId(null);
    mutate();
  };

  const undo = async (id: string) => {
    if (!confirm("撤销这个成就？任务会恢复到进行中状态。")) return;
    await api.undoAchievement(id);
    mutate();
  };

  // 按日期分组
  const groups: Record<string, Achievement[]> = {};
  (items || []).forEach((a) => {
    groups[a.date] = groups[a.date] || [];
    groups[a.date].push(a);
  });

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
          </div>
          <div className="text-sm text-fg-secondary">
            {items?.length || 0} 项
          </div>
        </div>

        {Object.keys(groups).length === 0 ? (
          <div className="rounded-lg border border-border bg-bg-secondary p-8 text-center text-fg-muted">
            还没有成就。完成任务后会沉淀在这里 ✨
          </div>
        ) : (
          <div className="space-y-6">
            {Object.entries(groups)
              .sort(([a], [b]) => b.localeCompare(a))
              .map(([date, list]) => (
                <div key={date}>
                  <h2 className="text-sm font-semibold text-fg-secondary uppercase tracking-wider mb-2 px-2">
                    {date}
                  </h2>
                  <div className="space-y-2">
                    {list.map((a) => (
                      <div
                        key={a.id}
                        className="rounded-lg border border-border bg-bg-secondary p-4 hover:border-border-hover transition"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              {a.cv_status === "ready" ? (
                                <CheckCircle2 size={14} className="text-success flex-shrink-0" />
                              ) : (
                                <Circle size={14} className="text-fg-muted flex-shrink-0" />
                              )}
                              <h3 className="font-semibold text-fg">{a.title}</h3>
                              <span className="text-xs px-2 py-0.5 rounded bg-bg-tertiary text-fg-secondary">
                                {a.project}
                              </span>
                            </div>
                            {editingId === a.id ? (
                              <div className="mt-2 space-y-2">
                                <textarea
                                  value={editCv}
                                  onChange={(e) => setEditCv(e.target.value)}
                                  rows={3}
                                  className="w-full bg-bg border border-border rounded px-2 py-1.5 text-sm text-fg focus:outline-none focus:border-accent"
                                />
                                <div className="flex gap-2">
                                  <button
                                    onClick={saveEdit}
                                    className="text-xs px-3 py-1 bg-accent text-black rounded hover:bg-accent-hover"
                                  >
                                    保存
                                  </button>
                                  <button
                                    onClick={() => setEditingId(null)}
                                    className="text-xs px-3 py-1 bg-bg-tertiary text-fg-secondary rounded"
                                  >
                                    取消
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <>
                                {a.cv && (
                                  <p className="text-sm text-fg-secondary mt-1">
                                    {a.cv}
                                  </p>
                                )}
                                {a.outcome && (
                                  <p className="text-xs text-fg-muted mt-1">
                                    结果：{a.outcome}
                                  </p>
                                )}
                                {a.reflection && (
                                  <p className="text-xs text-fg-muted mt-1">
                                    复盘：{a.reflection}
                                  </p>
                                )}
                              </>
                            )}
                          </div>
                          {editingId !== a.id && (
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => startEdit(a)}
                                className="p-1.5 text-fg-muted hover:text-fg transition"
                                title="编辑 CV"
                              >
                                <Edit2 size={14} />
                              </button>
                              <button
                                onClick={() => undo(a.id)}
                                className="p-1.5 text-fg-muted hover:text-danger transition"
                                title="撤销"
                              >
                                <Undo2 size={14} />
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
