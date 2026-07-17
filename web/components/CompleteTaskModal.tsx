"use client";

import { useState, useEffect, useRef } from "react";
import { X, Sparkles, Check } from "lucide-react";
import type { Task, CVStatus } from "@/lib/api";

/**
 * 完成任务沉淀成就的 4 字段弹窗。
 *
 * 4 字段结构（继承自 task-cockpit skill，对应后端 Achievement 表）：
 * - outcome   客观结果（必填，对外/对 CV 用）
 * - cv        简历级成就陈述（必填，agent 生成 / 用户可改）
 * - reflection 主观复盘（可选，对内 / 成长 / 团队沉淀用）
 * - cv_status  ready（已沉淀可用） / pending（素材不足，挂起待补）
 *
 * 设计参考 task-cockpit dashboard.html 的 complete-modal 视觉。
 * 提交走 api.completeTask，后端已支持 cv_status 升级链路
 * （pending → ready 走 updateAchievement）。
 */
export function CompleteTaskModal({
  task,
  onClose,
  onSave,
}: {
  // 接受最小接口：focus 卡片只暴露 id+title，但同样支持完整 Task
  task: Pick<Task, "id" | "title">;
  onClose: () => void;
  onSave: (data: {
    outcome: string;
    cv: string;
    reflection: string;
    cv_status: CVStatus;
  }) => Promise<void>;
}) {
  const [outcome, setOutcome] = useState("");
  const [cv, setCv] = useState("");
  const [reflection, setReflection] = useState("");
  const [cvStatus, setCvStatus] = useState<CVStatus>("ready");
  const [submitting, setSubmitting] = useState(false);
  const outcomeRef = useRef<HTMLTextAreaElement>(null);

  // 打开时焦点 outcome，并预填 cv 默认值
  useEffect(() => {
    setCv(`完成「${task.title}」`);
    setTimeout(() => outcomeRef.current?.focus(), 50);
  }, [task.title]);

  // 关闭弹窗（点击遮罩 / Esc）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = async () => {
    const o = outcome.trim();
    const c = cv.trim();
    if (!o) {
      outcomeRef.current?.focus();
      return;
    }
    if (!c) return;
    setSubmitting(true);
    try {
      await onSave({ outcome: o, cv: c, reflection: reflection.trim(), cv_status: cvStatus });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 backdrop-blur-[2px] flex items-center justify-center"
      onClick={onClose}
    >
      <div
        className="bg-bg-secondary border border-border rounded-2xl w-[min(520px,94vw)] max-h-[90vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-accent" />
            <h2 className="text-[15px] font-semibold text-fg">完成任务 ✨</h2>
          </div>
          <button
            onClick={onClose}
            className="text-fg-muted hover:text-fg transition p-1 rounded hover:bg-bg-tertiary"
            title="关闭 (Esc)"
          >
            <X size={16} />
          </button>
        </div>

        {/* 任务标题快照（只读） */}
        <div className="px-5 pt-4 pb-1">
          <div className="text-[11px] uppercase tracking-[0.1em] text-fg-muted font-semibold mb-1.5">
            任务
          </div>
          <div className="text-[14px] text-fg-secondary px-3 py-2 rounded-md bg-bg-tertiary/50">
            {task.title}
          </div>
        </div>

        {/* outcome（必填） */}
        <div className="px-5 pt-3">
          <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-muted mb-1.5">
            结果描述 <span className="text-danger">*</span>
            <span className="ml-2 normal-case font-normal text-fg-muted/70 tracking-normal">
              这件事做完了什么、有什么结果
            </span>
          </label>
          <textarea
            ref={outcomeRef}
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
            placeholder="例如：用户反馈登录 bug 已修复，无复现，DAU 提升 5%"
            rows={2}
            className="w-full bg-bg border border-border rounded-md px-3 py-2 text-[14px] text-fg placeholder-fg-muted/60 focus:outline-none focus:border-accent resize-none"
          />
        </div>

        {/* cv（必填） */}
        <div className="px-5 pt-3">
          <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-muted mb-1.5">
            CV 成就陈述 <span className="text-danger">*</span>
            <span className="ml-2 normal-case font-normal text-fg-muted/70 tracking-normal">
              动词开头，含结果/影响
            </span>
          </label>
          <textarea
            value={cv}
            onChange={(e) => setCv(e.target.value)}
            placeholder="例如：定位并修复高优先级登录鉴权 bug，消除用户阻塞，当日上线验证"
            rows={3}
            className="w-full bg-bg border border-border rounded-md px-3 py-2 text-[14px] text-fg placeholder-fg-muted/60 focus:outline-none focus:border-accent resize-none"
          />
        </div>

        {/* reflection（可选） */}
        <div className="px-5 pt-3">
          <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-muted mb-1.5">
            复盘反思 <span className="normal-case font-normal text-fg-muted/70 tracking-normal">（可选）</span>
          </label>
          <textarea
            value={reflection}
            onChange={(e) => setReflection(e.target.value)}
            placeholder="这次有什么收获或教训..."
            rows={2}
            className="w-full bg-bg border border-border rounded-md px-3 py-2 text-[14px] text-fg placeholder-fg-muted/60 focus:outline-none focus:border-accent resize-none"
          />
        </div>

        {/* cv_status */}
        <div className="px-5 pt-3">
          <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-muted mb-1.5">
            CV 状态
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setCvStatus("ready")}
              className={`flex-1 px-3 py-2 rounded-md text-[13px] border transition ${
                cvStatus === "ready"
                  ? "bg-success/10 border-success text-success"
                  : "bg-bg border-border text-fg-muted hover:text-fg"
              }`}
            >
              ✅ 已有具体成果，直接入库
            </button>
            <button
              type="button"
              onClick={() => setCvStatus("pending")}
              className={`flex-1 px-3 py-2 rounded-md text-[13px] border transition ${
                cvStatus === "pending"
                  ? "bg-warning/10 border-warning text-warning"
                  : "bg-bg border-border text-fg-muted hover:text-fg"
              }`}
            >
              ⏳ 结果待补充，先存草稿
            </button>
          </div>
          {cvStatus === "pending" && (
            <div className="mt-2 text-[11px] text-fg-muted leading-relaxed">
              pending 项不会丢 — 后续在成就库点编辑可补全数据后升级为 ready。
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-4 mt-3 border-t border-border">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-[13px] text-fg-muted hover:text-fg rounded-md hover:bg-bg-tertiary transition"
          >
            取消
          </button>
          <button
            onClick={submit}
            disabled={!outcome.trim() || !cv.trim() || submitting}
            className="px-4 py-1.5 text-[13px] font-medium bg-accent text-black rounded-md hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-1.5"
          >
            <Check size={13} strokeWidth={2.5} />
            {submitting ? "沉淀中..." : "沉淀成就"}
          </button>
        </div>
      </div>
    </div>
  );
}
