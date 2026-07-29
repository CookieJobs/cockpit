"use client";

import { useState, useEffect, useRef } from "react";
import { X, Sparkles, Check, ChevronDown, Loader2, AlertCircle } from "lucide-react";
import type { Task, CVStatus } from "@/lib/api";
import { api } from "@/lib/api";

/**
 * 完成任务弹窗（v3 — 2026-07-28 砍 4 字段为 1 必填）。
 *
 * 旧设计 (v1-v2): 4 字段全显示 (outcome / cv / reflection / cv_status)
 *   - 用户反馈: "感觉在写两遍" (outcome + cv 90% 重复)
 *   - 完成时多巴胺峰值, 4 字段问卷最差时机
 *   - 完成价值用户当下看不到, 弹窗变纯成本
 *
 * 新设计 (v3): 主流程只剩 outcome 1 必填
 *   - outcome: 用户填结果描述 (1-2 句)
 *   - cv: 智能预填 `完成「${title}」` + "✨ 润色" 按钮调 LLM 重写
 *     LLM 不可用 / 失败 → 静默 fallback, 不阻塞完成
 *   - reflection + cv_status: 折叠在"高级"区, 默认收起
 *
 * 设计哲学继承: "完成即沉淀" 还在, 只是从"问 4 个字段" 变成"沉淀默认就好, 你想润色再润色"
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
  const [cv, setCv] = useState(`完成「${task.title}」`);
  const [reflection, setReflection] = useState("");
  const [cvStatus, setCvStatus] = useState<CVStatus>("ready");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [polishing, setPolishing] = useState(false);
  const [polishError, setPolishError] = useState<string | null>(null);
  const outcomeRef = useRef<HTMLTextAreaElement>(null);

  // 打开时焦点 outcome
  useEffect(() => {
    setTimeout(() => outcomeRef.current?.focus(), 50);
  }, []);

  // 关闭弹窗（点击遮罩 / Esc）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !polishing) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, polishing]);

  const submit = async () => {
    const o = outcome.trim();
    const c = cv.trim();
    if (!o) {
      outcomeRef.current?.focus();
      return;
    }
    if (!c) return; // 理论上不会触发 (cv 有默认值), 留个保险
    setSubmitting(true);
    try {
      await onSave({ outcome: o, cv: c, reflection: reflection.trim(), cv_status: cvStatus });
    } finally {
      setSubmitting(false);
    }
  };

  // ✨ AI 润色: 把 outcome 转成 CV 风格的成就陈述
  const polish = async () => {
    if (!outcome.trim()) {
      outcomeRef.current?.focus();
      return;
    }
    setPolishing(true);
    setPolishError(null);
    try {
      const res = await api.polishCv(task.title, outcome);
      setCv(res.cv);
    } catch (e) {
      // 失败: 保留当前 cv (兜底), 给个轻量提示
      setPolishError(e instanceof Error ? e.message : "润色失败, 保留原文");
      setTimeout(() => setPolishError(null), 3000);
    } finally {
      setPolishing(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 backdrop-blur-[2px] flex items-center justify-center"
      onClick={onClose}
    >
      <div
        className="bg-bg-secondary border border-border rounded-2xl w-[min(480px,94vw)] max-h-[90vh] overflow-y-auto shadow-2xl"
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

        {/* outcome（必填）— 唯一主流程字段 */}
        <div className="px-5 pt-4">
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

        {/* CV 区域 — 智能预填 + 一键润色 */}
        <div className="px-5 pt-3">
          <div className="flex items-center justify-between mb-1.5">
            <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-muted">
              CV 成就陈述
              <span className="ml-2 normal-case font-normal text-fg-muted/70 tracking-normal">
                动词开头, 含结果/影响
              </span>
            </label>
            <button
              type="button"
              onClick={polish}
              disabled={polishing || !outcome.trim()}
              className="text-[11px] px-2 py-0.5 rounded bg-accent/15 text-accent hover:bg-accent/25 disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-1"
              title="让 AI 把结果描述改写成简历级别的成就陈述"
            >
              {polishing ? (
                <>
                  <Loader2 size={10} className="animate-spin" />
                  润色中
                </>
              ) : (
                <>
                  <Sparkles size={10} />
                  润色
                </>
              )}
            </button>
          </div>
          <textarea
            value={cv}
            onChange={(e) => setCv(e.target.value)}
            rows={2}
            className="w-full bg-bg border border-border rounded-md px-3 py-2 text-[13px] text-fg-secondary placeholder-fg-muted/60 focus:outline-none focus:border-accent resize-none"
            placeholder="例如：定位并修复高优先级登录鉴权 bug, 消除用户阻塞, DAU 提升 5%"
          />
          {polishError && (
            <div className="mt-1.5 text-[11px] text-warning flex items-center gap-1">
              <AlertCircle size={11} />
              {polishError}（已保留原文）
            </div>
          )}
        </div>

        {/* 高级选项 — 折叠, 默认收起 (reflection + cv_status) */}
        <div className="px-5 pt-3">
          <button
            type="button"
            onClick={() => setShowAdvanced((s) => !s)}
            className="text-[11px] text-fg-muted hover:text-fg-secondary flex items-center gap-1 transition"
          >
            <ChevronDown
              size={11}
              className={`transition-transform ${showAdvanced ? "rotate-180" : ""}`}
            />
            高级选项（可选）
          </button>

          {showAdvanced && (
            <div className="mt-3 space-y-3 pb-1">
              {/* reflection（可选） */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-muted mb-1.5">
                  复盘反思 <span className="normal-case font-normal text-fg-muted/70 tracking-normal">（可选）</span>
                </label>
                <textarea
                  value={reflection}
                  onChange={(e) => setReflection(e.target.value)}
                  placeholder="这次有什么收获或教训..."
                  rows={2}
                  className="w-full bg-bg border border-border rounded-md px-3 py-2 text-[13px] text-fg placeholder-fg-muted/60 focus:outline-none focus:border-accent resize-none"
                />
              </div>

              {/* cv_status — 三态 (2026-07-20 立 needs_data) */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-muted mb-1.5">
                  CV 状态
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setCvStatus("ready")}
                    className={`flex-1 px-2 py-2 rounded-md text-[12px] border transition ${
                      cvStatus === "ready"
                        ? "bg-success/10 border-success text-success"
                        : "bg-bg border-border text-fg-muted hover:text-fg"
                    }`}
                  >
                    <div>✅ ready</div>
                    <div className="text-[10px] mt-0.5 opacity-80">具体成果</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setCvStatus("needs_data")}
                    className={`flex-1 px-2 py-2 rounded-md text-[12px] border transition ${
                      cvStatus === "needs_data"
                        ? "bg-warning/10 border-warning text-warning"
                        : "bg-bg border-border text-fg-muted hover:text-fg"
                    }`}
                  >
                    <div>📊 needs data</div>
                    <div className="text-[10px] mt-0.5 opacity-80">差数据</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setCvStatus("pending")}
                    className={`flex-1 px-2 py-2 rounded-md text-[12px] border transition ${
                      cvStatus === "pending"
                        ? "bg-fg-muted/10 border-fg-muted text-fg-secondary"
                        : "bg-bg border-border text-fg-muted hover:text-fg"
                    }`}
                  >
                    <div>⏳ pending</div>
                    <div className="text-[10px] mt-0.5 opacity-80">先存草稿</div>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-4 mt-4 border-t border-border">
          <button
            onClick={onClose}
            disabled={polishing}
            className="px-3 py-1.5 text-[13px] text-fg-muted hover:text-fg rounded-md hover:bg-bg-tertiary transition disabled:opacity-40"
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
