"""Source-level invariant tests for `web/components/ProjectEmojiPicker.tsx`.

The approved design (`docs/superpowers/specs/2026-08-12-project-emoji-picker-hover-design.md`)
locks the hover contract for the project emoji trigger, the unselected emoji grid
cells, and the picker footer controls. The selected-state ring, the popover
`popover-in` entrance animation, and the keyboard `focus-visible` ring are
explicitly allowed exceptions and must not be flagged by these tests.

These tests are intentionally narrow: they read the source file and check that
the precise class strings and interaction primitives are still present. They do
not run a browser, do not require a dev server, and do not import the component.
That keeps the regression contract portable and fast.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PICKER = ROOT / "web" / "components" / "ProjectEmojiPicker.tsx"


def read_picker() -> str:
    return PICKER.read_text(encoding="utf-8")


def section(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def code_lines(source: str) -> list[str]:
    """Return source lines with `// ...` line comments stripped.

    The component uses single-line `//` doc-comments that mention API names
    (e.g. "不再 pop.close()" inside a rationale block). Those mentions are
    historical commentary, not runtime calls, so the popover close-check must
    ignore them and only fail on actual call sites.
    """
    return [line for line in source.splitlines() if not line.lstrip().startswith("//")]


def test_trigger_hover_uses_a_circular_outline_without_layout_shift():
    source = read_picker()
    trigger = section(source, 'ref={pop.triggerRef}', 'aria-expanded={pop.open}')

    assert "rounded-full" in trigger
    assert "transition-shadow" in trigger
    assert "hover:shadow-[0_0_0_1px_rgb(var(--color-border-hover))]" in trigger
    assert "aria-label=\"点击更换项目 emoji\"" in trigger
    assert "focus-visible:ring-2 focus-visible:ring-accent/60" in trigger
    for forbidden in ("hover:scale-", "hover:bg-", "hover:ring-", "hover:transform"):
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
    # `pop.close()` is only forbidden as an active call site. Mentions in
    # single-line `//` comments (e.g. "不再 pop.close() — 让用户连续微调")
    # are historical rationale and must not trip the assertion.
    non_comment_source = "\n".join(code_lines(source))
    assert "pop.close()" not in non_comment_source
