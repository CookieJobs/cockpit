// 2026-08-11 立：组件层只表达“这个元素代表什么”，不自行挑颜色。
//
// 视觉语义与产品语义一一对应：
// - interaction：可操作、已选中、当前焦点
// - asset：已沉淀、可复用的成就价值
// - warning：风险、待补数据、需要用户处理
//
// 这里的静态 class 字符串也会被 Tailwind JIT 扫描；tailwind.config.ts 的 lib
// content 路径是这个契约能够进入最终 CSS 的必要条件。

export type VisualRole = "interaction" | "asset" | "warning";
export type VisualTreatment = "soft" | "solid" | "text";

// The only tints allowed behind same-role text. They are verified against both
// theme surfaces in test-visual-tokens.mjs; product call sites must not invent
// a stronger value without extending that behavioral contrast contract.
export const SOFT_TONE_OPACITIES: Record<VisualRole, readonly number[]> = {
  interaction: [5, 10],
  asset: [5],
  warning: [5],
};

const VISUAL_TONES: Record<VisualRole, Record<VisualTreatment, string>> = {
  interaction: {
    soft: "border border-accent/35 bg-accent/10 text-accent",
    solid: "bg-accent text-bg hover:bg-accent-hover",
    text: "text-accent hover:text-accent-hover",
  },
  asset: {
    soft: "border border-asset/35 bg-asset/5 text-asset",
    solid: "bg-asset text-bg hover:bg-asset-hover",
    text: "text-asset hover:text-asset-hover",
  },
  warning: {
    soft: "border border-warning/35 bg-warning/5 text-warning",
    solid: "bg-warning text-bg hover:bg-warning-hover",
    text: "text-warning hover:text-warning-hover",
  },
};

/**
 * Return the Tailwind treatment for a user-visible visual role.
 *
 * Components should prefer this boundary over reusing accent for unrelated states:
 * it keeps interaction, achievement value, and risk legible in both themes.
 */
export function getVisualTone(role: VisualRole, treatment: VisualTreatment = "soft"): string {
  return VISUAL_TONES[role][treatment];
}
