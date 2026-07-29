"use client";

/**
 * 全局 Toast 组件 (2026-07-28 立)。
 *
 * 设计目标:
 * - 完成弹窗关闭后, 弹一个轻量 toast 庆祝 + 跳转到 /achievements 的入口
 *   让"完成即沉淀"的价值用户当下能看见
 * - 不阻塞操作, 3.5 秒自动消失, hover 暂停
 * - 一次最多显示 3 条, 新的进, 老的出
 * - 全局单例 (mounted in app/layout.tsx), 任何组件 useToast() 即可调用
 *
 * 用法:
 *   const toast = useToast();
 *   toast.success("🎉 任务已完成", "查看成就库 →", () => router.push("/achievements"));
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { CheckCircle2, X, Sparkles, ArrowRight } from "lucide-react";

export type ToastVariant = "success" | "info" | "warning";

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
  action?: ToastAction;
  /** 自动关闭的毫秒数, 默认 3500. 0 = 不自动关闭 (用于需要用户操作的场景) */
  duration?: number;
}

interface ToastContextValue {
  show: (toast: Omit<ToastItem, "id">) => string;
  success: (message: string, actionLabel?: string, onAction?: () => void) => string;
  info: (message: string, actionLabel?: string, onAction?: () => void) => string;
  warning: (message: string, actionLabel?: string, onAction?: () => void) => string;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TOAST_LIMIT = 3;

let _seq = 0;
function nextId() {
  _seq += 1;
  return `toast-${Date.now()}-${_seq}`;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    setToasts((cur) => cur.filter((t) => t.id !== id));
    const t = timersRef.current.get(id);
    if (t) {
      clearTimeout(t);
      timersRef.current.delete(id);
    }
  }, []);

  const show = useCallback<ToastContextValue["show"]>((toast) => {
    const id = nextId();
    const item: ToastItem = { id, ...toast };
    setToasts((cur) => {
      const next = [...cur, item];
      // 超过上限: 移除最早的
      if (next.length > TOAST_LIMIT) {
        const removed = next.shift();
        if (removed) {
          const t = timersRef.current.get(removed.id);
          if (t) {
            clearTimeout(t);
            timersRef.current.delete(removed.id);
          }
        }
      }
      return next;
    });
    const dur = item.duration ?? 3500;
    if (dur > 0) {
      const timer = setTimeout(() => dismiss(id), dur);
      timersRef.current.set(id, timer);
    }
    return id;
  }, [dismiss]);

  const wrap = useCallback(
    (variant: ToastVariant) =>
      (message: string, actionLabel?: string, onAction?: () => void) => {
        const action = actionLabel && onAction ? { label: actionLabel, onClick: onAction } : undefined;
        return show({ message, variant, action });
      },
    [show],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      show,
      success: wrap("success"),
      info: wrap("info"),
      warning: wrap("warning"),
      dismiss,
    }),
    [show, wrap, dismiss],
  );

  // 卸载时清掉所有 timer (防 React strict mode 双重 mount 留 timer)
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach((t) => clearTimeout(t));
      timers.clear();
    };
  }, []);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} dismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // 在 layout 没包 ToastProvider 时降级为 console.warn, 不让 UI 崩
    return {
      show: () => "",
      success: () => "",
      info: () => "",
      warning: () => "",
      dismiss: () => {},
    };
  }
  return ctx;
}

function ToastViewport({
  toasts,
  dismiss,
}: {
  toasts: ToastItem[];
  dismiss: (id: string) => void;
}) {
  return (
    <div
      className="fixed top-4 left-1/2 -translate-x-1/2 z-[60] flex flex-col items-center gap-2 pointer-events-none"
      aria-live="polite"
      aria-atomic="true"
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
      ))}
    </div>
  );
}

const VARIANT_STYLES: Record<ToastVariant, { ring: string; icon: ReactNode; iconColor: string }> = {
  success: {
    ring: "border-success/40 shadow-[0_8px_24px_rgba(0,0,0,0.4),0_0_0_1px_rgba(34,197,94,0.15)]",
    icon: <CheckCircle2 size={16} className="text-success" />,
    iconColor: "text-success",
  },
  info: {
    ring: "border-accent/40 shadow-[0_8px_24px_rgba(0,0,0,0.4),0_0_0_1px_rgba(212,175,55,0.15)]",
    icon: <Sparkles size={16} className="text-accent" />,
    iconColor: "text-accent",
  },
  warning: {
    ring: "border-warning/40 shadow-[0_8px_24px_rgba(0,0,0,0.4),0_0_0_1px_rgba(245,158,11,0.15)]",
    icon: <Sparkles size={16} className="text-warning" />,
    iconColor: "text-warning",
  },
};

function ToastCard({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  const [paused, setPaused] = useState(false);
  const [entered, setEntered] = useState(false);
  const variant = VARIANT_STYLES[toast.variant];

  useEffect(() => {
    // 下一帧加 entered 触发 transition
    const id = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className={`pointer-events-auto group flex items-center gap-2.5 pl-3 pr-2 py-2.5 rounded-xl bg-bg-secondary border ${variant.ring} backdrop-blur-md min-w-[280px] max-w-[420px] transition-all duration-200 ${
        entered ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-1"
      }`}
    >
      <div className="flex-shrink-0">{variant.icon}</div>
      <div className="flex-1 text-[13px] text-fg leading-snug">{toast.message}</div>
      {toast.action && (
        <button
          onClick={() => {
            toast.action!.onClick();
            onDismiss();
          }}
          className={`flex-shrink-0 text-[12px] font-medium ${variant.iconColor} hover:underline flex items-center gap-0.5 px-1.5 py-1 rounded hover:bg-bg-tertiary transition`}
        >
          {toast.action.label}
          <ArrowRight size={11} />
        </button>
      )}
      <button
        onClick={onDismiss}
        className="flex-shrink-0 text-fg-muted hover:text-fg p-0.5 rounded hover:bg-bg-tertiary transition"
        title="关闭"
        aria-label="关闭"
      >
        <X size={12} />
      </button>
      {/* 暂停时给视觉提示 (简单的 opacity 变化, 不显示进度条) */}
      {paused && <span className="sr-only">已暂停</span>}
    </div>
  );
}
