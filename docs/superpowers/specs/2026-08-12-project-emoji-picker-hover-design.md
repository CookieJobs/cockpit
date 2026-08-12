# Project Emoji Picker Hover — Design

## Status and decision

**Approved design direction:** restrained editable affordance.

The project emoji is a small piece of project identity, not a primary action. Its
hover state must make editability discoverable without competing with the project
name, progress, or task actions.

This change is presentation-only. It must not alter project data, the 50-item
emoji catalogue, picker actions, or popover state-machine behavior.

## Problem

The former trigger hover combined several high-attention signals: scale, a light
rounded background, box shadow, and an accent-coloured ring. When placed before a
project title, this makes the emoji appear to jump into a floating button. The
tooltip directly below it creates a second rectangular surface, worsening the
visual crowding seen in the supplied screenshot.

The picker grid and footer controls must follow the same interaction language.
A hover treatment that adds scale, shadows, or an accent ring to every emoji cell
turns a quick, low-risk selection into a visually noisy control.

## User-facing behavior

### Trigger

- At rest, the displayed emoji remains its current text size and occupies the
  existing layout footprint.
- On pointer hover, the trigger may show only a subtle `bg-bg-tertiary` surface
  and a 1px `border-border` outline. The border space must be reserved at rest
  with a transparent border, preventing a layout shift.
- It must not change scale, transform, box-shadow, foreground/accent colour, or
  the emoji's own size on hover or active state.
- Pressed state may only slightly reduce that same background contrast. It must
  not introduce motion or elevation.
- Keyboard users retain a visible `focus-visible:ring-2 focus-visible:ring-accent/60`
  treatment. This is a focus indicator, not a pointer-hover effect.
- The existing Chinese tooltip remains `点击更换项目 emoji`; it is explanatory
  metadata rather than a second hover animation. Do not replace it with a custom
  tooltip component in this scope.

### Picker contents

- An unselected emoji cell changes only its background to `bg-bg-tertiary` on
  hover. It must not scale, translate, shadow, or gain a ring.
- The selected emoji is persistently distinguishable with
  `bg-accent/20 ring-1 ring-accent/50`; this selected state may use accent because
  it conveys data state rather than a transient pointer state.
- The `当前 hash` and `随机` footer buttons may change text colour and background
  only. They must not scale or gain a shadow.
- Keep the existing short `transition-colors` timings. Do not use
  `transition-all`, `transition-transform`, `hover:scale-*`, `hover:shadow-*`,
  or `hover:ring-*` for unselected interactive elements.

### Popover behavior that must remain unchanged

- The popover opens on trigger click, is rendered through a Portal, and uses the
  shared `usePopover` and `usePopoverPosition` primitives.
- Clicking outside or pressing Escape closes it; Escape returns focus to the
  trigger.
- Choosing a grid emoji, restoring the deterministic hash emoji, or choosing a
  random emoji does **not** close the picker, so the user can compare choices.
- Internal pointer events must not be misclassified as outside clicks.
- The current `popover-in` scale-and-fade entrance remains allowed because it is
  the popover's entrance, not a hover effect on an emoji control.

## Scope boundaries

### In scope

- The visual classes and comments in `web/components/ProjectEmojiPicker.tsx`.
- Focused regression coverage that protects the visual-interaction contract.
- Type checking and focused project-emoji behavior checks.

### Explicitly out of scope

- Changing `Project.emoji` persistence, API schemas, the deterministic hash
  fallback, or the `PROJECT_EMOJIS` list.
- Changing `web/components/Popover.tsx`, positioning, z-index, Portal usage, or
  dismissal semantics.
- Reworking title editing, project-card layout, copy, or introducing a custom
  tooltip library.
- General hover refactors elsewhere in the application.

## Existing-code constraint

The working tree already contains an uncommitted
`web/components/ProjectEmojiPicker.tsx`. Treat it as user-owned in-progress work:
inspect and preserve compatible parts instead of overwriting it. If it already
satisfies an item in this specification, retain it and add only missing tests or
minimal corrections. Report any conflict rather than discarding the change.

## Design-system constraints

- Use only the existing semantic tokens (`bg-bg-tertiary`, `border-border`,
  `accent`) and Tailwind utilities already established by the theme system.
- Do not introduce hard-coded colours, since both light and dark themes are
  supported.
- Match the restrained background/colour feedback used by nearby StatusMenu,
  DueEditor, and archive controls; an emoji picker must not establish a separate
  elevation or motion language.

## Acceptance criteria

1. Trigger hover produces no transform, scale, shadow, or accent ring; its emoji
   retains a constant size.
2. The trigger's default transparent border and hover border prevent any shift
   of the adjacent project title.
3. Unselected grid cells and footer controls have background/colour-only hover
   feedback; the selected grid cell remains visibly selected.
4. Existing open/close, Portal, click-outside, Escape focus-return, and
   non-closing selection behavior remain intact.
5. The updated component type-checks with `cd web && npx tsc --noEmit`.
6. A focused invariant test fails if a future edit restores forbidden hover
   transforms, shadows, or rings, and it verifies the preserved interaction
   primitives and selected-state distinction.
7. Manual verification in both themes confirms the trigger is subtle, stable,
   and readable next to Chinese project titles; the picker opens without clipping.

## Required evidence from the implementer

The implementation handoff must include:

- changed-file summary;
- commands run, exit status, and concise test output;
- a checklist mapped to the seven acceptance criteria;
- a deviation report. If any requirement is unclear or conflicts with existing
  user changes, stop before broadening scope and record the conflict; do not make
  a silent design decision.
