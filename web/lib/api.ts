// Cockpit API 客户端

// 默认指向本地后端端口，跟 .env 里的 COCKPIT_PORT 对齐（默认 7842）。
// 显式设 NEXT_PUBLIC_API_BASE 可覆盖（远程/容器部署时）。
// 留空会回退到相对路径（next dev 自己 :3000），那是个常见踩坑点 ——
// 所以我们选"宁可打错端口也不要静默 fallback"：默认就是 dev 的正确值。
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:7842";

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

export type Priority = "高" | "中" | "低";
export type TaskStatus = "未开始" | "进行中" | "已完成";
export type CVStatus = "pending" | "needs_data" | "ready";

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
  description?: string;
  tasks: Task[];
}

export interface Snapshot {
  focus: FocusItem[];
  projects: ProjectSnapshot[];
  done_today: Achievement[];
  counts: { achievementsReady: number; achievementsPending: number };
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

  completeTask: (id: string, data: { outcome?: string; reflection?: string; cv?: string; cv_status?: CVStatus }) =>
    request<Achievement>(`/api/tasks/${id}/complete`, {
      method: "POST",
      body: JSON.stringify({
        outcome: data.outcome || "",
        reflection: data.reflection || "",
        cv: data.cv || "",
        cv_status: data.cv_status || "ready",
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

  updateAchievement: (id: string, data: { cv?: string; cv_status?: CVStatus }) =>
    request<Achievement>(`/api/achievements/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  undoAchievement: (id: string) =>
    request<Task>(`/api/achievements/${id}/undo`, { method: "POST" }),

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
};

// ===== Utility =====

export function dueColor(due: string | null): "danger" | "warning" | "accent" | "muted" {
  if (!due) return "muted";
  const dueDate = new Date(due);
  const now = new Date();
  const diffDays = Math.ceil((dueDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return "danger";       // overdue
  if (diffDays === 0) return "warning";    // today
  if (diffDays <= 3) return "accent";      // soon
  return "muted";
}

export function dueLabel(due: string | null): string {
  if (!due) return "";
  const dueDate = new Date(due);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const diffDays = Math.ceil((dueDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
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
 * 任务"挂起 N 天"显示（继承自 task-cockpit dashboard.html 的 taskAge 逻辑）。
 *
 * 阈值：2 天以下不显示（任务刚建就是 0/1 天，不值得挤一行）。
 * 2 天及以上：显示"挂了 N 天"灰色小字，提示用户任务长期没动。
 */
export function taskAgeDays(createdAt: string | null | undefined): number {
  if (!createdAt) return 0;
  const a = new Date(createdAt);
  a.setHours(0, 0, 0, 0);
  const b = new Date();
  b.setHours(0, 0, 0, 0);
  return Math.round((b.getTime() - a.getTime()) / 86400000);
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
