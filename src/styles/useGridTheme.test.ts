import { describe, expect, it } from 'vitest'
import { toCanvasColour } from './useGridTheme'

/* The failure this guards against is silent: canvas ignores a fillStyle it
 * cannot parse and keeps the previous colour, so a mis-formatted string paints
 * the wrong thing rather than throwing. */

describe('toCanvasColour', () => {
  it('passes through colours canvas already understands', () => {
    expect(toCanvasColour('rgb(10, 20, 32)')).toBe('rgb(10, 20, 32)')
    expect(toCanvasColour('rgba(0, 146, 209, 0.14)')).toBe('rgba(0, 146, 209, 0.14)')
    expect(toCanvasColour('  #0092d1  ')).toBe('#0092d1')
  })

  it('converts the color(srgb …) form Chrome produces from color-mix()', () => {
    // The real value observed for --grid-border-column in the light theme.
    expect(toCanvasColour('color(srgb 0.921569 0.941177 0.968627 / 0.7)')).toBe(
      'rgba(235, 240, 247, 0.7)',
    )
  })

  it('drops a redundant alpha of 1', () => {
    expect(toCanvasColour('color(srgb 0 0.572549 0.819608 / 1)')).toBe('rgb(0, 146, 209)')
    expect(toCanvasColour('color(srgb 0 0.572549 0.819608)')).toBe('rgb(0, 146, 209)')
  })

  it('accepts percentage alpha', () => {
    expect(toCanvasColour('color(srgb 1 1 1 / 50%)')).toBe('rgba(255, 255, 255, 0.5)')
  })

  it('clamps out-of-gamut channels rather than emitting invalid output', () => {
    // color-mix in a wider space can round-trip slightly outside 0–1.
    expect(toCanvasColour('color(srgb 1.02 -0.01 0.5)')).toBe('rgb(255, 0, 128)')
  })
})
