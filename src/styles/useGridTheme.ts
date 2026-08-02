import { useEffect, useMemo, useState } from 'react'
import { useThemeStore } from './theme'

/**
 * Resolves Frame's grid tokens to literal colour strings for the canvas grid.
 *
 * Why this has to exist: the brand tokens express every interactive colour as
 * `color-mix(in srgb, var(--color-brand-primary) 14%, transparent)`. The
 * browser resolves that during style computation — a canvas 2D context has no
 * style computation, it wants `"rgb(0 146 209 / 0.14)"`. So the only way to
 * paint a canvas grid in brand colours without hard-coding them (which the
 * design rules forbid, and which would freeze the grid in one theme) is to ask
 * the browser to compute them for us and read the answer back.
 *
 * The read is done once per theme change against a detached probe element,
 * not per frame and not per cell.
 */

const GRID_TOKENS = [
  'grid-border-row',
  'grid-border-column',
  'grid-border-section',
  'grid-header-bg',
  'grid-header-text',
  'grid-header-border',
  'grid-row-stripe',
  'grid-row-hover',
  'grid-row-selected',
  'grid-cell-selected',
  'grid-cell-anchor-ring',
  'grid-range-fill',
  'grid-range-border',
  'grid-fill-handle',
  'grid-fill-handle-ring',
  'grid-drop-indicator',
  'grid-resize-handle',
  'grid-cell-restricted-bg',
  'grid-cell-restricted-text',
  'grid-cell-restricted-hatch',
  'grid-cell-dirty',
  'grid-cell-dirty-marker',
  'grid-cell-error-bg',
  'grid-cell-error-border',
  'grid-cell-conflict-bg',
  'grid-cell-conflict-marker',
  'grid-cell-readonly-bg',
  'grid-comment-indicator',
  'grid-presence-ring',
] as const

const SURFACE_TOKENS = [
  'color-bg',
  'color-surface',
  'color-text',
  'color-text-secondary',
  'color-text-muted',
  'color-brand-primary',
] as const

export type GridColourToken = (typeof GRID_TOKENS)[number] | (typeof SURFACE_TOKENS)[number]
export type GridPalette = Record<GridColourToken, string>

/**
 * Normalise a computed colour to `rgb()` / `rgba()`.
 *
 * Chrome resolves `color-mix(in srgb, …)` to the modern `color(srgb r g b / a)`
 * form, with channels as 0–1 floats. Canvas 2D in current Chrome accepts that,
 * but older engines and non-Chromium browsers do not — and a `fillStyle`
 * assignment that fails to parse is *silently ignored*, leaving the previous
 * colour in place. That is the worst possible failure mode for a grid: it does
 * not throw, it just paints the wrong thing somewhere in the middle of a
 * repaint. Converting up front removes the class of bug entirely.
 */
export function toCanvasColour(computed: string): string {
  const srgb = computed.match(
    /^color\(\s*srgb\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s*(?:\/\s*([\d.eE+-]+%?)\s*)?\)$/,
  )
  if (!srgb) return computed.trim()

  const channel = (raw: string | undefined): number => {
    const n = Number.parseFloat(raw ?? '0')
    return Math.max(0, Math.min(255, Math.round((Number.isFinite(n) ? n : 0) * 255)))
  }
  const [r, g, b] = [channel(srgb[1]), channel(srgb[2]), channel(srgb[3])]

  const rawAlpha = srgb[4]
  if (rawAlpha === undefined) return `rgb(${r}, ${g}, ${b})`

  const parsed = rawAlpha.endsWith('%')
    ? Number.parseFloat(rawAlpha) / 100
    : Number.parseFloat(rawAlpha)
  const alpha = Math.max(0, Math.min(1, Number.isFinite(parsed) ? parsed : 1))

  if (alpha === 1) return `rgb(${r}, ${g}, ${b})`
  // Trim to 4dp so the values stay readable in the gallery and in diffs.
  return `rgba(${r}, ${g}, ${b}, ${Number(alpha.toFixed(4))})`
}

/**
 * Force the browser to compute a token to a literal.
 *
 * getComputedStyle().getPropertyValue() on a custom property returns the
 * *specified* value — for a color-mix() that is the un-evaluated function text,
 * which is useless here. Assigning it to a real colour property and reading
 * that back gets the resolved colour. The probe is detached from layout so it
 * costs nothing visible.
 */
function resolvePalette(): GridPalette {
  const probe = document.createElement('span')
  probe.style.position = 'absolute'
  probe.style.visibility = 'hidden'
  probe.style.pointerEvents = 'none'
  document.body.appendChild(probe)

  const out = {} as GridPalette
  try {
    for (const token of [...GRID_TOKENS, ...SURFACE_TOKENS]) {
      probe.style.color = `var(--${token})`
      out[token] = toCanvasColour(getComputedStyle(probe).color)
    }
  } finally {
    probe.remove()
  }
  return out
}

/** Numeric geometry the canvas needs in device pixels rather than CSS text. */
export interface GridMetrics {
  rowHeight: number
  headerHeight: number
  cellPaddingX: number
  cellPaddingY: number
  borderWidth: number
  fillHandleSize: number
  indentStep: number
  fontSize: string
  headerFontSize: string
}

function resolveMetrics(): GridMetrics {
  const s = getComputedStyle(document.documentElement)
  const px = (name: string, fallback: number): number => {
    const parsed = Number.parseFloat(s.getPropertyValue(name))
    return Number.isFinite(parsed) ? parsed : fallback
  }
  return {
    rowHeight: px('--grid-row-height', 32),
    headerHeight: px('--grid-header-height', 36),
    cellPaddingX: px('--grid-cell-padding-x', 8),
    cellPaddingY: px('--grid-cell-padding-y', 4),
    borderWidth: px('--grid-border-width', 1),
    fillHandleSize: px('--grid-fill-handle-size', 6),
    indentStep: px('--grid-indent-step', 20),
    fontSize: s.getPropertyValue('--grid-font-size').trim() || '0.8125rem',
    headerFontSize: s.getPropertyValue('--grid-header-font-size').trim() || '0.75rem',
  }
}

export interface GridTheme {
  palette: GridPalette
  metrics: GridMetrics
}

export function useGridTheme(): GridTheme {
  // `revision` bumps on every theme change, including the system-follows case,
  // which is what makes the canvas re-read rather than staying on stale colours.
  const revision = useThemeStore((s) => s.revision)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    // A view transition paints the new theme asynchronously; reading in the
    // same frame as the attribute change can catch the outgoing values.
    const id = requestAnimationFrame(() => setTick((t) => t + 1))
    return () => cancelAnimationFrame(id)
  }, [revision])

  return useMemo(
    () => ({ palette: resolvePalette(), metrics: resolveMetrics() }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-resolve on theme change, not on data
    [revision, tick],
  )
}
