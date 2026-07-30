/**
 * 完成任务引导（2026-07-30 立）。
 *
 * 背景：完成弹窗简化到 1 必填 (outcome) 后（2026-07-28 lesson #14），
 * 用户卡在新问题：「完成 PRD / 修 bug / 开会」这种抽象任务怎么写有价值的 outcome？
 * 本质是"动作 ≠ 价值" — 用户只记得"动作"，忘了"价值"。
 *
 * 解法（本文件）：按任务标题模式分 4 类（artifact/fix/discussion/research + generic 兜底），
 * 每类给：
 *   - emoji + label（视觉锚点）
 *   - 4 个引导维度（思维框架）
 *   - placeholder 示例（具体参考）
 *   - 1-2 个 follow-up 问题（AI 追问的种子）
 *
 * 关键设计：
 *   - 分类纯前端函数，无后端依赖（不阻塞完成流程）
 *   - 4 类关键词覆盖 Cockpit 实际 80% 任务（PRD/PPT/报告 → artifact，bug/修 → fix，
 *     会议/沟通 → discussion，调研/对比 → research）
 *   - generic 兜底避免"分类失败"把弹窗搞复杂
 *   - 关键词匹配 case-insensitive + 容忍中英文混合（Cockpit 用户两种都写）
 */

export type TaskCategory =
  | "artifact"  // 制品型：写/出/做/设计 PRD/PPT/文档/报告/原型
  | "fix"       // 修复型：修/改/解决/排查 bug
  | "discussion" // 对话型：开会/沟通/同步/评审/对齐
  | "research"  // 调研型：调研/对比/评估/分析
  | "generic";  // 通用兜底

export interface Guidance {
  emoji: string;
  label: string;
  /** 4 个思维维度，弹窗以 chip 形式展示 */
  dimensions: string[];
  /** outcome 输入框的占位示例 */
  placeholder: string;
  /** follow-up 问题，AI 追问 + 引导卡片共用 */
  followUps: string[];
}

/** 任务标题 → 分类。优先匹配更具体的类型（artifact/fix/discussion/research），最后 generic 兜底。
 *
 * 优先级 (2026-07-30 重构, lesson #15 盲点修复):
 *   artifact > fix > discussion > research > generic
 *
 * 关键设计:
 *   1. artifact 优先: 因为"整理述职材料" 既是整理(动作) 也是产出(artifact), 走 artifact 更符合用户预期
 *      但不能太宽: "整理思路" 应该走 generic, "整理周报" 走 artifact — 通过 artifact 关键词覆盖控制
 *   2. artifact 用"动作+产物" 双关键词配对: 单独一个动词或单独一个产物都不够, 避免误匹配
 *   3. fix 拆 3 子条件: 复合动词 (修复/解决) / "修" + bug类 / 直接含 bug 类关键词
 *   4. **不用 \b**: 中文没有 word boundary, \b 在中文里不工作, 容易漏匹配
 *   5. discussion 关键词是明确的"会议/沟通" 动作, 跟 artifact 的"写/整理" 错开, 避免误判
 *   6. research 关键词是"调研/对比/评估", 跟 artifact 的"写" 错开
 */
export function classifyTaskTitle(title: string): TaskCategory {
  if (!title || typeof title !== "string") return "generic";
  const t = title.toLowerCase().trim();

  // 1. artifact: 动作 (写/整理/产出/设计/...) + 产物 (文档/PPT/草稿/周报/材料/...)
  // 关键: 必须是动作+产物配对, 单动作 (如"整理一下") 不算
  if (
    /(写|编写|撰写|编|出|做|整理|制作|产出|输出|设计|画|建|搭|草拟|起草|拟|编辑|更新|发布|提交|审阅|完成|产出|出|产|弄|出完|做完|改|改好|改完|编辑|拟定)/i.test(
      t,
    ) &&
    /(prd|文档|报告|方案|ppt|原型|流程图|脑图|稿|表|讲稿|讲义|手册|教程|wiki|readme|综述|纪要|清单|规划|计划|分析|周报|月报|季报|材料|选题|文案|内容|笔记|日志|日记|感想|分享|调研|笔记|说明|规范|章程|手册|协议|合同|报价)/i.test(
      t,
    )
  ) {
    return "artifact";
  }

  // 2. fix: 3 子条件 (任一命中即 fix)
  // 2a. 复合动词: 修复/解决/排查/修好/修完/定位/debug/重构/优化/清理/处理/搞定/解决掉
  // 2b. 单独的"修" + bug 类名词: 修登录 bug, 修线上问题
  // 2c. 直接含 bug 类关键词: 系统崩溃了, 闪退问题, 报错, timeout
  // **不用 \b**: 中文没有 word boundary, 用 \b 会漏匹配 ("崩溃" 后面接 "了" 不是 \b)
  if (
    /(修复|解决|排查|修好|修完|定位|debug|重构|优化|清理|处理|搞定|解决掉)/i.test(
      t,
    ) ||
    /修.*?(bug|问题|故障|异常|报错|崩溃|闪退|卡顿|超时|宕机|泄露|泄漏|异常|报错|失败|卡死)/i.test(
      t,
    ) ||
    /(bug|报错|崩溃|闪退|故障|超时|宕机|卡顿|泄露|泄漏|异常|exception|crash|hang|freeze|timeout|500|404|401|403|null|undefined|nan|oom|leak)/i.test(
      t,
    )
  ) {
    return "fix";
  }

  // 3. discussion: 会议/沟通/对齐/评审/讨论
  // 关键: artifact 关键词已经处理了"复盘/总结" 类的写作产物, 这里只保留会议类动作
  // 包含: 明确"会议" 类动词 (开会/会议/评审/对齐) + 复合会议 (复盘会/对齐会/评审会/分享会/讨论会)
  if (
    /(开会|会议|沟通|同步|评审|讨论|对齐|站会|1on1|1:1|oneonone|review|retrospective|standup|meeting|跟.*?同步|跟.*?对齐|跟.*?对|复盘会|评审会|对齐会|分享会|讨论会|启动会|kickoff|回顾会)/i.test(
      t,
    )
  ) {
    return "discussion";
  }

  // 4. research: 调研/对比/评估/分析/探索
  if (
    /(调研|对比|评估|探索|考察|选型|poc|benchmark|可行性|research|可行性研究|对比.*?方案|调研.*?厂商)/i.test(
      t,
    )
  ) {
    return "research";
  }

  return "generic";
}

const GUIDANCE: Record<TaskCategory, Guidance> = {
  artifact: {
    emoji: "📄",
    label: "制品型任务",
    dimensions: ["覆盖场景数", "评审结论", "跨团队协作", "业务指标"],
    placeholder:
      "例如：为 App 改版输出主流程 PRD，覆盖 18 个核心场景，产品/设计/开发三方评审一次通过",
    followUps: [
      "这份是给谁看的？",
      "评审结果怎么样？",
      "覆盖了多少场景？",
    ],
  },
  fix: {
    emoji: "🔧",
    label: "问题修复",
    dimensions: ["影响用户数", "解决时长", "复现难度", "业务影响"],
    placeholder:
      "例如：修复高优登录鉴权 bug，影响约 5% DAU 用户，2 小时定位 4 小时上线，无复现",
    followUps: [
      "影响多少用户？",
      "用了多久解决？",
      "问题有多紧急？",
    ],
  },
  discussion: {
    emoji: "💬",
    label: "对话协同",
    dimensions: ["参与方", "输出决策数", "推动事项", "共识程度"],
    placeholder:
      "例如：组织产品/设计/开发三方对齐会，输出 5 个决策点，推动登录改版同步启动",
    followUps: [
      "参与方是谁？",
      "输出了什么决策？",
      "推动了什么事项？",
    ],
  },
  research: {
    emoji: "🔍",
    label: "调研分析",
    dimensions: ["对比方案数", "关键发现", "建议采纳", "耗时"],
    placeholder:
      "例如：调研 3 家厂商 SSO 方案，输出对比报告，建议 A 方案（性价比最高），节省 ¥30 万/年",
    followUps: [
      "对比了几个方案？",
      "关键发现是什么？",
      "推荐什么，为什么？",
    ],
  },
  generic: {
    emoji: "✨",
    label: "通用任务",
    dimensions: ["量化结果", "时间成本", "团队/用户影响"],
    placeholder:
      "完成了什么 + 有什么结果 / 影响（越具体越好，比如: 5% DAU 提升 / 2 天完成 / 影响 3 个团队）",
    followUps: [
      "这件事的价值是什么？",
      "对谁有影响？",
      "耗时多久？",
    ],
  },
};

export function getGuidance(category: TaskCategory): Guidance {
  return GUIDANCE[category];
}
