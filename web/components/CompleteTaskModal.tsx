"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { X, Sparkles, Check, ChevronDown, Loader2, AlertCircle, MessageCircleQuestion, Plus, RotateCcw } from "lucide-react";
import type { Task, CVStatus } from "@/lib/api";
import { api } from "@/lib/api";
import { classifyTaskTitle, getGuidance, type TaskCategory } from "@/lib/taskGuidance";

/**
 * 完成任务弹窗（v4 — 2026-07-30 加任务引导 + AI 追问）。
 *
 * 演进历史:
 *   v1: 4 字段全显示 (outcome / cv / reflection / cv_status) — 完成时摩擦最大
 *   v2: 折叠 cv_status + reflection
 *   v3 (2026-07-28): 砍到 1 必填 (outcome) + cv 智能预填 + ✨ 润色按钮
 *       → 解决"完成时刻摩擦" 痛点 (lesson #14)
 *   v4 (本次, 2026-07-30): 加"任务标题分类 → 引导卡片 + 动态 placeholder" + "AI 追问 (follow_up_questions)"
 *       → 解决"动作≠价值" 痛点 (lesson #15):
 *         用户写"完成 PRD" 这种抽象任务, 不知道怎么产出有价值的 outcome / cv
 *         新设计:
 *           - 弹窗根据 task.title 自动分类 (artifact/fix/discussion/research/generic)
 *           - outcome 下方显示轻量引导卡片 (emoji + label + 4 维度 + 1-2 follow-up chip)
 *           - outcome placeholder 动态化 (按类型给具体示例)
 *           - "✨ 润色" 时 LLM 如觉得信息不够, 返 1-2 个追问 questions
 *           - 追问以 chip 形式展示在 cv 框上方, 用户点 chip 把问题追加到 outcome
 *             (再点润色, LLM 看到补全的信息会返更好的 cv)
 *           - 形成"outcome → AI 追问 → 补全 → 再润色" 的对话闭环
 *
 * 哲学:
 *   弹窗不只是"收集字段", 更是"帮用户回忆价值" 的引导工具。
 *   用户当下只记得"动作", 弹窗主动给"价值维度" 和"追问", 帮他把动作翻译成价值。
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
    // 2026-08-01: LLM 主动追问 (polish 拿到的), 落库到 follow_up_questions
    follow_up_questions?: string[];
  }) => Promise<void>;
}) {
  // 任务分类 + 引导文案 (按 task.title 静态决定, 弹窗打开一次后不变)
  const taskCategory: TaskCategory = useMemo(
    () => classifyTaskTitle(task.title),
    [task.title],
  );
  const guidance = useMemo(() => getGuidance(taskCategory), [taskCategory]);

  const [outcome, setOutcome] = useState("");
  const [cv, setCv] = useState(`完成「${task.title}」`);
  const [reflection, setReflection] = useState("");
  const [cvStatus, setCvStatus] = useState<CVStatus>("ready");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showGuidance, setShowGuidance] = useState(true); // 引导卡片默认展开, 用户可关
  const [submitting, setSubmitting] = useState(false);
  const [polishing, setPolishing] = useState(false);
  const [polishError, setPolishError] = useState<string | null>(null);
  // LLM 主动追问 (2026-07-30 立): 信息不够具体时, LLM 返 1-2 个 follow_up_questions
  const [followUpQuestions, setFollowUpQuestions] = useState<string[]>([]);
  // outcome 框高亮 (2026-07-30 立, v4.1): 追问 chip 追加后让 outcome 框闪一下, 用户知道追加到了
  const [outcomeHighlight, setOutcomeHighlight] = useState(false);
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

  // ===== v0.3.1 主动建议机制（2026-08-02 立）=====
  // 痛点: outcome 写完后, 用户经常忘记点"润色"按钮, cv 就停在 `完成「${title}」` 兜底,
  //       沉淀质量肉眼可见低. → outcome 停笔 1.5s 后自动调 polishCv, 给 ghost 建议.
  // 关键: 不直接替换 cv, 用户可"采纳" / "忽略", 保留控制权.
  // 触发条件: outcome >= 30 字 + 用户没主动忽略 + 没在手动润色
  const [autoSuggestedCv, setAutoSuggestedCv] = useState<string | null>(null);
  const [autoPolishing, setAutoPolishing] = useState(false);
  const [suggestionDismissed, setSuggestionDismissed] = useState(false);

  useEffect(() => {
    const o = outcome.trim();
    if (o.length < 30 || suggestionDismissed || polishing) {
      return;
    }
    const timer = setTimeout(async () => {
      try {
        setAutoPolishing(true);
        const res = await api.polishCv(task.title, o);
        if (res.polished && res.cv && res.cv !== cv) {
          setAutoSuggestedCv(res.cv);
        }
      } catch {
        // 静默失败 — 手动润色按钮有 toast 提示
      } finally {
        setAutoPolishing(false);
      }
    }, 1500);
    return () => clearTimeout(timer);
  }, [outcome, task.title, suggestionDismissed, polishing, cv]);

  const acceptSuggestion = () => {
    if (autoSuggestedCv) {
      setCv(autoSuggestedCv);
      setAutoSuggestedCv(null);
      setSuggestionDismissed(true);
    }
  };
  const dismissSuggestion = () => {
    setAutoSuggestedCv(null);
    setSuggestionDismissed(true);
  };

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
      // 2026-08-01: 把 LLM 主动追问 (polish 拿到的) 传给后端, 落库到 follow_up_questions
      //   - 用户在 /achievements/follow-up 页可以补全
      //   - 补全后 cv_status 升级 ready (Reminders 端点用来扫描待补全)
      await onSave({
        outcome: o,
        cv: c,
        reflection: reflection.trim(),
        cv_status: cvStatus,
        follow_up_questions: followUpQuestions,
      });
    } finally {
      setSubmitting(false);
    }
  };

  // ✨ AI 润色: 把 outcome 转成 CV 风格的成就陈述
  // 2026-07-30 增强: 同时接收 LLM 主动追问的 follow_up_questions
  // 2026-08-02 协调 (v0.3.1): 手动润色时, 清空自动建议 (用户在管了, 别再打扰)
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
      // 手动润色 = 用户在管了, 关掉自动建议避免双源冲突
      setAutoSuggestedCv(null);
      setSuggestionDismissed(true);
      // 保留 LLM 的追问 (覆盖之前的, 因为是基于新 outcome 重新判断的)
      setFollowUpQuestions(res.follow_up_questions ?? []);
    } catch (e) {
      // 失败: 保留当前 cv (兜底), 给个轻量提示
      setPolishError(e instanceof Error ? e.message : "润色失败, 保留原文");
      setTimeout(() => setPolishError(null), 3000);
    } finally {
      setPolishing(false);
    }
  };

  // 把追问追加到 outcome 末尾 (用户填了答案后, 下次润色会拿到更完整的 outcome)
  const appendFollowUp = (q: string) => {
    const sep = outcome.trim() ? "\n" : "";
    const newOutcome = `${outcome}${sep}【${q}】`;
    setOutcome(newOutcome);
    setFollowUpQuestions((prev) => prev.filter((item) => item !== q));
    // 重新 focus outcome 框, 让用户接着打字
    setTimeout(() => outcomeRef.current?.focus(), 50);
    // 视觉反馈: outcome 框临时高亮 1.2s, 让用户知道追加成功了 (2026-07-30 立)
    setOutcomeHighlight(true);
    setTimeout(() => setOutcomeHighlight(false), 1200);
  };

  // 重置 CV 框到默认值 (2026-07-30 立, v4.1 UX 残留)
  // 场景: 用户润色后想看默认 `完成「title」` 兜底, 不用手动删 CV 文本
  const resetCv = () => {
    setCv(`完成「${task.title}」`);
  };

  // CV 是否已经不是默认值 (决定是否显示重置按钮)
  const isCvModified = cv !== `完成「${task.title}」`;

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
            placeholder={guidance.placeholder}
            rows={2}
            className={
              "w-full bg-bg border rounded-md px-3 py-2 text-[14px] text-fg placeholder-fg-muted/60 focus:outline-none focus:border-accent resize-none transition-colors " +
              (outcomeHighlight ? "border-accent ring-2 ring-accent/30" : "border-border")
            }
          />

          {/* ✨ 润色按钮行 (2026-07-30 改位置: 移到 outcome 下方)
              关键: 按钮要贴着行动目标 outcome, 不是贴着 CV 输出框
              之前位置 (CV 框旁) 让用户误以为按钮操作 CV, 实际流程是 outcome → CV */}
          <div className="mt-2 flex items-center justify-between gap-2">
            <span className="text-[10.5px] text-fg-muted/80 flex items-center gap-1">
              <span aria-hidden>↓</span>
              <span>改写成下方 CV 框</span>
              {!outcome.trim() && (
                <span className="text-fg-muted/60">· 先填结果描述</span>
              )}
            </span>
            <button
              type="button"
              onClick={polish}
              disabled={polishing || !outcome.trim()}
              className={
                "text-[11px] px-2.5 py-1 rounded transition flex items-center gap-1 " +
                (polishing || !outcome.trim()
                  ? "bg-bg-tertiary text-fg-muted cursor-not-allowed"  // disabled: 灰底灰字, 强对比
                  : "bg-accent/15 text-accent hover:bg-accent/25")  // enabled: accent 色调
              }
              title={
                outcome.trim()
                  ? "基于「结果描述」润色成下方 CV 框"
                  : "先在「结果描述」框写点东西才能润色"
              }
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
        </div>

        {/* 任务引导卡片 (2026-07-30 立, lesson #15):
            按 task.title 分类, 给用户"价值维度" 提示, 帮用户回忆动作背后的价值 */}
        {showGuidance && (
          <div className="px-5 pt-2.5">
            <div className="rounded-md bg-accent/5 border border-accent/20 px-3 py-2.5">
              <div className="flex items-center justify-between mb-1.5">
                <div className="text-[11px] text-fg-secondary flex items-center gap-1.5">
                  <span className="text-[13px] leading-none">{guidance.emoji}</span>
                  <span className="font-medium">{guidance.label}</span>
                  <span className="text-fg-muted">· 试试从这些角度写</span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowGuidance(false)}
                  className="text-fg-muted hover:text-fg p-0.5 rounded transition"
                  title="隐藏引导"
                >
                  <X size={11} />
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {guidance.dimensions.map((dim) => (
                  <span
                    key={dim}
                    className="text-[10.5px] px-1.5 py-0.5 rounded bg-bg/60 border border-border text-fg-muted"
                  >
                    {dim}
                  </span>
                ))}
              </div>
              <div className="text-[10.5px] text-fg-muted mt-1.5">
                写不出来？点上方「结果描述」旁的 ✨ 润色，AI 会主动问你几个关键问题。
              </div>
            </div>
          </div>
        )}

        {/* LLM 主动追问 (2026-07-30 立, lesson #15):
            polish 完后, 如果 LLM 觉得 outcome 不够具体, 会返 1-2 个追问.
            点 chip 把问题追加到 outcome 末尾, 用户填答案后下次润色会拿到更完整的 cv. */}
        {followUpQuestions.length > 0 && (
          <div className="px-5 pt-2.5">
            <div className="rounded-md bg-info/10 border border-info/30 px-3 py-2.5">
              <div className="flex items-center justify-between mb-1.5">
                <div className="text-[11px] text-info font-medium flex items-center gap-1.5">
                  <MessageCircleQuestion size={12} />
                  AI 想问你几个问题帮你补全 (点追加到结果描述)
                </div>
                <button
                  type="button"
                  onClick={() => setFollowUpQuestions([])}
                  className="text-fg-muted hover:text-fg p-0.5 rounded transition"
                  title="收起追问"
                >
                  <X size={11} />
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {followUpQuestions.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => appendFollowUp(q)}
                    className="text-[11px] px-2 py-1 rounded bg-bg border border-info/30 text-info hover:bg-info/15 transition flex items-center gap-1"
                  >
                    <Plus size={9} />
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* v0.3.1 主动建议区 (2026-08-02 立):
            outcome 停笔 1.5s 后自动调 polishCv, 建议以 ghost 形式展示, 用户采纳或忽略.
            位置: 放在 CV 框**上方** (不是 outcome 旁) — 用户视线从 outcome 移到 CV 框时看到建议,
            跟原"✨ 润色"按钮形成"主动建议 + 手动精修"双轨. */}
        {autoSuggestedCv && (
          <div className="px-5 pt-3">
            <div className="rounded-md bg-accent/8 border border-accent/25 px-3 py-2.5">
              <div className="flex items-center justify-between mb-1.5">
                <div className="text-[11px] text-accent font-medium flex items-center gap-1.5">
                  <Sparkles size={12} />
                  AI 建议 (试用)
                  {autoPolishing && <Loader2 size={10} className="animate-spin" />}
                  <span className="font-normal text-fg-muted/80 tracking-normal">· 不用你点润色按钮了</span>
                </div>
                <button
                  type="button"
                  onClick={dismissSuggestion}
                  className="text-fg-muted hover:text-fg p-0.5 rounded transition"
                  title="关闭建议"
                >
                  <X size={11} />
                </button>
              </div>
              <div className="text-[12.5px] text-fg-secondary italic mb-2 leading-relaxed">
                {autoSuggestedCv}
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={acceptSuggestion}
                  className="text-[11px] px-2.5 py-1 rounded bg-accent/20 text-accent hover:bg-accent/30 transition flex items-center gap-1"
                >
                  <Check size={10} />
                  采纳
                </button>
                <button
                  type="button"
                  onClick={dismissSuggestion}
                  className="text-[11px] px-2.5 py-1 rounded text-fg-muted hover:text-fg-secondary hover:bg-bg-tertiary transition"
                >
                  忽略
                </button>
                <span className="text-[10px] text-fg-muted/70 ml-auto">
                  也可手动改 CV 框, 建议会自动消失
                </span>
              </div>
            </div>
          </div>
        )}

        {/* CV 区域 — AI 润色结果 (输出, 不是输入) */}
        <div className="px-5 pt-3">
          <div className="flex items-center justify-between mb-1.5">
            <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-muted">
              CV 成就陈述
              <span className="ml-2 normal-case font-normal text-fg-muted/70 tracking-normal">
                AI 润色结果 · 可手动改
              </span>
            </label>
            {/* 重置按钮: 仅在 cv 已被修改时显示 (2026-07-30 立, v4.1 UX 残留) */}
            {isCvModified && (
              <button
                type="button"
                onClick={resetCv}
                className="text-[10.5px] text-fg-muted hover:text-fg-secondary flex items-center gap-1 transition"
                title="重置 CV 到默认值 「完成「${task.title}」」"
              >
                <RotateCcw size={10} />
                重置
              </button>
            )}
          </div>
          <textarea
            value={cv}
            onChange={(e) => setCv(e.target.value)}
            rows={2}
            className="w-full bg-bg border border-border rounded-md px-3 py-2 text-[13px] text-fg-secondary placeholder-fg-muted/60 focus:outline-none focus:border-accent resize-none"
            placeholder={
              outcome.trim()
                ? "例如：定位并修复高优先级登录鉴权 bug, 消除用户阻塞, DAU 提升 5%"
                : "先在上方「结果描述」框写点东西，然后点上方「润色」让 AI 帮你改写"
            }
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
