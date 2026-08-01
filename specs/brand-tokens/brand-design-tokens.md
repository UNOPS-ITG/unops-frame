---
description: Enforces use of brand design tokens and utility classes for all colors, shadows, borders, typography, and layout. No hard-coded color values allowed anywhere in components, pages, views, or templates.
globs: "**/*.{html,css,scss,ts,tsx,component.ts}"
alwaysApply: true
---

# Brand Design Tokens & Utility Classes — Mandatory Usage

All UI code in this project **MUST** use the design tokens defined in `src/styles/brand-tokens.css` and the utility classes from `src/styles/utilities.css`. Hard-coding color values **and hard-coding layout widths** are strictly forbidden. Every component, page, view, and template that contains HTML or CSS must follow these rules.

## Design Philosophy

Our brand uses a cool blue hue (#0092d1, ~198°). Three rules govern every color decision:

**Rule 1 — Never use a pure neutral.** No #FFFFFF, #000000, #808080, #F5F5F5, or any flat grey. Every background, border, and text color carries a trace of the brand's cyan-blue hue. This is what separates a UI that feels designed from one that feels assembled.

**Rule 2 — Match shadow color to brand temperature.** Shadows use `rgba(0, 73, 118, ...)` (brand-tinted navy) in light/grey themes and `rgba(5, 12, 24, ...)` with brand-hue luminance borders in dark. Never `rgba(0, 0, 0, ...)`. Every shadow includes a `0 0 0 1px` hairline border carrying the brand temperature.

**Rule 3 — Tint every interactive state.** Hover, focus, and active states use `var(--color-hover)`, `var(--color-active)`, `var(--color-focus-ring)` — brand-colored overlays. Never a flat grey overlay like `rgba(0,0,0,0.1)`.

## What is forbidden

```css
/* ❌ NEVER — hard-coded colors */
color: #333;
background: white;
border: 1px solid #e5e5e5;
box-shadow: 0 2px 4px rgba(0,0,0,0.1);
background-color: #f5f5f5;
color: rgb(100, 100, 100);
```

```css
/* ❌ NEVER — hard-coded layout widths */
max-width: 720px;
max-width: 52rem;
max-width: 1152px;
```

```css
/* ✅ ALWAYS — use design tokens */
color: var(--color-text);
background: var(--color-surface);
border: 1px solid var(--color-border);
box-shadow: var(--shadow-md);
background-color: var(--color-bg);
color: var(--color-text-secondary);
max-width: var(--layout-md);
```

## Layout width rules

**Rule 4 — Always use layout tokens for page/container max-widths.** Never hard-code `px` or `rem` values for `max-width` on page containers, content areas, or major layout regions. Use the `--layout-*` tokens so widths stay consistent and can be adjusted from a single place.

| Token | Value | When to use |
|---|---|---|
| `--layout-xs` | 28rem (448px) | Dialogs, small modals, popover panels |
| `--layout-sm` | 40rem (640px) | Settings pages, narrow forms, sidebars |
| `--layout-md` | 52rem (832px) | Single-column content: chat, conversation lists, documents, toolbars |
| `--layout-lg` | 60rem (960px) | Template selectors, mid-width listing pages |
| `--layout-xl` | 72rem (1152px) | Card grids: workspace list, workspace home |
| `--layout-prompt` | 40rem | Chat prompt input boxes (hero and inline) |

Prefer the `.container-sm` / `.container-md` / `.container-lg` / `.container-xl` utility classes on wrapper elements. Fall back to `max-width: var(--layout-*)` in component CSS when a utility class isn't practical (e.g., inside a BEM block that also needs padding).

## Available token categories

| Purpose | Tokens |
|---------|--------|
| Surfaces | `--color-bg`, `--color-surface`, `--color-surface-raised`, `--color-surface-sunken` |
| Borders | `--color-border`, `--color-border-strong`, `--color-border-subtle` |
| Text | `--color-text`, `--color-text-secondary`, `--color-text-muted`, `--color-text-link` |
| Shadows | `--shadow-xs`, `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-xl` |
| Interactive | `--color-hover`, `--color-active`, `--color-selected`, `--color-focus-ring` |
| Buttons | `--color-btn-primary-bg`, `--color-btn-primary-hover`, `--color-btn-primary-active`, `--color-btn-danger-hover`, `--color-btn-danger-active` |
| Chips | `--color-chip-bg`, `--color-chip-text`, `--color-chip-border`, `--chip-radius`, `--chip-padding-y`, `--chip-padding-x`, `--chip-font-size`, `--chip-font-weight`, `--chip-gap` |
| Brand | `--color-brand-primary`, `--color-brand-subtle`, `--color-brand-secondary` |
| Feedback | `--color-brand-success`, `--color-brand-warning`, `--color-brand-error`, `--color-brand-info` |
| Status | `--color-status-active-bg`, `--color-status-draft-bg`, `--color-status-danger-bg`, etc. |
| Inputs | `--color-input-bg`, `--color-input-border`, `--color-input-border-focus` |
| Code | `--color-code-bg`, `--color-code-text` |
| Typography | `--font-family-display`, `--font-family-body`, `--font-family-mono` |
| Font sizes | `--font-size-xs` through `--font-size-5xl` |
| Font weights | `--font-weight-normal`, `--font-weight-medium`, `--font-weight-semibold`, `--font-weight-bold` |
| Line heights | `--line-height-tight`, `--line-height-snug`, `--line-height-normal`, `--line-height-relaxed` |
| Spacing | `--spacing-0` through `--spacing-24` |
| Radii | `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-xl`, `--radius-2xl`, `--radius-full` |
| Layout widths | `--layout-xs` (28rem), `--layout-sm` (40rem), `--layout-md` (52rem), `--layout-lg` (60rem), `--layout-xl` (72rem), `--layout-prompt` (40rem) |
| Transitions | `--transition-fast`, `--transition-base`, `--transition-slow` |
| Z-index | `--z-dropdown`, `--z-sticky`, `--z-overlay`, `--z-modal`, `--z-popover`, `--z-tooltip` |

## Utility classes (from `src/styles/utilities.css`)

Always prefer utility classes for common layout patterns instead of writing one-off CSS:

| Category | Classes |
|----------|---------|
| Flex layout | `.flex-row`, `.flex-col`, `.flex-center`, `.flex-between`, `.flex-1`, `.flex-shrink-0` |
| Alignment | `.items-start`, `.items-center`, `.items-end` |
| Gap | `.gap-1`, `.gap-2`, `.gap-3`, `.gap-4`, `.gap-6`, `.gap-8` |
| Sizing | `.w-full`, `.h-full`, `.min-h-0` |
| Containers | `.container-sm`, `.container-md`, `.container-lg`, `.container-xl` (centered, width-limited page containers) |
| Text | `.truncate`, `.line-clamp-2`, `.line-clamp-3` |
| Chips | `.ops-chip` (base), `.ops-chip--mono`, `.ops-chip--pill`, `.ops-chip--bordered`, `.ops-chip--branded`, `.chips-row` (flex container) |
| Accessibility | `.visually-hidden` |
| Scrollable | `.scrollable` (adds thin scrollbar with brand-tinted track/thumb) |

Use these in JSX: `<div className="flex-row items-center gap-3">`. Combine with component-specific BEM classes when needed.

## CSS class naming convention

Use BEM-style naming for component-scoped CSS: `.component-name`, `.component-name__element`, `.component-name--modifier`. Colocate CSS files with their components (e.g., `ChatInput.tsx` + `ChatInput.css`).

## Exceptions

The ONLY permitted raw color values are:
- `transparent` and `currentColor` (CSS keywords)
- `inherit` (CSS keyword)
- Colors inside `src/styles/brand-tokens.css` itself (token definitions)
- SVG `fill`/`stroke` when referencing a brand token is not possible
- Recharts/charting libraries that require actual color strings (read computed values from tokens)

The ONLY permitted raw `max-width` values are:
- Viewport-relative expressions like `min(100vw - ..., var(--layout-*))` that combine a token with viewport math
- Component-internal sizing (e.g., `max-width: 100%`, tooltip/badge widths under 24rem)
- Values inside `src/styles/brand-tokens.css` itself (token definitions)
