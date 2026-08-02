/**
 * PR 描述生成 (2026-08-01 立)
 *
 * 跟周报/述职不同, PR 描述是"项目维度" 的输出:
 * - 用户挑一个项目, 从该项目下选 N 条 ready 成就
 * - 选模板 (PR_Feature / PR_Bugfix / PR_Refactor)
 * - 调 LLM 生成 4 段 markdown: 背景/改动/影响/测试
 * - 复制到剪贴板 / 下载 .md 直接贴 GitHub PR
 *
 * 跟 lib/templates.ts 区别:
 * - templates.ts 是时间维度 (周报/述职)
 * - pr.ts 是项目维度 (PR 描述)
 *
 * 设计 (lesson #11 "成就二次加工" 用户决策):
 * - 端到端: 选项目 → 选成就 → 选模板 → 调 LLM → 出 markdown
 * - LLM 失败 fallback 纯模板填空 (跟 /report 一样, 不阻塞)
 * - "作为 PR 候选" checkbox 在 /achievements 累积到 localStorage, /pr 页加载预选
 */

import { api, type Achievement } from "./api";

export type PRTemplateKind = "PR_Feature" | "PR_Bugfix" | "PR_Refactor";

export interface PRTemplate {
  key: PRTemplateKind;
  label: string;
  emoji: string;
  description: string;
  /** 4 段标题 */
  sections: ["背景", "改动", "影响", "测试"];
  /** 纯模板 fallback (LLM 失败时使用) */
  fallback: (project: string, achievements: Achievement[]) => string;
}

export const PR_TEMPLATES: PRTemplate[] = [
  {
    key: "PR_Feature",
    label: "新功能",
    emoji: "✨",
    description: "新增一个产品功能",
    sections: ["背景", "改动", "影响", "测试"],
    fallback: (project, achievements) =>
      `## 背景\n\n为 ${project} 添加新功能:\n\n${achievements.map((a) => `- ${a.title}`).join("\n")}\n\n` +
      `## 改动\n\n(请补充具体实现细节)\n\n` +
      `## 影响\n\n(请补充对用户/业务的影响)\n\n` +
      `## 测试\n\n(请补充测试覆盖)\n`,
  },
  {
    key: "PR_Bugfix",
    label: "Bug 修复",
    emoji: "🐛",
    description: "修复一个生产 bug",
    sections: ["背景", "改动", "影响", "测试"],
    fallback: (project, achievements) =>
      `## 背景\n\n修复 ${project} 的问题:\n\n${achievements.map((a) => `- ${a.title}`).join("\n")}\n\n` +
      `## 改动\n\n(请补充根因 + 修复方案)\n\n` +
      `## 影响\n\n(请补充修复后的验证, e.g. DAU / 用户反馈)\n\n` +
      `## 测试\n\n(请补充回归测试)\n`,
  },
  {
    key: "PR_Refactor",
    label: "重构",
    emoji: "♻️",
    description: "代码重构 / 性能优化",
    sections: ["背景", "改动", "影响", "测试"],
    fallback: (project, achievements) =>
      `## 背景\n\n${project} 重构:\n\n${achievements.map((a) => `- ${a.title}`).join("\n")}\n\n` +
      `## 改动\n\n(请补充重构方案 + 涉及模块)\n\n` +
      `## 影响\n\n(请补充性能指标 / 可维护性提升)\n\n` +
      `## 测试\n\n(请补充回归 + 性能 benchmark)\n`,
  },
];

/** LLM 调用的端点封装 */
export async function generatePr(args: {
  project: string;
  achievements: Achievement[];
  templateKind: PRTemplateKind;
}): Promise<{ markdown: string; polished: boolean }> {
  return api.generatePr({
    project_name: args.project,
    achievements: args.achievements.map((a) => ({
      title: a.title,
      cv: a.cv,
      outcome: a.outcome,
    })),
    template_kind: args.templateKind,
  });
}
