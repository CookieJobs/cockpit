/**
 * First-use guidance belongs in the empty state, never as a delayed overlay.
 * The name is kept temporarily so existing imports remain source-compatible.
 */
export function OnboardingTooltip() {
  return (
    <div className="rounded-lg border border-border bg-bg-secondary px-4 py-3 text-sm text-fg-secondary">
      先建一个项目，再添加任务；完成时写下结果，成果会沉淀到成就库并可在输出中心使用。
    </div>
  );
}
