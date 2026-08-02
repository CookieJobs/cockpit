// 成就统计纯函数 (2026-08-02 v0.3.5 立)
//
// 给 /achievements 顶部"沉淀质量"卡片用.
// 3 个核心指标:
//   1. ready 比例: cv_status=ready / total
//   2. 量化率: cv 文本含数字的占比 (DAU 5%, 10 万用户, 3 个模块 等)
//   3. 强动词比例: cv 以强动作动词开头的占比
//
// 跟 cv-template.ts 一样是纯函数, 无 React 依赖, 端到端可测.
//
// v0.4.3 计划: 把这套纯函数包装成 /api/achievements/stats 后端端点 + 专门统计页.

import type { Achievement } from "./api";

// v0.3.4 立: 强动词清单 (跟 app/api/llm.py POLISH_CV_SYSTEM 同步)
export const STRONG_VERBS = [
  "构建", "设计", "重构", "推动", "主导", "优化", "修复",
  "落地", "引入", "沉淀", "实现", "搭建", "制定", "抽象", "打造",
];

// v0.3.4 立: 弱动词清单 (禁止开头)
export const WEAK_VERBS = ["负责", "参与", "协助", "处理", "做了", "搞了", "弄了", "搞定了"];

// 量化匹配: 数字 + 单位 (%, 万, 倍, 个, 人, 天, 小时, ms, QPS, DAU...)
//   简化: 任何数字 + % / 万 / 倍 / 个 / 人 / 天 / 时 / ms / QPS / DAU / MAU
//   都算"量化"
const QUANTIFY_REGEX = /\d+(\.\d+)?\s*(%|万|倍|个|人|位|次|天|时|小时|分|秒|ms|s|qps|qps|日|月|年|条|行|款|dau|mau|api)/i;
// 或: 数字直接跟在"提升/增长/降低/节省/减少"等动词后
const QUANTIFY_VERB_REGEX = /(提升|增长|降低|节省|减少|加速|覆盖|服务)\s*\d/;

export interface AchievementStats {
  total: number;
  ready: number;
  pending: number;
  needs_data: number;
  ready_ratio: number;       // 0-1
  quantify_ratio: number;    // 0-1 (cv 文本含数字/量级)
  strong_verb_ratio: number; // 0-1 (cv 以强动词开头)
  // 细分
  quantify_count: number;
  strong_verb_count: number;
}

export function computeStats(items: Achievement[]): AchievementStats {
  const total = items.length;
  if (total === 0) {
    return {
      total: 0,
      ready: 0,
      pending: 0,
      needs_data: 0,
      ready_ratio: 0,
      quantify_ratio: 0,
      strong_verb_ratio: 0,
      quantify_count: 0,
      strong_verb_count: 0,
    };
  }

  let ready = 0;
  let pending = 0;
  let needsData = 0;
  let quantifyCount = 0;
  let strongVerbCount = 0;

  for (const a of items) {
    if (a.cv_status === "ready") ready++;
    else if (a.cv_status === "pending") pending++;
    else if (a.cv_status === "needs_data") needsData++;

    const cv = (a.cv || "").trim();
    if (!cv) continue;

    // 量化判定
    if (QUANTIFY_REGEX.test(cv) || QUANTIFY_VERB_REGEX.test(cv)) {
      quantifyCount++;
    }

    // 强动词判定: cv 开头第一个动词
    if (STRONG_VERBS.some((v) => cv.startsWith(v))) {
      strongVerbCount++;
    }
  }

  return {
    total,
    ready,
    pending,
    needs_data: needsData,
    ready_ratio: ready / total,
    quantify_ratio: quantifyCount / total,
    strong_verb_ratio: strongVerbCount / total,
    quantify_count: quantifyCount,
    strong_verb_count: strongVerbCount,
  };
}

// 工具: 比例 → 百分比字符串 (0-100, 整数, 四舍五入)
export function ratioToPct(ratio: number): number {
  return Math.round(ratio * 100);
}

// v0.4.3 立: 动词分布 — 统计每种强动词被用的次数
//   顺序: 按 count desc, 同 count 按 verb asc (稳定排序)
//   只统计 cv 以强动词开头的; 不以强动词开头的归到 "(其他)"
export interface VerbCount {
  verb: string;
  count: number;
}

export function verbDistribution(items: Achievement[]): VerbCount[] {
  const counts = new Map<string, number>();
  let other = 0;

  for (const a of items) {
    const cv = (a.cv || "").trim();
    if (!cv) continue;
    const matched = STRONG_VERBS.find((v) => cv.startsWith(v));
    if (matched) {
      counts.set(matched, (counts.get(matched) || 0) + 1);
    } else {
      other++;
    }
  }

  const result: VerbCount[] = Array.from(counts.entries())
    .map(([verb, count]) => ({ verb, count }))
    .sort((a, b) => {
      if (b.count !== a.count) return b.count - a.count;
      return a.verb.localeCompare(b.verb);
    });
  if (other > 0) {
    result.push({ verb: "(其他)", count: other });
  }
  return result;
}

// 工具: 评级 (0-100% 比例 → 文字)
//   >= 80%: 优秀
//   >= 60%: 良好
//   >= 40%: 一般
//   <  40%: 待提升
export function gradeRatio(ratio: number): { label: string; color: string } {
  const pct = ratioToPct(ratio);
  if (pct >= 80) return { label: "优秀", color: "text-success" };
  if (pct >= 60) return { label: "良好", color: "text-accent" };
  if (pct >= 40) return { label: "一般", color: "text-warning" };
  return { label: "待提升", color: "text-danger" };
}
