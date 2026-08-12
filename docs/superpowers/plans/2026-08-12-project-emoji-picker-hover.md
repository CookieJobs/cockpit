# Project Emoji Picker Hover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the project-emoji picker discoverable but visually quiet, without changing its data model or interaction semantics.

**Architecture:** Keep `ProjectEmojiPicker` as the sole visual owner of this behavior. Its trigger, unselected grid cells, and footer controls use colour-only interaction feedback; the selected cell and keyboard focus retain their existing semantic emphasis. A focused Python invariant test protects these source-level visual and behavior contracts without adding a browser-testing framework.

**Tech Stack:** Next.js 15, React, TypeScript, Tailwind CSS semantic theme tokens, pytest.

## Global Constraints

- Read `AGENTS.md`, `.ai/AI_CTO.md`, `docs/GOAL.md`, the approved design spec, and relevant frontend/theme lessons before editing.
- The approved specification is `docs/superpowers/specs/2026-08-12-project-emoji-picker-hover-design.md`; it overrides aesthetic improvisation.
- Treat all existing uncommitted files as user-owned. In particular, inspect but do not overwrite compatible in-progress work in `web/components/ProjectEmojiPicker.tsx`.
- Do not alter API/Pydantic/storage behavior, the deterministic hash fallback, `PROJECT_EMOJIS`, `Popover.tsx`, copy, positioning, z-index, Portal use, or picker dismissal behavior.
- Do not add a dependency or run `next build`. Verify frontend types with `cd web && npx tsc --noEmit`.
- Use semantic theme tokens only; no hard-coded colour values.
- A pointer hover must never use scale, transform, shadow, or accent ring. `popover-in` entrance animation, the selected-cell ring, and `focus-visible` ring are explicitly permitted exceptions.
- Do not manufacture a failing test by reverting or damaging user-owned in-progress code. If the new test passes on the first run because the existing change already meets the approved contract, record that fact and continue.

---

## File map

| File | Responsibility |
|---|---|
| `web/components/ProjectEmojiPicker.tsx` | Owns the trigger, emoji grid, and footer-control class strings; preserves all picker behavior. |
| `app/tests/test_project_emoji_picker_invariants.py` | Focused source-level regression contract for hover, selection, focus, and popover primitives. |
| `docs/superpowers/specs/2026-08-12-project-emoji-picker-hover-design.md` | Approved product/design contract; read-only implementation reference. |

---

### Task 1: Lock the restrained hover contract and make the smallest compatible component correction

**Files:**

- Create: `app/tests/test_project_emoji_picker_invariants.py`
- Modify only if needed: `web/components/ProjectEmojiPicker.tsx`
- Do not modify: `web/components/Popover.tsx`, `web/lib/projectEmojis.ts`, `web/lib/api.ts`, `app/core/models.py`, `app/core/storage.py`

**Interfaces:**

- Consumes: `ProjectEmojiPickerProps` (`value`, `hashEmoji`, `onChange`, `children`), `usePopover`, `usePopoverPosition`, `PROJECT_EMOJIS`.
- Produces: unchanged component public API and unchanged selection/open-close behavior; source-level hover invariants protected by pytest.

- [ ] **Step 1: Read the approved constraints and inspect the exact existing component state**

Run:

```bash
sed -n '1,260p' docs/superpowers/specs/2026-08-12-project-emoji-picker-hover-design.md
sed -n '1,260p' web/components/ProjectEmojiPicker.tsx
git diff -- web/components/ProjectEmojiPicker.tsx
```

Confirm before touching code:

- The trigger retains a reserved transparent border at rest and uses only
  `hover:bg-bg-tertiary hover:border-border` plus a `focus-visible` ring.
- Grid `isCurrent` is the only static accent ring; the unselected branch is
  `hover:bg-bg-tertiary` only.
- Footer buttons use colour/background-only hover classes.
- `usePopover`, `usePopoverPosition`, Portal rendering, `pop.close()` omission,
  `onMouseDownCapture={swallow}`, and `popover-in` are still present.

If an existing uncommitted implementation already fulfills a point, retain it;
do not reformat unrelated lines.

- [ ] **Step 2: Create the focused regression test**

Create `app/tests/test_project_emoji_picker_invariants.py` with this complete
test module. It deliberately scopes forbidden hover checks to the trigger and
unselected-grid/footer branches so the allowed selected-state and popover
exceptions do not cause false failures.

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PICKER = ROOT / "web" / "components" / "ProjectEmojiPicker.tsx"


def read_picker() -> str:
    return PICKER.read_text(encoding="utf-8")


def section(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_trigger_hover_is_quiet_and_layout_stable():
    source = read_picker()
    trigger = section(source, 'ref={pop.triggerRef}', 'title="点击更换项目 emoji"')

    assert "border border-transparent" in trigger
    assert "hover:bg-bg-tertiary" in trigger
    assert "hover:border-border" in trigger
    assert "focus-visible:ring-2 focus-visible:ring-accent/60" in trigger
    for forbidden in ("hover:scale-", "hover:shadow-", "hover:ring-", "hover:transform"):
        assert forbidden not in trigger


def test_picker_hover_is_colour_only_while_selection_remains_distinct():
    source = read_picker()
    grid = section(source, '<div className="grid grid-cols-10 gap-0.5">', '</div>\n\n          {/* 分隔')
    footer = section(source, '{/* 分隔 + 当前 hash', '</div>\n        </div>,')

    assert 'isCurrent\n                      ? "bg-accent/20 ring-1 ring-accent/50"' in grid
    assert ': "hover:bg-bg-tertiary"' in grid
    for forbidden in ("hover:scale-", "hover:shadow-", "hover:ring-", "hover:transform"):
        assert forbidden not in grid
        assert forbidden not in footer
    assert footer.count("hover:bg-bg-tertiary") == 2
    assert footer.count("hover:text-fg") == 2


def test_existing_popover_and_continuous_selection_contract_is_preserved():
    source = read_picker()

    for required in (
        'import { createPortal } from "react-dom";',
        'const pop = usePopover();',
        'usePopoverPosition(pop.triggerRef, pop.open, { offsetY: 6, zIndex: 60 })',
        'className="popover-in',
        'onMouseDownCapture={swallow}',
        'aria-haspopup="dialog"',
        'aria-expanded={pop.open}',
    ):
        assert required in source
    assert "pop.close()" not in source
```

- [ ] **Step 3: Run the focused test and interpret the baseline honestly**

Run:

```bash
pytest app/tests/test_project_emoji_picker_invariants.py -v
```

Interpretation:

- If it fails, use the failing assertion to identify the precise visual contract
  missing from `ProjectEmojiPicker.tsx`.
- If it passes immediately, the existing in-progress component already meets the
  visual contract; preserve it. Do not change it just to create a red test.

- [ ] **Step 4: Apply only the minimal correction required by a failing assertion**

Within `ProjectEmojiPicker.tsx`, make only the relevant class-string correction:

```tsx
// Trigger: reserve layout with the default border; hover adds no elevation or motion.
className="inline-flex items-center justify-center p-1 -m-1 rounded-full cursor-pointer border border-transparent transition-colors duration-150 hover:bg-bg-tertiary hover:border-border active:bg-bg-tertiary/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"

// Grid: selected is persistent state; unselected pointer feedback is colour only.
isCurrent
  ? "bg-accent/20 ring-1 ring-accent/50"
  : "hover:bg-bg-tertiary"
```

Do not remove `popover-in`, the selected ring, or the focus-visible ring. Do not
add an icon, custom tooltip, hard-coded colour, animation, or component API.

- [ ] **Step 5: Re-run focused evidence and frontend type checking**

Run:

```bash
pytest app/tests/test_project_emoji_picker_invariants.py -v
cd web && npx tsc --noEmit
```

Expected: pytest reports 3 passed and TypeScript exits 0. Do not run `next build`.

- [ ] **Step 6: Manually verify the interaction in the running app**

With the frontend dev server already running, check both light and dark themes:

1. Hover the project emoji next to a Chinese project title: it remains the same
   size, title does not move, and there is no shadow/elevation.
2. Keyboard-tab to the trigger: focus ring is visible; Enter/Space opens picker.
3. Hover an unselected grid emoji and each footer control: only background/text
   colour reacts; no cell moves.
4. Confirm selected emoji has a persistent accent treatment distinct from hover.
5. Choose several emoji values, restore `当前 hash`, and choose `🎲 随机`:
   picker stays open each time.
6. Click outside, then reopen and press Escape: it closes; focus returns to the
   trigger. Scroll the board with picker open: it stays positioned with trigger
   and is not clipped.

Record any failure as a deviation; do not patch unrelated components to hide it.

- [ ] **Step 7: Review the exact diff, then commit only owned implementation files**

Run:

```bash
git diff --check
git diff -- web/components/ProjectEmojiPicker.tsx app/tests/test_project_emoji_picker_invariants.py
git status --short
```

Stage only `web/components/ProjectEmojiPicker.tsx` if it changed and the new test:

```bash
git add -- web/components/ProjectEmojiPicker.tsx app/tests/test_project_emoji_picker_invariants.py
git commit -m "fix: quiet project emoji picker hover"
```

Do not stage any pre-existing user files. In the final handoff state explicitly
whether the component source was changed or already compliant, list both command
results, map evidence to every acceptance criterion, and report any deviation.

---

## MiniMax Code handoff prompt

Copy the following message verbatim into MiniMax Code after it opens the Cockpit
repository:

```text
你是 Cockpit 的执行工程师。只执行已经批准的计划，不重新做产品/UX 决策。

先完整阅读并遵守：
1. AGENTS.md
2. .ai/AI_CTO.md
3. docs/GOAL.md
4. docs/lessons/01-frontend-ux-bugs.md
5. docs/lessons/05-theme-system.md
6. docs/superpowers/specs/2026-08-12-project-emoji-picker-hover-design.md
7. docs/superpowers/plans/2026-08-12-project-emoji-picker-hover.md

任务：严格执行上述 Implementation Plan 的 Task 1，修复项目 emoji picker 的 hover 视觉。先检查当前 git worktree 与 web/components/ProjectEmojiPicker.tsx；这里存在用户未提交的在途改动，必须保留兼容部分，不能用你的版本覆盖它。

硬约束：
- 只允许修改计划列出的组件和测试文件；不要改 API、数据库、PROJECT_EMOJIS、Popover.tsx、项目卡布局、文案、定位/z-index 或 picker 的开关行为。
- hover 只允许背景/文字颜色反馈；禁止 scale、transform、box-shadow、hover accent ring。selected state ring、focus-visible ring、popover-in 入场动画是允许的例外，不能删。
- 不添加依赖，不使用硬编码颜色，不跑 next build。
- 使用 apply_patch 编辑；不要改写或暂存无关的用户文件。
- 如果现有的未提交组件已满足某一条设计要求，不要为了“有改动”而重写或故意破坏它；补充缺失测试并如实报告即可。
- 任意需求冲突、测试失败、或需要扩大范围时，立刻停止并在最终报告的“偏离/阻塞”中说明；不要自行决定。

完成前必须运行：
pytest app/tests/test_project_emoji_picker_invariants.py -v
cd web && npx tsc --noEmit

最后输出：
1. 改动文件列表，以及每个文件改了什么；
2. 两条命令的完整结果和 exit code；
3. 对照 Spec 七项 Acceptance Criteria 的逐项证据；
4. 偏离/阻塞（没有则明确写“无”）；
5. 本次 commit hash。只提交你拥有的两份实现文件。
```
