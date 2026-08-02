"use client";

/**
 * OnboardingTooltip — 新用户首次访问 3 步引导 (2026-08-01 立)
 *
 * 3 步:
 * 1. 建项目 — "在右栏对话里说「建一个项目：X」"
 * 2. 加任务 — "在右栏对话里说「加个任务：X」"
 * 3. 完成沉淀 — "完成时弹 4 字段弹窗, 写结果 + 沉淀成就"
 *
 * 行为:
 * - localStorage `cockpit_onboarded=true` 标记, 第二次访问不显示
 * - 每步可点"下一步" / "跳过" 推进
 * - 走完 3 步或点"完成" 后设置 onboarded, 永不再显示
 * - 用户可主动"重新引导" (留个出口, e.g. settings 页"重看引导"按钮)
 *
 * 哲学 (lesson #19 "新用户冷启动"):
 * - 反讽文案 + 抽象 CTA = 用户 30 秒内流失
 * - 3 步具体动作 + 每步可验证 = 用户知道下一步干啥
 * - localStorage 标记避免"老用户被反复弹"
 *
 * 实现:
 * - 浮层覆盖 MainBoard 主区 (z-50)
 * - 简单 modal 形态 (不像 popover 那样锚定元素, 第一次访问没"建项目按钮" 等锚点)
 * - 3 步切换 + 进度点 (1/2/3)
 */

import { useEffect, useState } from "react";
import { X, ArrowRight, Check, MessageSquare, Plus, Sparkles } from "lucide-react";
import { useToast } from "./Toast";

const STORAGE_KEY = "cockpit_onboarded";

interface Step {
  emoji: string;
  title: string;
  body: string;
  icon: React.ReactNode;
}

const STEPS: Step[] = [
  {
    emoji: "📁",
    title: "建一个项目",
    body: "在右栏对话里说「建一个项目：我的第一个项目」",
    icon: <Plus size={14} />,
  },
  {
    emoji: "✅",
    title: "加一个任务",
    body: "在右栏对话里说「加个任务：完成 XX」, 任务会出现在看板",
    icon: <MessageSquare size={14} />,
  },
  {
    emoji: "✨",
    title: "完成 + 沉淀",
    body: "完成任务会弹窗, 写下结果 + 自动沉淀成「成就」。未来写周报直接用",
    icon: <Sparkles size={14} />,
  },
];

export function OnboardingTooltip() {
  const [open, setOpen] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);
  const toast = useToast();

  useEffect(() => {
    try {
      const done = localStorage.getItem(STORAGE_KEY);
      if (!done) {
        // 延迟 1s 弹出, 等页面加载完不抢注意力
        setTimeout(() => setOpen(true), 1000);
      }
    } catch {
      /* 隐私模式, 假设已 onboarded */
    }
  }, []);

  const finish = (skipped: boolean) => {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
    setOpen(false);
    if (skipped) {
      toast.success("下次还会再问你", "重新打开 cockpit 看到引导");
    }
  };

  const next = () => {
    if (stepIdx < STEPS.length - 1) {
      setStepIdx(stepIdx + 1);
    } else {
      finish(false);
    }
  };

  if (!open) return null;

  const step = STEPS[stepIdx];
  const isLast = stepIdx === STEPS.length - 1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) finish(true);
      }}
    >
      <div className="bg-bg border border-border rounded-2xl shadow-2xl max-w-md w-full p-6 relative">
        {/* 关闭按钮 */}
        <button
          onClick={() => finish(true)}
          className="absolute top-3 right-3 text-fg-muted hover:text-fg transition p-1 rounded hover:bg-bg-tertiary"
          title="跳过引导"
        >
          <X size={16} />
        </button>

        {/* 步骤指示器 */}
        <div className="flex items-center justify-center gap-1.5 mb-4">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all ${
                i === stepIdx
                  ? "w-8 bg-accent"
                  : i < stepIdx
                  ? "w-1.5 bg-accent/40"
                  : "w-1.5 bg-fg-muted/30"
              }`}
            />
          ))}
        </div>

        {/* 步骤内容 */}
        <div className="text-center space-y-3 py-2">
          <div className="text-[40px]">{step.emoji}</div>
          <h2 className="text-[18px] font-semibold text-fg flex items-center justify-center gap-2">
            {step.icon}
            {stepIdx + 1}. {step.title}
          </h2>
          <p className="text-[13px] text-fg-secondary leading-relaxed">
            {step.body}
          </p>
        </div>

        {/* 操作按钮 */}
        <div className="flex items-center justify-between gap-2 mt-6">
          <button
            onClick={() => finish(true)}
            className="text-[12px] text-fg-muted hover:text-fg transition px-3 py-1.5"
          >
            跳过引导
          </button>
          <button
            onClick={next}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md text-[13px] font-semibold bg-accent text-black hover:bg-accent-hover transition"
          >
            {isLast ? (
              <>
                <Check size={13} />
                开始使用
              </>
            ) : (
              <>
                下一步
                <ArrowRight size={13} />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

/** 工具: 重置 onboarded 标记 (settings 页"重看引导" 用) */
export function resetOnboarding(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
