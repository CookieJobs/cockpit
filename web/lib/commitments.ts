/**
 * 今日承诺 (commitments) — localStorage 工具 (2026-08-01 立)
 *
 * 用途: 用户在主页 FocusSection 主动从 ProjectsSection 挑 N 个 task 加入承诺,
 * 承诺清单跨刷新保留, 用于驱动"今日承诺 N/M 已完成" 进度条。
 *
 * 设计:
 * - 纯前端工具, 不依赖后端 (承诺是用户自我承诺, 不是数据, 跨设备同步不必要)
 * - localStorage 持久化, key = `cockpit_today_commitments`
 * - SSR 安全: typeof window === 'undefined' 兜底
 * - 用 Set 内部表示, 暴露 string[] 数组
 * - 提供 progress() 函数算 {total, done, percent} 给 FocusSection 进度条
 *
 * 哲学 (用户决策 2026-08-01):
 * - "今日聚焦" 之前是系统硬选 5 个最高优先级 — 用户没控制权
 * - 新版 "今日计划" 承诺机制 — 用户主动挑 3-5 个, 承诺感驱动完成
 * - 承诺清单 + 系统 focus 共存: 承诺的 task 优先显示
 */

const STORAGE_KEY = "cockpit_today_commitments";

/** 读承诺集合 (SSR 安全) */
function readSet(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr.filter((x) => typeof x === "string") : []);
  } catch {
    return new Set();
  }
}

/** 写承诺集合 */
function writeSet(set: Set<string>) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(set)));
  } catch {
    /* 隐私模式 / quota 满, 静默忽略 */
  }
}

/** 加一个承诺 */
export function addCommitment(taskId: string): void {
  const set = readSet();
  set.add(taskId);
  writeSet(set);
}

/** 移除一个承诺 */
export function removeCommitment(taskId: string): void {
  const set = readSet();
  set.delete(taskId);
  writeSet(set);
}

/** 切换承诺状态 (在/不在) — 返回新状态 */
export function toggleCommitment(taskId: string): boolean {
  const set = readSet();
  if (set.has(taskId)) {
    set.delete(taskId);
    writeSet(set);
    return false;
  } else {
    set.add(taskId);
    writeSet(set);
    return true;
  }
}

/** 是否在承诺里 */
export function isCommitment(taskId: string): boolean {
  return readSet().has(taskId);
}

/** 列所有承诺 (顺序: 写入顺序, 但 Set 不保证 — 用 Array.from 转 array) */
export function listCommitments(): string[] {
  return Array.from(readSet());
}

/** 清空所有承诺 */
export function clearCommitments(): void {
  writeSet(new Set());
}

/**
 * 算承诺进度
 * @param doneIds 已完成的 task id 集合 (前端用 snapshot.done_tasks 算)
 * @returns {total, done, percent} — percent 是 0-100 整数
 */
export function progress(doneIds: Set<string>): { total: number; done: number; percent: number } {
  const set = readSet();
  const total = set.size;
  if (total === 0) return { total: 0, done: 0, percent: 0 };
  let done = 0;
  for (const id of set) {
    if (doneIds.has(id)) done++;
  }
  return { total, done, percent: Math.round((done / total) * 100) };
}
