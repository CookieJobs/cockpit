// Cockpit API 客户端

// API base URL 解析逻辑 (2026-07-21 修):
// - dev (.env.local): NEXT_PUBLIC_API_BASE=http://127.0.0.1:7842 → 显式绝对地址
// - production (Docker 部署): NEXT_PUBLIC_API_BASE=/api → 相对路径, 同源 fetch
//
// 防静默 fallback 踩坑 (历史 bug 2026-07-21):
// 之前 fallback 是 http://127.0.0.1:7842, 但 Next.js build 时 .env.local
// 优先级高于 .env.production, 本地开发设的 127.0.0.1:7842 会 inline 进 bundle,
// 部署到服务器后前端 fetch 连你**本机** 7842 而不是服务器 7842, 必报
// "Failed to fetch"。修法: Dockerfile build 时显式 ARG/ENV 覆盖, 这里
// fallback 改成空字符串, 让 fetch 走相对路径 (相对当前页面 origin)。
//
// 注意: 在用户浏览器 dev 模式 (next dev) 下, 没设 env 时 fetch 相对路径
// 会请求 next 自己 :3000/api/... → 404。所以保留 dev 模式 fallback 到 127.0.0.1:7842。
const _isDev = process.env.NODE_ENV === "development";
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ||
  (_isDev ? "http://127.0.0.1:7842" : "");

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!res.ok) {
    const err = await res.text();
    // 如果拿到的是 HTML（很可能是 next 的 404 页面），截短 + 提示一下根因，
    // 避免用户对着 100KB 的 HTML 报错抓瞎。
    const isHtml = err.trimStart().startsWith("<!");
    const hint = isHtml
      ? `（响应是 HTML 不是 JSON —— 通常是 NEXT_PUBLIC_API_BASE 没指向后端，或后端没启动。当前 API_BASE=${API_BASE}）`
      : "";
    const trimmed = isHtml ? `${err.slice(0, 200)}…` : err;
    throw new Error(`${res.status}: ${trimmed}${hint}`);
  }
  return res.json();
}

// ===== 类型 =====

/** 任务优先级（4 档）。2026-07-22 从「高/中/低」3 档升级：
 *  - P0 紧急/最高优先级, 必须立刻处理
 *  - P1 高优先级, 重要但非紧急
 *  - P2 默认档（普通）
 *  - P3 不急
 *  旧 DB 数据的「高/中/低」会在后端启动时一次性迁移到 P0/P2/P3。
 */
export type Priority = "P0" | "P1" | "P2" | "P3";
export type TaskStatus = "未开始" | "进行中" | "已完成";
export type CVStatus = "pending" | "needs_data" | "ready";

// 优先级 badge 样式 (2026-07-22 立, 2026-07-23 抽到 lib/api.ts 共享,
//                    2026-07-23 P3 改 success 绿):
//   软底色 (color/15) + 同色描边 (color/30) + 同色文字
//   P0 红 (0°)    = 最急 / danger
//   P1 橙 (30°)   = 高 / warning
//   P2 蓝 (220°)  = 普通 (默认) / info，跟 P1 暖色拉开 200°
//   P3 绿 (142°)  = 不急 / success ← 2026-07-23 从灰色换绿色, 跟 P0/P1/P2 一致
//                                                       用彩色表达"放松/无压力"
// 共享给 MainBoard 的 TaskRow (PriorityMenu trigger + popover 列表项),
// MainBoard 的 FocusItem (今日聚焦卡, 只读 span) 和
// /today 的 FocusRow (今日聚焦行, 只读 span) — 三处永远同步, 改颜色梯度只改一处。
// 跟 StatusMenu (短横条 + 灰/靛蓝/绿) 颜色梯度协调, 但形状/语义完全区分
// (StatusMenu 是进度编码, PriorityMenu 是紧急度编码 — 两个不同维度)。
// 注: P2 用 info (蓝) 而非 accent (靛蓝), 避免跟 P1 (橙) 暖色撞色, 也避免跟
//     StatusMenu "进行中" (accent 靛蓝) 视觉混淆 — 普通优先级是中性默认态, 蓝色最不抢眼。
//     P3 用 success (绿) 而非 fg-secondary (灰), 跟 P0 红/P1 橙/P2 蓝形成完整色环
//     (0° → 30° → 220° → 142°), 不急 = 放松, 绿色符合直觉。
export const PRIORITY_BADGE_STYLES: Record<Priority, string> = {
  P0: "bg-danger/15 text-danger border-danger/30",
  P1: "bg-warning/15 text-warning border-warning/30",
  P2: "bg-info/15 text-info border-info/30",
  P3: "bg-success/15 text-success border-success/30",
};

export interface ChecklistItem {
  text: string;
  done: boolean;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  archived: boolean;
  // 2026-07-30: 拖动排序。间隔 10 存, 给插入留空间。
  sort_order: number;
}

export interface Task {
  id: string;
  project: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: Priority;
  due: string | null;
  blocked: boolean;
  draft: boolean;
  created_at: string;
  completed_at: string | null;
  checklist: ChecklistItem[];
  // 2026-07-30: 项目内拖动排序。
  sort_order: number;
}

export interface Achievement {
  id: string;
  date: string;
  task_id: string;
  project_id: string;
  project: string;
  title: string;
  outcome: string;
  reflection: string;
  cv: string;
  cv_status: CVStatus;
  tags: string[];
  // 2026-08-01: LLM 主动追问 (任务完成时根据任务类型生成), 旧 achievement 默认 []
  follow_up_questions: string[];
  // 2026-08-01: 用户对每条追问的答案 {q_idx: answer_str}, 补全后 cv_status 升级 ready
  follow_up_answers: Record<string, string>;
  distillation_trace_id?: string | null;
}

export interface FocusItem {
  id: string;
  project: string;
  title: string;
  priority: Priority;
  due: string | null;
  blocked: boolean;
}

export interface ProjectSnapshot {
  id: string | null;
  name: string;
  description: string;
  tasks: Task[];
  // 2026-07-30: 拖动排序字段同步到 snapshot (后端 build_snapshot 已经透传)
  sort_order: number;
  // 2026-08-01: 项目内已完成 task 数 (后端 build_snapshot 算, 前端"查看已完成 N" 折叠区用)
  done_count: number;
}

export interface Snapshot {
  focus: FocusItem[];
  projects: ProjectSnapshot[];
  done_today: Achievement[];
  counts: { achievementsReady: number; achievementsPending: number };
  // 2026-08-01: 全局已完成 task 列表 (跨 project, 按 completed_at desc)
  done_tasks: Task[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  text: string;
  action: string | null;
  data: Record<string, unknown> | null;
  used_llm: boolean;
  tool_calls: Array<{ name: string; args: Record<string, unknown>; result_preview?: string }> | null;
  session_id?: string | null;
  persisted?: boolean;
}

export interface LLMStatus {
  available: boolean;
  backend: string | null;
  model: string | null;
  configured_backend: string;
  has_key: boolean;
  error?: string;
}

export type LLMBackend = "anthropic" | "deepseek" | "minimax" | "openai" | "custom";

export interface LLMSettingsPublic {
  backend: LLMBackend;
  model: string;
  api_key_masked: string | null;
  base_url: string | null;
  has_key: boolean;
  source: string;
}

export interface LLMSettingsResponse {
  db_config: LLMSettingsPublic | null;
  env_config: LLMSettingsPublic;
  active_source: string;
  available: boolean;
  active_backend: string | null;
  active_model: string | null;
}

export interface LLMSettingsUpdate {
  backend?: LLMBackend;
  model?: string;
  api_key?: string;
  base_url?: string;
}

// ===== Chat Sessions =====

export interface ChatSession {
  id: string;
  label: string;
  created_at: string;
  last_active_at: string;
  archived: boolean;
  message_count: number;
}

export interface ChatHistoryMessage {
  id: string;
  session_id: string;
  role: string; // "user" | "assistant"
  content: string;
  tool_calls: Array<{ id?: string; name: string; args: Record<string, unknown> }> | null;
  created_at: string;
}

// ===== Integrations (v0.5a.1) =====
// 接入中心 — 描述一个 agent 的元信息 + 当前是否已注册 cockpit MCP server

export interface IntegrationAgent {
  id: string;            // "claude_code" / "cursor" / "trae" / ...
  name: string;          // "Claude Code"
  type: "json" | "command";  // json = 写配置文件; command = 返对话命令 (WorkBuddy)
  scope?: "user" | "project";
  note: string;
  docs_url?: string | null;
  post_install: string;
  // json 类型才有
  config_paths?: Record<string, string>;   // 各 OS 模板路径
  current_os_path?: string | null;         // 当前 OS 展开后的实际路径
  is_installed: boolean;
  // command 类型才有
  install_command?: string;
  manual_command?: string;
}

export interface IntegrationsResponse {
  cockpit_path: string;
  current_os: string;
  agents: IntegrationAgent[];
}

export interface InstallIntegrationResult {
  success: boolean;
  agent_id: string;
  config_path: string;
  was_already_installed: boolean;
  post_install: string;
}

export interface UninstallIntegrationResult {
  success: boolean;
  agent_id: string;
  removed: boolean;
  config_path?: string;
  note?: string;
}

export interface IntegrationStatusItem {
  id: string;
  name: string;
  type: "json" | "command";
  is_installed: boolean;
  config_path?: string;
}

export interface IntegrationStatus {
  cockpit_path: string;
  current_os: string;
  installed_count: number;
  total_count: number;
  installed: IntegrationStatusItem[];
  not_installed: IntegrationStatusItem[];
}

// ===== Projects =====

export const api = {
  health: () => request<{ status: string; version: string; name: string }>("/api/health"),

  listProjects: (include_archived = false) =>
    request<Project[]>(`/api/projects?include_archived=${include_archived}`),

  createProject: (name: string) =>
    request<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  updateProject: (id: string, data: Partial<Project>) =>
    request<Project>(`/api/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteProject: (id: string) =>
    request<{ ok: boolean }>(`/api/projects/${id}`, { method: "DELETE" }),

  // 2026-07-30: 拖动 reorder
  reorderProjects: (items: { id: string; sort_order: number }[]) =>
    request<{ updated: number }>("/api/projects/reorder", {
      method: "POST",
      body: JSON.stringify({ items }),
    }),

  // ===== Tasks =====

  listTasks: (project?: string) =>
    request<Task[]>(`/api/tasks${project ? `?project=${project}` : ""}`),

  createTask: (data: Partial<Task> & { project: string; title: string }) =>
    request<Task>("/api/tasks", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  confirmDrafts: () =>
    request<{ confirmed: number }>("/api/tasks/confirm-drafts", { method: "POST" }),

  updateTask: (id: string, data: Partial<Task>) =>
    request<Task>(`/api/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteTask: (id: string) =>
    request<{ ok: boolean }>(`/api/tasks/${id}`, { method: "DELETE" }),

  // 2026-07-30: 拖动 reorder (项目内)
  reorderTasks: (items: { id: string; sort_order: number }[]) =>
    request<{ updated: number }>("/api/tasks/reorder", {
      method: "POST",
      body: JSON.stringify({ items }),
    }),

  completeTask: (id: string, data: { outcome?: string; reflection?: string; cv?: string; cv_status?: CVStatus; follow_up_questions?: string[]; distillation_trace_id?: string }) =>
    request<Achievement>(`/api/tasks/${id}/complete`, {
      method: "POST",
      body: JSON.stringify({
        outcome: data.outcome || "",
        reflection: data.reflection || "",
        cv: data.cv || "",
        cv_status: data.cv_status || "ready",
        follow_up_questions: data.follow_up_questions || [],
        distillation_trace_id: data.distillation_trace_id,
      }),
    }),

  // ===== Checklist =====

  checklistAdd: (taskId: string, text: string) =>
    request<Task>(`/api/tasks/${taskId}/checklist/add`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  checklistToggle: (taskId: string, index: number) =>
    request<Task>(`/api/tasks/${taskId}/checklist/toggle`, {
      method: "POST",
      body: JSON.stringify({ index }),
    }),

  checklistRemove: (taskId: string, index: number) =>
    request<Task>(`/api/tasks/${taskId}/checklist/remove`, {
      method: "POST",
      body: JSON.stringify({ index }),
    }),

  // ===== Achievements =====

  listAchievements: (params?: { project?: string; since?: string; only_ready?: boolean; cv_status?: CVStatus }) => {
    const search = new URLSearchParams();
    if (params?.project) search.set("project", params.project);
    if (params?.since) search.set("since", params.since);
    if (params?.cv_status) search.set("cv_status", params.cv_status);
    else if (params?.only_ready) search.set("only_ready", "true");
    const q = search.toString();
    return request<Achievement[]>(`/api/achievements${q ? `?${q}` : ""}`);
  },

  // ===== LLM helpers (2026-07-28 立, 2026-07-30 加 follow_up_questions) =====

  // 把 outcome 润色成 CV 风格的成就陈述 (完成弹窗"✨ 润色"按钮用)
  // 后端 POST /api/llm/polish_cv:
  //   - polished=false 表示 LLM 不可用已 fallback
  //   - follow_up_questions: 当 outcome 信息不够具体时, LLM 主动追问 1-2 个问题
  //     (2026-07-30 立, 解决"完成 PRD" 类抽象任务"动作≠价值" 痛点)
  polishCv: (taskTitle: string, outcome: string) =>
    request<{
      cv: string;
      polished: boolean;
      follow_up_questions?: string[];
      trace_id?: string;
    }>("/api/llm/polish_cv", {
      method: "POST",
      body: JSON.stringify({ task_title: taskTitle, outcome }),
    }),

  // 2026-08-01 立: PR 描述生成 — 从 ready 成就生成 4 段 markdown
  generatePr: (data: {
    project_name: string;
    achievements: Array<{ title: string; cv?: string; outcome?: string }>;
    template_kind: "PR_Feature" | "PR_Bugfix" | "PR_Refactor";
  }) =>
    request<{ markdown: string; polished: boolean }>("/api/llm/generate_pr", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateAchievement: (id: string, data: { cv?: string }) =>
    request<Achievement>(`/api/achievements/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  undoAchievement: (id: string) =>
    request<Task>(`/api/achievements/${id}/undo`, { method: "POST" }),

  // 2026-08-01 立: 按 task_id 撤销最近一次完成 (主页"已完成 task" 折叠区用)
  undoTask: (id: string) =>
    request<Task>(`/api/tasks/${id}/undo`, { method: "POST" }),

  // 2026-08-01 立: 补全追问提醒端点 (扫 cv_status != ready 且有 follow_up_questions 的成就)
  listPendingFollowUps: (params?: { cv_status?: CVStatus; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.cv_status) search.set("cv_status", params.cv_status);
    if (params?.limit) search.set("limit", String(params.limit));
    const q = search.toString();
    return request<{ items: Achievement[]; total: number }>(
      `/api/reminders/pending${q ? `?${q}` : ""}`
    );
  },

  // 2026-08-01 立: 补全追问 (PATCH achievement 写 follow_up_answers + 升级 cv_status)
  answerFollowUps: (id: string, answers: Record<string, string>) =>
    request<Achievement>(`/api/achievements/${id}/follow_ups`, {
      method: "PATCH",
      body: JSON.stringify({ answers }),
    }),

  // ===== Snapshot =====

  getSnapshot: () => request<Snapshot>("/api/snapshot"),

  // ===== Chat =====

  chat: (text: string, history?: ChatMessage[], sessionId?: string) =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        text,
        history: history || null,
        prefer_llm: true,
        session_id: sessionId || null,
      }),
    }),

  // 流式 chat（SSE）：逐事件回调。失败/中断时 reject。
  // 用 fetch + ReadableStream 而不是 EventSource，因为我们走 POST + body
  // （EventSource 只支持 GET）。SSE 帧格式：`event: <type>\ndata: <json>\n\n`
  chatStream: async (
    text: string,
    sessionId: string | null,
    onEvent: (event: { type: string; data: any }) => void,
    signal?: AbortSignal,
  ): Promise<void> => {
    const res = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        prefer_llm: true,
        session_id: sessionId || null,
      }),
      signal,
    });
    if (!res.ok || !res.body) {
      const err = await res.text();
      throw new Error(`${res.status}: ${err}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      // SSE 帧以双换行分隔
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        // 解析 event: / data: 行
        let event = "message";
        let data = "";
        const lines = raw.split("\n");
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            event = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            data += line.slice(6);
          }
        }
        if (data) {
          try {
            onEvent({ type: event, data: JSON.parse(data) });
          } catch (e) {
            console.error("Failed to parse SSE data:", e, data);
          }
        }
      }
    }
  },

  // ===== Chat Sessions =====

  listSessions: (includeArchived = false, limit = 50) =>
    request<{ sessions: ChatSession[] }>(
      `/api/chat/sessions?include_archived=${includeArchived}&limit=${limit}`
    ),

  getSession: (sessionId: string) =>
    request<ChatSession>(`/api/chat/sessions/${sessionId}`),

  createSession: (sessionId: string, label?: string) =>
    request<{ session: ChatSession; created: boolean }>("/api/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, label: label || null }),
    }),

  renameSession: (sessionId: string, label: string) =>
    request<ChatSession>(`/api/chat/sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify({ label }),
    }),

  deleteSession: (sessionId: string) =>
    request<{ ok: boolean; deleted_session_id: string }>(
      `/api/chat/sessions/${sessionId}`,
      { method: "DELETE" }
    ),

  cleanupEmptySessions: () =>
    request<{
      ok: boolean;
      deleted_count: number;
      deleted_ids: string[];
      threshold: number;
    }>("/api/chat/sessions/cleanup-empty", { method: "POST" }),

  listMessages: (sessionId: string, limit = 40) =>
    request<{ messages: ChatHistoryMessage[]; session_id: string }>(
      `/api/chat/sessions/${sessionId}/messages?limit=${limit}`
    ),

  // ===== LLM =====

  llmStatus: () => request<LLMStatus>("/api/llm/status"),

  llmTest: () =>
    request<{ ok: boolean; backend: string; model: string }>("/api/llm/test", {
      method: "POST",
    }),

  llmReset: () => request<{ ok: boolean }>("/api/llm/reset", { method: "POST" }),

  // ===== LLM Settings (用户在 UI 配) =====

  getLLMSettings: () => request<LLMSettingsResponse>("/api/settings/llm"),

  saveLLM: (data: LLMSettingsUpdate) =>
    request<LLMSettingsPublic>("/api/settings/llm", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  clearLLM: () =>
    request<{ ok: boolean; deleted: boolean }>("/api/settings/llm", {
      method: "DELETE",
    }),

  testLLM: (data: LLMSettingsUpdate) =>
    request<{ ok: boolean; backend?: string; model?: string; error?: string }>(
      "/api/settings/llm/test",
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),

  // ===== Integrations (v0.5a.1 — 一键注册 cockpit MCP 到 Claude Code / Cursor / ...) =====

  listSupportedIntegrations: () =>
    request<IntegrationsResponse>("/api/integrations/supported"),

  installIntegration: (agentId: string, cockpitPath?: string) =>
    request<InstallIntegrationResult>("/api/integrations/install", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, cockpit_path: cockpitPath ?? null }),
    }),

  uninstallIntegration: (agentId: string) =>
    request<UninstallIntegrationResult>("/api/integrations/uninstall", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId }),
    }),

  integrationStatus: () =>
    request<IntegrationStatus>("/api/integrations/status"),
};

// ===== Utility =====

/**
 * 把 "YYYY-MM-DD" 字符串按 **本地时区** 解析成 Date。
 *
 * ⚠️ 不要直接用 `new Date("2026-08-01")`!
 * ISO date-only 字符串在 JS 规范里被固定解析为 **UTC 午夜 00:00**。
 * 跟 `new Date()`(本地当前时刻) 比较时, 会被时区偏移(中国 UTC+8 = 8 小时)
 * 污染, Math.ceil(0.33) 进位到 1 → "今天" 显示成"明天" (2026-08-01 用户报)。
 *
 * 正确做法: 拆字段构造, 显式走本地时区。
 * lesson #18: 时区 bug 永远是 JS 的锅, 不是用户/数据库的锅。
 */
export function parseLocalDate(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function dueColor(due: string | null): "danger" | "warning" | "accent" | "muted" {
  if (!due) return "muted";
  // 跟 now 必须在同一个时区参考系下比较。parseLocalDate 走本地,
  // new Date() 默认也是本地 — 两个本地时刻相减, 0 时区偏移污染。
  const dueDate = parseLocalDate(due);
  const now = new Date();
  // 归零到本地 0 点, 跟"日历日" 粒度匹配 (不再计算小时/分/秒的 0.5 天差)
  now.setHours(0, 0, 0, 0);
  const diffDays = Math.round((dueDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return "danger";       // overdue
  if (diffDays === 0) return "warning";    // today
  if (diffDays <= 3) return "accent";      // soon
  return "muted";
}

export function dueLabel(due: string | null): string {
  if (!due) return "";
  // 跟 dueColor 同样的修复: parseLocalDate 走本地, now 归零到本地 0 点
  const dueDate = parseLocalDate(due);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  // 用 Math.round 而不是 Math.ceil: 修法之前用 ceil 会把"今天 早上 8 点"当成 0.33 天
  // 然后进位到 1 天 = "明天"。round 后 0.33 → 0, 0.5 边界 (本地 12:00 之前) 也归 0,
  // 12:00 之后归 1。但因为 now.setHours(0,0,0,0) 后 now 是 0:00:00, dueDate 也是 0:00:00,
  // 差永远是整数 N * 24h, round/ceil/floor 都给相同结果 — 安全。
  const diffDays = Math.round((dueDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return `${-diffDays}天前`;
  if (diffDays === 0) return "今天";
  if (diffDays === 1) return "明天";
  if (diffDays <= 7) return `${diffDays}天后`;
  return due;
}

export function statusIcon(status: TaskStatus): string {
  switch (status) {
    case "未开始": return "○";
    case "进行中": return "◐";
    case "已完成": return "●";
  }
}

/**
 * 相对日期显示（"今天" / "昨天" / "N 天前" / "N 周前" / "M月D日"）
 * 按"日历日"对比（不按小时），避免"今天"半夜前后跳来跳去。
 * 用于"已沉淀"区显示每条成就距今多久 — 比纯日期更易扫读。
 */
export function relativeDate(d: string | null | undefined): string {
  if (!d) return "";
  const date = typeof d === "string" ? new Date(d) : d;
  if (isNaN(date.getTime())) return "";
  const dDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const nDay = new Date();
  nDay.setHours(0, 0, 0, 0);
  const diff = Math.round((nDay.getTime() - dDay.getTime()) / 86400000);
  if (diff <= 0) return "今天";
  if (diff === 1) return "昨天";
  if (diff < 7) return `${diff} 天前`;
  if (diff < 30) return `${Math.floor(diff / 7)} 周前`;
  if (diff < 365) return `${date.getMonth() + 1}月${date.getDate()}日`;
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
}

/**
 * 计算 N 天前的 YYYY-MM-DD 字符串 — 用于成就 / 项目维度的"近期"窗口过滤。
 * 默认 7 天，跟 ProjectCard 的"已沉淀"区窗口一致。
 */
export function daysAgoISO(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

// ===== 项目 deterministic emoji（继承自 task-cockpit dashboard.html）=====
// 50 个 emoji 池子，按项目 id 字符串哈希取模——同一项目永远拿到同一个图标
// （视觉稳定 + 跨刷新一致 + 跟项目名解耦可改）
const PROJECT_EMOJIS = [
  "🎯", "🌟", "🔥", "💡", "🛠️", "🎨", "🚀", "📐", "🧩", "⚡️",
  "🌈", "🎪", "🔮", "🏆", "🌱", "🦋", "🐬", "🦊", "🌊", "🍀",
  "🎸", "🏔️", "🌙", "☀️", "🎭", "🧲", "🪄", "🦄", "🐉", "🍭",
  "🎲", "🧪", "🔭", "🗺️", "🎵", "🏄", "🌺", "🦅", "🍋", "🎃",
  "🧸", "🪐", "🌴", "🦁", "🐙", "🎋", "🍄", "🧊", "🪩", "🎠",
] as const;

export function projectEmoji(id: string | null | undefined): string {
  if (!id) return "📁"; // 未分组的兜底
  let h = 0;
  for (let i = 0; i < id.length; i++) {
    h = (h * 31 + id.charCodeAt(i)) >>> 0;
  }
  return PROJECT_EMOJIS[h % PROJECT_EMOJIS.length];
}
