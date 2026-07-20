/**
 * 周报/述职模板（2026-07-20 立 /report workspace）。
 *
 * 设计原则（参考 PRD 场景 4-5）：
 * - 模板在前端定义，**不调 LLM**（v1）— 模板结构固定, 拼接即可
 * - 每个模板给一个"骨架" (sections), 每个 section 是一组项目分组
 * - 用户可手动编辑每条 bullet, 调整模板预设顺序
 * - LLM 润色是 v2 的事 — v1 把"骨架 + 拼接" 做扎实, 后续 LLM 介入更平滑
 *
 * 模板选择策略：
 * - 产品周报: 按项目分组, 3 段 (进展/风险/计划)
 * - 研发周报: 按项目分组, 2 段 (技术进展/关键决策)
 * - 述职材料: 按季度, STAR 格式, 按项目分组
 */

import type { Achievement } from "./api";

export type TemplateKind = "product_weekly" | "eng_weekly" | "review_quarterly";

export interface TimeRange {
  key: string;
  label: string;
  // since date (YYYY-MM-DD) — used to filter achievements
  since: () => string;
  // until date (YYYY-MM-DD), inclusive — used for display
  until: () => string;
  description: string;
}

export interface Template {
  key: TemplateKind;
  label: string;
  emoji: string;
  description: string;
  // Markdown 标题
  title: (range: TimeRange) => string;
  // 模板结构 — 每个 section 一组项目分组
  sections: TemplateSection[];
  // 给一个 bullet 算分（用于排序 — 同 section 内重要的靠前）
  scoreBullet: (a: Achievement) => number;
}

export interface TemplateSection {
  key: string;
  title: string;
  // section 描述（提示用户这里写什么）
  hint: string;
  // 决定这条 achievement 是否属于本 section
  match: (a: Achievement) => boolean;
}

// ===== Time ranges =====

function ymd(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

export const TIME_RANGES: TimeRange[] = [
  {
    key: "this_week",
    label: "本周",
    description: "周一到今天",
    since: () => {
      const d = new Date();
      const day = d.getDay() || 7; // 周日=0, 转 7
      d.setDate(d.getDate() - (day - 1));
      return ymd(d);
    },
    until: () => ymd(new Date()),
  },
  {
    key: "last_week",
    label: "上周",
    description: "上周一至上周日",
    since: () => {
      const d = new Date();
      const day = d.getDay() || 7;
      d.setDate(d.getDate() - (day - 1) - 7);
      return ymd(d);
    },
    until: () => {
      const d = new Date();
      const day = d.getDay() || 7;
      d.setDate(d.getDate() - (day - 1) - 1);
      return ymd(d);
    },
  },
  {
    key: "this_month",
    label: "本月",
    description: "本月 1 号到今天",
    since: () => {
      const d = new Date();
      return ymd(new Date(d.getFullYear(), d.getMonth(), 1));
    },
    until: () => ymd(new Date()),
  },
  {
    key: "this_quarter",
    label: "本季度",
    description: "本季度 1 号到今天",
    since: () => {
      const d = new Date();
      const q = Math.floor(d.getMonth() / 3);
      return ymd(new Date(d.getFullYear(), q * 3, 1));
    },
    until: () => ymd(new Date()),
  },
];

// ===== Templates =====

export const TEMPLATES: Template[] = [
  {
    key: "product_weekly",
    label: "产品周报",
    emoji: "📊",
    description: "按项目分组, 3 段: 本周进展 / 风险阻塞 / 下周计划",
    title: (r) => `## ${r.label}周报（${r.since()} ~ ${r.until()}）`,
    sections: [
      {
        key: "progress",
        title: "本周进展",
        hint: "已完成的事, 配 cv/数据佐证",
        // 默认所有 ready + 显眼的 needs_data 都进
        match: (a) => a.cv_status === "ready" || a.cv_status === "needs_data",
      },
    ],
    // 评分: ready 优先, 然后按 cv 长度 (长的更详细) 排
    scoreBullet: (a) => {
      let s = 0;
      if (a.cv_status === "ready") s += 100;
      else if (a.cv_status === "needs_data") s += 50;
      s += Math.min(50, a.cv.length);
      return s;
    },
  },
  {
    key: "eng_weekly",
    label: "研发周报",
    emoji: "🛠️",
    description: "按项目分组, 2 段: 技术进展 / 关键决策",
    title: (r) => `## 研发${r.label}周报（${r.since()} ~ ${r.until()}）`,
    sections: [
      {
        key: "tech_progress",
        title: "技术进展",
        hint: "代码 / 架构 / 性能 / 工具 等",
        match: (a) => a.cv_status === "ready" || a.cv_status === "needs_data",
      },
    ],
    scoreBullet: (a) => {
      let s = 0;
      if (a.cv_status === "ready") s += 100;
      else if (a.cv_status === "needs_data") s += 50;
      s += Math.min(50, a.cv.length);
      return s;
    },
  },
  {
    key: "review_quarterly",
    label: "述职材料",
    emoji: "🏆",
    description: "STAR 格式, 按项目分组, 只用 ready 成就",
    title: (r) => `## 述职材料（${r.since()} ~ ${r.until()}）\n\n### 核心成果`,
    sections: [
      {
        key: "star",
        title: "核心成果 (STAR)",
        hint: "背景/行动/结果 三段, 只用 ready 成就",
        // 述职只用 ready（其他状态在源材料里补全后用 updateAchievement 升级）
        match: (a) => a.cv_status === "ready",
      },
    ],
    scoreBullet: (a) => 100 + Math.min(50, a.cv.length),
  },
];

// ===== 核心: 给定 range + template + achievements, 生成 markdown =====

export interface GeneratedReport {
  markdown: string;
  // 这份报告用了哪些成就（按 project 分组, 顺序匹配 markdown 里的项目顺序）
  usedAchievements: Achievement[];
  // 哪些项目有数据
  projectOrder: string[];
}

export function generateReport(
  achievements: Achievement[],
  range: TimeRange,
  template: Template
): GeneratedReport {
  // 1. 过滤 template sections 命中的
  const matched = achievements.filter((a) =>
    template.sections.some((s) => s.match(a))
  );

  // 2. 按 project 分组
  const byProject = new Map<string, Achievement[]>();
  for (const a of matched) {
    const k = a.project || "未分类";
    if (!byProject.has(k)) byProject.set(k, []);
    byProject.get(k)!.push(a);
  }

  // 3. 每个 project 内按 score 排序（高在前）
  for (const list of byProject.values()) {
    list.sort((x, y) => template.scoreBullet(y) - template.scoreBullet(x));
  }

  // 4. 拼 markdown
  const lines: string[] = [template.title(range), ""];

  for (const section of template.sections) {
    lines.push(`### ${section.title}`);
    lines.push(`> ${section.hint}`);
    lines.push("");

    if (byProject.size === 0) {
      lines.push("_（本段时间暂无相关成就）_");
      lines.push("");
      continue;
    }

    // 按 project 名排序（中文 locale），稳定
    const projects = Array.from(byProject.keys()).sort((a, b) =>
      a.localeCompare(b, "zh-CN")
    );

    for (const proj of projects) {
      const items = byProject.get(proj)!.filter((a) => section.match(a));
      if (items.length === 0) continue;
      lines.push(`**${proj}**`);
      for (const a of items) {
        const bullet = a.cv || a.outcome || a.title;
        // needs_data 加 [差数据] 标记, 提示用户
        const tag = a.cv_status === "needs_data" ? " `[📊 差数据]`" : "";
        lines.push(`- ${bullet}${tag}`);
      }
      lines.push("");
    }
  }

  return {
    markdown: lines.join("\n"),
    usedAchievements: matched,
    projectOrder: Array.from(byProject.keys()),
  };
}

// 给前端编辑用: 把 markdown 里的某条 bullet 替换成新文本
export function replaceBulletInMarkdown(
  markdown: string,
  oldText: string,
  newText: string
): string {
  // 简单替换 — 一份报告里没有重复 bullet, 一次替换足够
  return markdown.split(oldText).join(newText);
}
