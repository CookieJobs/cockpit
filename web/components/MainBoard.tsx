"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { createPortal } from "react-dom";
import useSWR from "swr";
import { listCommitments, isCommitment, toggleCommitment } from "@/lib/commitments";
import { useRouter } from "next/navigation";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { api, type Snapshot, type Project, type Task, type Achievement, type TaskStatus, statusIcon, dueColor, dueLabel, projectEmoji, relativeDate, daysAgoISO, type Priority, PRIORITY_BADGE_STYLES } from "@/lib/api";
import { Check, Trash2, ChevronRight, ChevronDown, Plus, CheckSquare, Square, X, Edit2, Settings, Calendar, Flag, MessageSquare, PanelRightOpen, Undo2, Archive, ArchiveRestore, Sparkles, GripVertical, Star, FileCode, FileText, Plug } from "lucide-react";
import { ChatWindow } from "./ChatWindow";
import { CompleteTaskModal } from "./CompleteTaskModal";
import { ThemeToggle } from "./ThemeToggle";
import { FollowUpReminder } from "./FollowUpReminder";
import { OnboardingTooltip } from "./OnboardingTooltip";
import { usePopover, usePopoverPosition } from "./Popover";
import { useToast } from "./Toast";
import Link from "next/link";
import { getChatLauncherClassName, getChatPanelClassName } from "@/lib/board-layout";
import { getVisualTone } from "@/lib/visual-system";

const CHAT_COLLAPSED_KEY = "cockpit_chat_collapsed";

export function MainBoard({ refreshKey }: { refreshKey: number }) {
  const { data: snapshot, mutate: refreshSnapshot } = useSWR<Snapshot>(
    "/api/snapshot",
    () => api.getSnapshot()
  );
  const { data: llmStatus } = useSWR("/api/llm/status", () => api.llmStatus(), {
    refreshInterval: 30000,
  });
  // 完成 toast (2026-07-28 立)
  const toast = useToast();
  const router = useRouter();

  // 2026-08-01 立: 今日承诺 — 从 localStorage 读 (commitments.ts), snapshot 变化时重新读
  //   不用 useState 因为 useEffect 一次性读就够, snapshot 变化用 refresh 触发
  const [commitments, setCommitments] = useState<string[]>([]);
  useEffect(() => {
    // SSR 安全: listCommitments() 内部 typeof window 兜底
    setCommitments(listCommitments());
  }, [snapshot]); // snapshot 变化时刷新 (完成/撤销时 doneIds 会变, 但 commitments 本身不变 — 简化)

  // doneIds = snapshot.done_tasks 的 id 集合 (算承诺进度用)
  const doneIds = useMemo(
    () => new Set(snapshot?.done_tasks.map((t) => t.id) ?? []),
    [snapshot?.done_tasks],
  );

  // 2026-08-02 改: 对话栏默认**折叠**, 主动展开才出现 ——
  //   v0.2 上线时默认 true (展开), 老用户已经习惯"进 cockpit 就看到 AI 在右栏"
  //   但 v0.4.4 之后的产品定位是 "沉淀成就 → 生成履历", AI 聊天是 secondary 入口,
  //   主页应该是清爽的项目 + 成就视图。投资者 Round 2 挑刺 #1: "ChatWindow 占
  //   1/3 屏, 用户进 cockpit 不想聊 AI, 就想看自己的项目"
  //
  //   行为:
  //   - 新用户 (localStorage 没 cockpit_chat_collapsed 标记) → 默认折叠 (清爽主页)
  //   - 老用户 (localStorage 存了 "0" 展开 / "1" 折叠) → 保留他们的选择
  //   - 切换栏后立即写 localStorage, 老用户不感知变化, 新用户清爽
  const [chatOpen, setChatOpen] = useState<boolean>(false);
  useEffect(() => {
    try {
      const stored = localStorage.getItem(CHAT_COLLAPSED_KEY);
      if (stored === "0") setChatOpen(true);
      if (stored === "1") setChatOpen(false);
    } catch {
      /* SSR / 隐私模式无 localStorage, 走默认折叠 */
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

  // 聚焦对话输入框 (2026-08-01 立): FocusSection 空状态 CTA 用
  //   - 如果对话栏折叠, 先展开
  //   - 50ms 后 dispatch 'cockpit:focus-chat' event, ChatWindow 监听调 textarea.focus()
  //   - 不用 forwardRef, 简单全局 event 模式
  const handleFocusChat = () => {
    if (!chatOpen) toggleChat();
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent("cockpit:focus-chat"));
    }, 80);
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

  // 2026-08-02 立 (投资人 Round 1 优化): 成就数字增加时 highlight 1.5s
  //   - 任务完成 → 沉淀成就 → readyCount +1 → 数字 + 背景 +1s 闪一下
  //   - 撤销成就 → readyCount -1 → 不闪 (负向反馈不抢眼)
  //   - 心理作用: "我刚刚干的事被记下来了, 数字看得见" — 完成 → 沉淀闭环可视化
  const [readyFlash, setReadyFlash] = useState(false);
  const prevReadyCountRef = useRef(readyCount);
  useEffect(() => {
    if (readyCount > prevReadyCountRef.current) {
      setReadyFlash(true);
      const t = setTimeout(() => setReadyFlash(false), 1500);
      prevReadyCountRef.current = readyCount;
      return () => clearTimeout(t);
    }
    prevReadyCountRef.current = readyCount;
  }, [readyCount]);

  return (
    <div className="flex h-screen bg-bg">
      {/* 左栏:项目 + 任务 — 主视图,占主空间 */}
      <div className="flex-1 min-w-0 border-r border-border flex flex-col bg-bg-secondary">
        <div className="px-4 py-3 sm:px-5 sm:py-4 border-b border-border flex items-center gap-3">
          <h1 className="shrink-0 text-[17px] font-semibold text-fg tracking-tight">
            Cockpit
          </h1>
          <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto whitespace-nowrap [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:gap-3">
            {/* LLM 状态徽章 */}
            {llmStatus && (
              <span
                className={`shrink-0 text-[11px] px-2 py-0.5 rounded-full font-medium ${
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
            {/* 待补追问徽章 (2026-08-01 立) - 拉 /api/reminders/pending, total=0 不显示 */}
            <FollowUpReminder />
            <Link
              href="/report"
              className="shrink-0 text-[12px] text-fg-secondary hover:text-fg transition px-2 py-1 rounded hover:bg-bg-tertiary flex items-center gap-1"
              title="周报/述职 workspace"
            >
              <Sparkles size={11} />
              写周报
            </Link>
            {/* 2026-08-01 立: PR 描述生成入口 (项目维度) */}
            <Link
              href="/pr"
              className="shrink-0 text-[12px] text-fg-secondary hover:text-fg transition px-2 py-1 rounded hover:bg-bg-tertiary flex items-center gap-1"
              title="从 ready 成就生成 GitHub PR 描述"
            >
              <FileCode size={11} />
              PR 描述
            </Link>
            {/* v0.4.2 立: 跨项目 CV 视图 (时间维度, 一次沉淀多次输出的"输出"端基础) */}
            <Link
              href="/cv"
              className="shrink-0 text-[12px] text-fg-secondary hover:text-fg transition px-2 py-1 rounded hover:bg-bg-tertiary flex items-center gap-1"
              title="跨项目 CV 视图 (按时间倒序拉所有 ready 成就)"
            >
              <FileText size={11} />
              CV 视图
            </Link>
            {/* 2026-08-02 v0.5a.1 强化: 接入中心是杀手功能 (Claude Code / Cursor / Trae 等 6 个
             *   AI Agent 能直接读 cockpit 数据), 但之前 nav 只用小 Plug 图标 + "集成" 文字,
             *   杀手功能埋没了。Round 4 强化:
             *   - 文字 "集成" → "⚡ AI 直连" (强调价值, 不是技术)
             *   - 颜色: text-fg-secondary → text-accent (亮起来, 跟其他 nav 区分)
             *   - 加红点 dot: 当 installed_count < total_count, 提醒"还没接入"
             *   - hover tooltip: 装上能干啥 (6 个 Agent 直接读 cockpit 数据)
             *   - 心理作用: 用户每次进 cockpit 都看到 "⚡ AI 直连" + 红点, 知道这是关键能力
             */}
            <IntegrationNavLink />
            <Link
              href="/achievements"
              className="shrink-0 text-[12px] text-fg-secondary hover:text-fg transition px-2 py-1 rounded hover:bg-bg-tertiary"
            >
              成就
            </Link>
            <Link
              href="/settings"
              className="shrink-0 text-fg-muted hover:text-fg transition p-1.5 rounded hover:bg-bg-tertiary"
              title="设置"
            >
              <Settings size={14} />
            </Link>
            {/* 2026-08-01 立: 主题切换 (light/dark), 跟 Settings 同位置同尺寸 */}
            <ThemeToggle />
          </div>
        </div>

        {/* 2026-08-02 立: 本期成就卡片 (投资人 Round 1 优化 — 5 秒 Wow 时刻)
         *
         * 升级: 原来是一条窄 counter text, 现在改成有视觉重量的卡片。
         * 目的: 用户进入 cockpit 第一眼看到 "我这段时间沉淀了 X 条成就" +
         *   "今日 +N" + "查看全部 →" — 把心理重心从"待办焦虑"切到"已有积累"。
         *
         * 设计决定:
         * - 大数字 readyCount (text-asset 28px) — 跟 "12 条成就" 文案对比明显
         * - 右侧 stack: 今日 +N (fg) + 待补 N (warning) + 待办 N (fg-muted)
         * - 底部: "查看全部 →" 链接到 /achievements — 闭环
         * - highlight 动画: readyCount +1 时 readyFlash=true, 数字 + 卡片背景闪
         *   accent 色 1.5s, 让用户看到 "我刚做的事被记下来了"
         * - 不动 FocusSection 顺序: 本卡片在 counter 条位置, 不进 overflow 滚动区
         */}
        <div
          data-testid="achievement-spotlight"
          className={`mx-4 mt-3 mb-2 px-4 py-3 rounded-lg border transition-colors duration-500 ${
            readyFlash
              ? getVisualTone("asset")
              : "bg-bg-tertiary border-border"
          }`}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-baseline gap-2 min-w-0">
              <strong className="text-[28px] font-bold tabular-nums leading-none text-asset transition-colors duration-500">
                {readyCount}
              </strong>
              <span className="text-[12px] text-fg-secondary">条已沉淀成就</span>
              {readyFlash && (
                <span
                  className="text-[10px] font-medium px-1.5 py-0.5 rounded border border-asset/40 text-fg animate-pulse"
                  data-testid="achievement-spotlight-flash"
                >
                  +1
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-[11px] text-fg-muted shrink-0">
              {doneTodayCount > 0 && (
                <span className="flex items-center gap-1">
                  <span className="text-fg-secondary">今日</span>
                  <strong className="text-fg tabular-nums">+{doneTodayCount}</strong>
                </span>
              )}
              {pendingCount > 0 && (
                <span className="flex items-center gap-1">
                  <span className="text-fg-secondary">待补</span>
                  <strong className="text-warning tabular-nums">{pendingCount}</strong>
                </span>
              )}
              {focusCount > 0 && (
                <span className="flex items-center gap-1">
                  <span className="text-fg-secondary">待办</span>
                  <strong className="text-fg tabular-nums">{focusCount}</strong>
                </span>
              )}
            </div>
          </div>
          {readyCount > 0 && (
            <Link
              href="/achievements"
              className="mt-2 inline-flex items-center gap-1 text-[11px] text-fg-secondary hover:text-asset transition group"
            >
              查看全部 {readyCount} 条成就
              <ChevronRight
                size={11}
                className="transition-transform group-hover:translate-x-0.5"
              />
            </Link>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-5 space-y-6">
          {snapshot && (
            <>
              {/* 2026-08-02 立: 今日已完成区移到 spotlight 卡片正下方, 跟"今日 +N" 指示器联动
               *   - 之前: DoneTodaySection 在 ProjectsSection + DoneAllSection 之后, 用户得滚到底
               *   - 现在: 紧跟 spotlight 卡片, 主页第一屏就能看到今天干了啥
               *   - 配合: spotlight 卡片副 stack 里的"今日 +N" 直接链接到这块
               *   - 折叠默认展开 (跟 lesson #14 4 字段摩擦同源: 已经积攒成就不藏, 直接给用户看)
               *   - 心理钩子: "我今天已经干了 N 件事" 比 "我还有 5 项没干" 强 10 倍
               */}
              <DoneTodaySection
                items={snapshot.done_today}
                expanded={doneExpanded}
                onToggle={() => setDoneExpanded((e) => !e)}
                onChange={refresh}
              />
              <FocusSection
                snapshot={snapshot}
                onChange={refresh}
                onRequestComplete={(t) => setCompletingTask(t)}
                onRequestFocusChat={handleFocusChat}
                commitments={commitments}
                doneIds={doneIds}
              />
              <ProjectsSection
                snapshot={snapshot}
                onChange={refresh}
                onRequestComplete={(t) => setCompletingTask(t)}
                onRequestFocusChat={handleFocusChat}
              />
              <DoneAllSection
                items={snapshot.done_tasks}
                onChange={refresh}
              />
            </>
          )}
        </div>
      </div>

      {/* 新用户引导 (2026-08-01 立) - 首次访问弹 3 步引导, localStorage 标记 */}
      <OnboardingTooltip />

      {/* 完成任务弹窗 - 2026-07-28 v3 砍到 1 必填 (outcome) + CV 智能预填 + ✨ 润色按钮 */}
      {completingTask && (
        <CompleteTaskModal
          task={completingTask}
          onClose={() => setCompletingTask(null)}
          onSave={async (data) => {
            await api.completeTask(completingTask.id, data);
            setCompletingTask(null);
            // 庆祝 toast: 告知用户沉淀成功 + 跳转到成就库入口 (D 项)
            const readyAfter = (snapshot?.counts.achievementsReady ?? 0) + 1;
            toast.success(
              `🎉 已沉淀 · 成就库累计 ${readyAfter} 个 ready`,
              "查看成就库",
              () => router.push("/achievements"),
            );
            refresh();
          }}
        />
      )}

      {/* 右栏:对话窗口 - 折叠态:44px 窄条;展开态:w-[35%] 侧栏 */}
      {chatOpen ? (
        <div className={getChatPanelClassName()}>
          <ChatWindow onAction={refresh} onCollapse={() => toggleChat()} />
        </div>
      ) : (
        <button
          onClick={() => toggleChat()}
          className={getChatLauncherClassName()}
          title="展开对话"
        >
          <PanelRightOpen size={16} />
          <span
            className="hidden text-[10px] tracking-wider md:block"
            style={{ writingMode: "vertical-rl" }}
          >
            展开对话
          </span>
          <MessageSquare size={16} className="opacity-70 group-hover:opacity-100 md:mt-2 md:text-[12px]" />
        </button>
      )}
    </div>
  );
}

// 2026-08-02 v0.5a.1 立 + Round 4 强化: 主页 nav "⚡ AI 直连" 入口
//   - 拉 /api/integrations/status 拿 installed_count / total_count
//   - 红点: installed < total 提醒用户"还没接入"
//   - 装好所有: 不显示红点, 变 fg 颜色
//   - SWR refresh 30s, 用户去 /integrations 装好后回主页, dot 自动消失
//   - 单独组件是为了不被 MainBoard 重渲连累 (有 SWR 独立订阅)
function IntegrationNavLink() {
  const { data: status } = useSWR(
    "/api/integrations/status",
    () => api.integrationStatus(),
    { refreshInterval: 30000 },
  );

  const installed = status?.installed_count ?? 0;
  const total = status?.total_count ?? 6;  // fallback 6 (Claude Code / Cursor / Trae / Cline / Continue / WorkBuddy)
  const allInstalled = installed >= total && total > 0;
  const showDot = !allInstalled;  // 有 1 个没装就亮红点

  return (
    <Link
      href="/integrations"
      className="text-[12px] text-accent hover:text-accent-hover transition px-2 py-1 rounded hover:bg-bg-tertiary flex items-center gap-1 relative"
      title={
        allInstalled
          ? `已接入 ${installed}/${total} 个 AI Agent (Claude Code / Cursor / Trae / Cline / Continue / WorkBuddy)`
          : `把 cockpit 注册到 Claude Code / Cursor / Trae 等 ${total} 个 AI Agent, 让它们直接读你的项目 + 任务 + 成就 (当前 ${installed}/${total})`
      }
    >
      <Plug size={11} />
      <span>⚡ AI 直连</span>
      {showDot && (
        <span
          data-testid="integration-red-dot"
          className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-danger animate-pulse"
          aria-label={`${total - installed} 个 AI Agent 未接入`}
        />
      )}
    </Link>
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
  onRequestFocusChat,
  commitments,
  doneIds,
}: {
  snapshot: Snapshot;
  onChange: () => void;
  onRequestComplete: (task: Pick<Task, "id" | "title">) => void;
  onRequestFocusChat: () => void;
  // 2026-08-01 立: 今日承诺 (localStorage 持久化, 用户主动挑 N 个 task)
  commitments: string[];
  doneIds: Set<string>;
}) {
  // 找承诺的 Task 对象 (从 snapshot.projects[].tasks 里搜)
  const allActiveTasks: Task[] = useMemo(
    () => snapshot.projects.flatMap((p) => p.tasks),
    [snapshot.projects],
  );
  const taskById = useMemo(() => {
    const m = new Map<string, Task>();
    for (const t of allActiveTasks) m.set(t.id, t);
    return m;
  }, [allActiveTasks]);
  const committedTasks: Task[] = useMemo(
    () => commitments
      .map((id) => taskById.get(id))
      .filter((t): t is Task => !!t), // 过滤掉已删/已完成的
    [commitments, taskById],
  );
  const committedDone = committedTasks.filter((t) => doneIds.has(t.id)).length;
  const showProgress = commitments.length >= 1; // 有承诺就显示进度, 不用 >= 3 (避免空引导区)

  // 空状态判断
  if (snapshot.focus.length === 0 && committedTasks.length === 0) {
    // 2026-08-01: 删掉"所有任务都已收尾"反讽文案。
    //   区分两种空状态 — 新用户(没项目) vs 老用户(都完成了), 引导文案 + CTA 不同。
    const isNewUser = snapshot.projects.length === 0;
    return (
      <div>
        <SectionHeader title="今日聚焦" count={0} />
        <div className="px-1 py-6 text-center space-y-2">
          <div className="text-[20px]">{isNewUser ? "👋" : "🎉"}</div>
          <div className="text-[14px] text-fg-secondary font-medium">
            {isNewUser ? "还没有任务" : "今日聚焦都完成了"}
          </div>
          <div className="text-[12px] text-fg-muted">
            {isNewUser
              ? "在对话里试试「加个任务：完成 XX」"
              : "加新任务继续 — 在对话里说「加个任务」"}
          </div>
          <button
            onClick={onRequestFocusChat}
            className="mt-1 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium bg-accent/5 text-accent border border-accent/30 hover:bg-accent/10 transition"
          >
            {isNewUser ? "去对话添加任务" : "加新任务"}
          </button>
        </div>
      </div>
    );
  }

  // 区分承诺 vs focus: 承诺的优先显示
  const focusSet = new Set(snapshot.focus.map((f) => f.id));
  const focusNotCommitted = snapshot.focus.filter((f) => !commitments.includes(f.id));

  return (
    <div>
      <SectionHeader
        title="今日聚焦"
        count={commitments.length + focusNotCommitted.length}
        right={
          showProgress ? (
            <span className="text-[11px] text-fg-muted tabular-nums">
              承诺 {committedDone}/{commitments.length}
            </span>
          ) : undefined
        }
      />
      {/* 承诺进度条 */}
      {showProgress && (
        <div className="px-1 mb-2">
          <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
            <div
              className="h-full bg-accent transition-all"
              style={{
                width: `${commitments.length > 0 ? Math.round((committedDone / commitments.length) * 100) : 0}%`,
              }}
            />
          </div>
          {commitments.length < 3 && (
            <div className="text-[11px] text-fg-muted mt-1">
              挑 3 个任务加入今日承诺 — 在任务行的 ⋯ 菜单 / hover 时点 ⭐ 按钮
            </div>
          )}
        </div>
      )}
      {/* 承诺的任务 (优先) */}
      {committedTasks.length > 0 && (
        <div className="space-y-0.5 mb-1">
          {committedTasks.map((task) => (
            <FocusItem
              key={task.id}
              item={{
                id: task.id,
                project: task.project,
                title: task.title,
                priority: task.priority,
                due: task.due,
                blocked: task.blocked,
              }}
              isCommitment
              onRequestComplete={() => onRequestComplete({ id: task.id, title: task.title })}
            />
          ))}
        </div>
      )}
      {/* 系统 focus (未承诺的) */}
      {focusNotCommitted.length > 0 && (
        <div className="space-y-0.5">
          {focusNotCommitted.map((item) => (
            <FocusItem
              key={item.id}
              item={item}
              onRequestComplete={() => onRequestComplete(item)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FocusItem({
  item,
  onRequestComplete,
  isCommitment,
}: {
  item: Snapshot["focus"][number];
  onRequestComplete: () => void;
  // 2026-08-01 立: 该 task 是不是今日承诺 (高亮 + 左侧 ⭐ 标记)
  isCommitment?: boolean;
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
      } ${isCommitment ? "bg-accent/5 border-l-2 border-accent" : ""}`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onRequestComplete}
    >
      <div className="flex items-center gap-3">
        {/* 承诺标记 (2026-08-01 立) - 左侧 ⭐ 视觉锚点 */}
        {isCommitment && (
          <span
            className="flex-shrink-0 text-accent text-[12px]"
            title="今日承诺"
          >
            ⭐
          </span>
        )}

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
                        <span className="text-[10px] px-1.5 py-0 rounded bg-warning/5 text-warning font-medium flex-shrink-0">
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

function DoneAllSection({
  items,
  onChange,
}: {
  items: NonNullable<Snapshot["done_tasks"]>;
  onChange: () => void;
}) {
  // 2026-08-01 立: 全局"已完成 task" 折叠区 (跨 project, 不只是今天)
  //   旧版 task 完成即删, 用户"看回" 自己干的活要去 /achievements 才能找到
  //   新版 task 保留 (status=已完成), 主页底部加这个折叠区, 立刻看回所有 done
  //   - 默认收起 (done 多了不打扰主页)
  //   - 展开后按 completed_at desc 排 (最近完成的在前)
  //   - 每条带项目 emoji + 标题 + 撤销按钮
  const [expanded, setExpanded] = useState(false);
  if (!items || items.length === 0) return null;

  // 拿每个 task 对应的 achievement (task_id + date 是关键) — 简化: 调后端
  // 撤销走原 achievement 路径, 不用 task_id
  // 实际: 我们展示 task 但撤销是按 task_id 找最新 achievement, 简化展示
  return (
    <div className="rounded-lg border border-border bg-bg-secondary/50 overflow-hidden">
      <div
        className="px-3 py-2.5 flex items-center justify-between cursor-pointer hover:bg-bg-tertiary/40 transition select-none"
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex items-center gap-2">
          <ChevronRight
            size={12}
            strokeWidth={2}
            className={`text-fg-muted transition-transform flex-shrink-0 ${
              expanded ? "rotate-90" : ""
            }`}
          />
          <span className="text-[11px] uppercase tracking-[0.1em] text-fg-muted font-semibold">
            📦 已完成任务
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
          {items.map((t) => (
            <div key={t.id} className="px-3 py-2.5 group/item">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Check size={12} className="text-success flex-shrink-0" strokeWidth={2.5} />
                    {/* 项目 emoji — 跟 projectCard 头部一致 (复用 projectEmoji) */}
                    <span className="text-[12px] flex-shrink-0 opacity-70">
                      {projectEmoji(t.project)}
                    </span>
                    <span className="text-[13px] text-fg-muted line-through truncate">
                      {t.title}
                    </span>
                  </div>
                  {t.completed_at && (
                    <div className="text-[10px] text-fg-muted mt-1">
                      完成于 {t.completed_at}
                    </div>
                  )}
                </div>
                {/* 撤销按钮 (2026-08-01: 按 task.id 调后端, 后端找最近一条 achievement 撤销) */}
                <button
                  onClick={async (e) => {
                    e.stopPropagation();
                    if (!confirm(`撤销「${t.title}」的完成状态？任务会恢复到进行中。`)) return;
                    // 后端需要新端点: POST /api/tasks/{id}/undo 找最新 achievement 撤销
                    // 简化: 调 list_achievements 找该 task_id 对应的最新 achievement, 再 undo
                    // 实际: 我加新端点 /api/tasks/{id}/undo 走 storage.undo_by_task_id
                    try {
                      await api.undoTask(t.id);
                      onChange();
                    } catch (err) {
                      alert("撤销失败: " + (err instanceof Error ? err.message : err));
                    }
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
  );
}

function ProjectsSection({
  snapshot,
  onChange,
  onRequestComplete,
  onRequestFocusChat,
}: {
  snapshot: Snapshot;
  onChange: () => void;
  onRequestComplete: (task: Task) => void;
  onRequestFocusChat: () => void;
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

  // ===== 拖动排序 (2026-07-30 立) =====
  // 项目拖动是项目级, 跟 task 拖动互不干扰 (task 拖动在 ProjectCard 内部 DndContext)。
  // 策略: 乐观更新本地 snapshot.projects 立即重排, 调 api.reorderProjects, 失败回滚 + toast。
  // 间隔 10 存 sortOrder: 拖到中间 = (prev + next) / 2; 拖到首/尾 = 邻居 ±10。
  // 间隔耗尽 (diff < 1) 时批量重写, 但 N=10 项内的项目基本不会触发。
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleProjectDragEnd = async (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const projects = snapshot.projects;
    const oldIndex = projects.findIndex((p) => p.id === active.id);
    const newIndex = projects.findIndex((p) => p.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    // 计算新 sortOrder — 邻居中间值, 边缘 ±10
    const sortedArr = arrayMove(projects, oldIndex, newIndex);
    const prev = newIndex > 0 ? sortedArr[newIndex - 1].sort_order : null;
    const next = newIndex < sortedArr.length - 1 ? sortedArr[newIndex + 1].sort_order : null;
    let newOrder: number;
    if (prev === null && next === null) newOrder = 0;
    else if (prev === null) newOrder = (next as number) - 10;
    else if (next === null) newOrder = prev + 10;
    else newOrder = (prev + next) / 2;
    // 触发 onChange 让 snapshot 重新拉 (乐观更新也可以, 这里走最简: 让 SWR 拉新数据)
    try {
      await api.reorderProjects([{ id: active.id as string, sort_order: newOrder }]);
      onChange();
    } catch (err) {
      console.error("Failed to reorder project:", err);
      onChange(); // 拉回原状态
    }
    // 抑制 lint 警告: sortedArr 数组用于计算 newOrder, 不需要再 use
    void sortedArr;
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
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleProjectDragEnd}>
        <SortableContext
          items={snapshot.projects.map((p) => p.id).filter((id): id is string => !!id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-1.5">
            {snapshot.projects.map((p) => (
              <SortableProjectCard
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
              <div className="text-[13px] text-fg-muted px-3 py-4 text-center space-y-2">
                <div className="text-[20px]">📁</div>
                <div className="text-fg-secondary font-medium">还没有项目</div>
                <div className="text-[12px]">
                  在对话里试试「建一个项目：XX」
                </div>
                <button
                  onClick={onRequestFocusChat}
                  className="mt-1 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium bg-accent/5 text-accent border border-accent/30 hover:bg-accent/10 transition"
                >
                  去对话建项目
                </button>
              </div>
            )}
          </div>
        </SortableContext>
      </DndContext>

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

// ===== Sortable Wrappers (2026-07-30 拖动排序立) =====
//
// SortableProjectCard / SortableTaskRow 是拖动 wrapper, 内部 useSortable 拿 transform +
// handle props。ProjectCard / TaskRow 主体保持纯展示, 通过 dragHandle 接收 button 渲染。
//
// 设计: handle 在卡片内渲染, 不用 absolute 外挂, 避免 overflow-hidden 裁切。
// 触发区域: 整行 hover 时 opacity-0 → opacity-100 显示 handle, 平时不打扰。
// PointerSensor 5px activation distance: 防止 click 跟 drag 撞车 (用户想点但手抖一下)。

function SortableProjectCard(props: {
  project: Snapshot["projects"][number];
  expanded: boolean;
  onToggle: () => void;
  onChange: () => void;
  onRequestComplete: (task: Task) => void;
}) {
  const { project, expanded, onChange, ...rest } = props;
  const id = project.id || project.name;
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`relative ${isDragging ? "z-10 opacity-50" : ""}`}
    >
      <ProjectCard
        project={project}
        expanded={expanded}
        onChange={onChange}
        dragHandle={
          <button
            {...attributes}
            {...listeners}
            className="opacity-0 group-hover:opacity-60 hover:!opacity-100 w-5 h-5 flex items-center justify-center flex-shrink-0 text-fg-muted hover:text-fg rounded cursor-grab active:cursor-grabbing touch-none transition-opacity"
            title="拖动改顺序"
            aria-label="拖动项目"
            onClick={(e) => e.stopPropagation()}
          >
            <GripVertical size={12} />
          </button>
        }
        {...rest}
      />
    </div>
  );
}

function ProjectCard({
  project,
  expanded,
  onToggle,
  onChange,
  onRequestComplete,
  dragHandle,
}: {
  project: Snapshot["projects"][number];
  expanded: boolean;
  onToggle: () => void;
  onChange: () => void;
  onRequestComplete: (task: Task) => void;
  // 2026-07-30: 拖动句柄 (GripVertical button) 从 SortableProjectCard 注入
  dragHandle?: React.ReactNode;
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

  // ===== 任务拖动 (2026-07-30 立) =====
  // 项目内嵌独立 DndContext, 跟 ProjectsSection 外层互不干扰 (嵌套 DndContext
  // 各自独立 sensors, 拖 task 不会触发 project 拖动)。
  // sensors 在 ProjectCard 局部创建 (不能跟外层共享)。
  const taskSensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleTaskDragEnd = async (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const tasks = project.tasks;
    const oldIndex = tasks.findIndex((t) => t.id === active.id);
    const newIndex = tasks.findIndex((t) => t.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const sortedArr = arrayMove(tasks, oldIndex, newIndex);
    const prev = newIndex > 0 ? sortedArr[newIndex - 1].sort_order : null;
    const next = newIndex < sortedArr.length - 1 ? sortedArr[newIndex + 1].sort_order : null;
    let newOrder: number;
    if (prev === null && next === null) newOrder = 0;
    else if (prev === null) newOrder = (next as number) - 10;
    else if (next === null) newOrder = prev + 10;
    else newOrder = (prev + next) / 2;
    try {
      await api.reorderTasks([{ id: active.id as string, sort_order: newOrder }]);
      onChange();
    } catch (err) {
      console.error("Failed to reorder task:", err);
      onChange();
    }
    void sortedArr;
  };

  return (
    // 2026-08-01 v2 改: light/dark 双模式视觉层次
    //   light 模式: bg-bg (#ffffff 纯白) + 显式 border, 跟主区 wrapper
    //     (#f8fafc slate-50) 对比, 卡片"立"出来 (light 模式卡片**比主区亮**)
    //   dark 模式: dark:bg-bg-tertiary (#1e1e1e) + border, 跟主区 wrapper
    //     (#141414) 对比, 卡片也"立"出来 (dark 模式卡片**比主区亮**)
    //   关键: light/dark 模式里卡片都比主区 wrapper 亮, 视觉"凸"的方向一致,
    //     但实现上不能简单用 bg-bg (dark 模式 bg = #0a0a0a 跟 body 同色,
    //     卡片"沉"回去), 必须 conditional class。
    <div
      className={`rounded-xl overflow-hidden transition-all ${
        expanded
          ? "bg-bg dark:bg-bg-tertiary ring-1 ring-accent/60 border border-accent/40"
          : "bg-bg dark:bg-bg-tertiary border border-border hover:border-border-hover"
      }`}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <div className="group px-3 pt-2.5 pb-1.5 hover:bg-bg-tertiary/60 transition">
        {/* 标题行:chevron + name + count + 操作按钮 */}
        <div className="flex items-center gap-2.5">
          {/* 拖动句柄 (2026-07-30 立) — 平时 opacity-0 不打扰, group hover 时
              opacity-60 提示可拖, 自身 hover 时 opacity-100 强调。整行 click
              走 onToggle (展开/收起), 句柄 stopPropagation 阻止冒泡。 */}
          {dragHandle}
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
          <DndContext sensors={taskSensors} collisionDetection={closestCenter} onDragEnd={handleTaskDragEnd}>
            <SortableContext
              items={project.tasks.map((t) => t.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-0.5">
                {project.tasks.map((t) => (
                  <SortableTaskRow
                    key={t.id}
                    task={t}
                    onChange={onChange}
                    onRequestComplete={onRequestComplete}
                  />
                ))}
                {project.tasks.length === 0 && !addingTask && (
                  <div className="px-3 py-3 text-[13px] text-fg-muted text-center">
                    项目下还没有任务 — 在下面加一个
                  </div>
                )}
              </div>
            </SortableContext>
          </DndContext>
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
                  className="px-2.5 py-1.5 bg-accent text-bg text-[13px] font-medium rounded-md hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition"
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
                        <span className="text-[9px] px-1 py-0 rounded bg-warning/5 text-warning font-medium flex-shrink-0">
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

// 任务拖动 wrapper (2026-07-30 立), 跟 SortableProjectCard 同款思路。
// 跟 project 拖动的区别: task 排序是项目内局部的, 所以用 arrayMove 算
// 的 newOrder 也在项目内取 prev/next, 不需要额外上下文。
function SortableTaskRow(props: {
  task: Task;
  onChange: () => void;
  onRequestComplete: (task: Task) => void;
}) {
  const { task, onChange, onRequestComplete } = props;
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={isDragging ? "z-10 opacity-50" : ""}
    >
      <TaskRow
        task={task}
        onChange={onChange}
        onRequestComplete={onRequestComplete}
        dragHandle={
          <button
            {...attributes}
            {...listeners}
            className="opacity-0 group-hover/row:opacity-60 hover:!opacity-100 w-5 h-5 flex items-center justify-center flex-shrink-0 text-fg-muted hover:text-fg rounded cursor-grab active:cursor-grabbing touch-none transition-opacity"
            title="拖动改顺序"
            aria-label="拖动任务"
            onClick={(e) => e.stopPropagation()}
          >
            <GripVertical size={12} />
          </button>
        }
      />
    </div>
  );
}

function TaskRow({
  task,
  onChange,
  onRequestComplete,
  dragHandle,
}: {
  task: Task;
  onChange: () => void;
  onRequestComplete: (task: Task) => void;
  // 2026-07-30: 拖动句柄 (GripVertical button) 从 SortableTaskRow 注入
  dragHandle?: React.ReactNode;
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
        {/* 拖动句柄 (2026-07-30 立) — 放第一行最左, group hover 才显示
            (跟 StatusMenu / ✅ / 删除按钮一致的 "平时不打扰" 哲学)。
            click stopPropagation 防止冒泡到整行 click (展开/收起)。 */}
        {dragHandle}

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

        {/* 今日承诺 ⭐ 按钮 (2026-08-01 立)
            - 已有承诺 → 实心黄色 Star, 点击移除承诺
            - 没承诺 → 透明 Star, hover 整行才显示, 点击加入承诺
            - 在状态 / due 之前 (承诺是"我今天要做" 的标记, 视觉权重要高) */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleCommitment(task.id);
            onChange(); // 触发 snapshot refresh 让 FocusSection 重新算承诺清单
          }}
          className={`w-5 h-5 flex items-center justify-center flex-shrink-0 transition rounded ${
            isCommitment(task.id)
              ? "text-warning opacity-100"
              : "text-fg-muted/30 opacity-0 group-hover/row:opacity-100 hover:text-warning"
          }`}
          title={isCommitment(task.id) ? "已在今日承诺 — 点击移除" : "加入今日承诺"}
        >
          <Star size={13} fill={isCommitment(task.id) ? "currentColor" : "none"} />
        </button>

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

      {/* 第二行:meta — 只显示 checklist 进度 (2026-08-01: 删掉"挂了N天" 提示, 信息密度过高)
          2026-07-21 重构: priority 已经在第一行色点表示, 不需要第二行再写"高/中/低"
          2026-07-22 v3: 删掉「草稿/阻塞」徽章 — 它们已经从第二行上移到第一行右侧
          的状态融合指示器表达 (StatusMenu trigger 根据 blocked/draft 切换 🚧/📝/横条),
          跟第一行右侧的 due 一起形成「状态 + 截止 + 展开 + 按钮」紧凑右栏。
          2026-08-01: 删掉"挂了 N 天" 提示, 减少第二行 meta 噪音, "年龄" 视觉信息在
          card 层级用项目内的 task 排序隐式表达。 */}
      {totalCount > 0 && (
        <div className="flex items-center gap-3 pl-3 pr-3 pb-1.5 text-[12px] text-fg-muted">
          {/* checklist 进度 */}
          <span className="tabular-nums">
            ☑ {doneCount}/{totalCount}
          </span>
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
  //   P0 红 (最急) → P1 橙 → P2 蓝 → P3 绿 (不急) — 颜色饱和度跟紧急度匹配
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
          <button onClick={save} className="px-2 py-0.5 bg-accent text-bg rounded">
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
