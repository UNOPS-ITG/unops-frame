/**
 * Frame's brand tokens, expressed as Glide Data Grid's theme object.
 *
 * The whole reason this file exists rather than a literal theme: Glide wants
 * flat colour strings and Frame's tokens are `color-mix()` expressions that
 * only the browser can resolve. `useGridTheme` does the resolving; this maps
 * the result onto Glide's names.
 *
 * Keeping the mapping in one place is what makes a theme change — or a later
 * grid swap — a single-file edit rather than a hunt through render code.
 */

import type { GridTheme } from '../styles/useGridTheme'

/** The subset of Glide's `Theme` Frame actually sets. Typed structurally so a
 * Glide version bump that adds optional keys does not break the build. */
export interface GlideTheme {
  accentColor: string
  accentFg: string
  accentLight: string
  textDark: string
  textMedium: string
  textLight: string
  textBubble: string
  bgIconHeader: string
  fgIconHeader: string
  textHeader: string
  textHeaderSelected: string
  bgCell: string
  bgCellMedium: string
  bgHeader: string
  bgHeaderHasFocus: string
  bgHeaderHovered: string
  bgBubble: string
  bgBubbleSelected: string
  bgSearchResult: string
  borderColor: string
  headerBottomBorderColor: string
  drilldownBorder: string
  linkColor: string
  cellHorizontalPadding: number
  cellVerticalPadding: number
  headerFontStyle: string
  baseFontStyle: string
  markerFontStyle: string
  fontFamily: string
  editorFontSize: string
}

/**
 * The font stack. Read from the token rather than restated, because a grid that
 * measures text in one font and paints it in another produces columns that are
 * subtly too narrow — and canvas gives no reflow to reveal it.
 */
function fontFamily(): string {
  if (typeof document === 'undefined') return "'Schibsted Grotesk', system-ui, sans-serif"
  // --font-family-body, not a Tailwind alias: this read used --font-sans for a
  // while, which does not exist, so the fallback applied — and the fallback
  // named Inter, which was never loaded, so the canvas silently measured and
  // painted in the OS default. Two absent fonts deep before anything was
  // wrong on screen enough to notice.
  const declared = getComputedStyle(document.documentElement)
    .getPropertyValue('--font-family-body')
    .trim()
  return declared || "'Schibsted Grotesk', system-ui, sans-serif"
}

export function toGlideTheme(theme: GridTheme): GlideTheme {
  const { palette, metrics } = theme

  return {
    accentColor: palette['color-brand-primary'],
    accentFg: palette['color-surface'],
    accentLight: palette['grid-cell-selected'],

    textDark: palette['color-text'],
    textMedium: palette['color-text-secondary'],
    textLight: palette['color-text-muted'],
    textBubble: palette['color-text'],

    bgIconHeader: palette['grid-header-text'],
    fgIconHeader: palette['grid-header-bg'],
    textHeader: palette['grid-header-text'],
    textHeaderSelected: palette['color-text'],

    bgCell: palette['color-surface'],
    bgCellMedium: palette['grid-row-stripe'],
    bgHeader: palette['grid-header-bg'],
    bgHeaderHasFocus: palette['grid-row-selected'],
    bgHeaderHovered: palette['grid-row-hover'],

    bgBubble: palette['grid-row-stripe'],
    bgBubbleSelected: palette['grid-cell-selected'],
    bgSearchResult: palette['grid-range-fill'],

    borderColor: palette['grid-border-row'],
    headerBottomBorderColor: palette['grid-header-border'],
    drilldownBorder: palette['grid-border-column'],
    linkColor: palette['color-brand-primary'],

    cellHorizontalPadding: metrics.cellPaddingX,
    cellVerticalPadding: metrics.cellPaddingY,

    // Glide takes CSS shorthand strings here, not numbers.
    headerFontStyle: `600 ${metrics.headerFontSize}`,
    baseFontStyle: `${metrics.fontSize}`,
    markerFontStyle: `${metrics.fontSize}`,
    fontFamily: fontFamily(),
    editorFontSize: metrics.fontSize,
  }
}
