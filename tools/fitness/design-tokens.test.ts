import { describe, expect, it } from 'vitest'
import { walk, stripComments } from './walk'

/**
 * Brand token enforcement.
 *
 * The project's own design rule is that no colour, shadow or layout width is
 * ever hard-coded: every one carries the brand's cyan-blue temperature, and a
 * single flat grey is what separates a UI that feels designed from one that
 * feels assembled. That rule is only real if a machine checks it — by the time
 * a reviewer notices #f5f5f5 it is already in six components.
 *
 * The token definition files are the one legitimate place raw values live.
 */

const TOKEN_FILES = [
  'src/styles/brand-tokens.css',
  'src/styles/frame-grid-tokens.css',
  'src/styles/frame-form-tokens.css',
  'src/styles/tailwind-bridge.css',
]

const isTokenFile = (path: string): boolean => TOKEN_FILES.includes(path)

describe('brand tokens', () => {
  it('no raw colour values outside the token files', () => {
    const files = [...walk('src', ['.css']), ...walk('src', ['.tsx'])].filter(
      (f) => !isTokenFile(f.path),
    )

    // Hex, rgb()/rgba(), hsl()/hsla(). color-mix() is fine — it composes tokens.
    const rawColour = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/

    const offenders: string[] = []
    for (const f of files) {
      const body = stripComments(f.text)
      for (const [i, line] of body.split('\n').entries()) {
        // A url() carrying an inline SVG is still a place a raw colour hides,
        // which is exactly how the select caret ended up hard-coded, so it is
        // deliberately NOT exempt here.
        if (rawColour.test(line)) offenders.push(`${f.path}:${i + 1}  ${line.trim().slice(0, 90)}`)
      }
    }

    expect(
      offenders,
      'Colours come from tokens, never literals (see specs/brand-tokens/brand-design-tokens.md).\n' +
        'Three rules the tokens encode and a literal breaks: never a pure neutral —\n' +
        'every surface, border and text colour carries a trace of the brand hue;\n' +
        'shadows are brand-tinted navy, never black; and every interactive state is\n' +
        'a brand-coloured overlay rather than a flat grey wash.\n' +
        'A literal also cannot follow the light / grey / dark theme switch, so it\n' +
        'will look correct in exactly the one theme you developed in.\n' +
        'Use var(--color-*), var(--shadow-*), or color-mix() over a token.\n' +
        'Offending lines:',
    ).toEqual([])
  })

  it('no hard-coded layout widths outside the token files', () => {
    const files = walk('src', ['.css']).filter((f) => !isTokenFile(f.path))

    // max-width: 100% and viewport math that composes a token are both fine.
    const hardWidth = /max-width\s*:\s*(?!100%|none|var\(|min\(|max\(|clamp\()[\d.]+(px|rem|em)/

    const offenders: string[] = []
    for (const f of files) {
      const body = stripComments(f.text)
      for (const [i, line] of body.split('\n').entries()) {
        // A media-query breakpoint is not a container width, and it cannot be a
        // token even in principle: CSS custom properties are not permitted in
        // media feature values. Breakpoint SPRAWL is a real problem, so it is
        // checked separately below rather than not at all.
        if (/@media|@container/.test(line)) continue
        if (hardWidth.test(line)) offenders.push(`${f.path}:${i + 1}  ${line.trim().slice(0, 90)}`)
      }
    }

    expect(
      offenders,
      'Container widths come from --layout-xs/sm/md/lg/xl so they can be changed\n' +
        'in one place. A hard-coded 720px is a decision nobody can find later.\n' +
        'Offending lines:',
    ).toEqual([])
  })

  it('breakpoints are a small shared set, not one per component', () => {
    // Custom properties are illegal in media feature values, so breakpoints
    // cannot be tokens. What can be enforced is that there are FEW of them: a
    // codebase where each component invents its own collapse point has no
    // responsive design, it has a collection of unrelated ones, and the symptom
    // is a layout that reflows three times across a fifty-pixel drag.
    const breakpoints = new Map<string, string[]>()

    for (const f of walk('src', ['.css'])) {
      const body = stripComments(f.text)
      for (const [i, line] of body.split('\n').entries()) {
        for (const match of line.matchAll(/\((?:min|max)-width:\s*([^)]+)\)/g)) {
          const value = (match[1] ?? '').trim()
          const seen = breakpoints.get(value)
          if (seen) seen.push(`${f.path}:${i + 1}`)
          else breakpoints.set(value, [`${f.path}:${i + 1}`])
        }
      }
    }

    const MAX_BREAKPOINTS = 3
    const distinct = [...breakpoints].map(([value, at]) => `${value}  (${at.join(', ')})`).sort()

    expect(
      distinct.length,
      `At most ${MAX_BREAKPOINTS} distinct breakpoints. Reuse one already in the\n` +
        'set, or raise this bound deliberately because a layout genuinely needs a\n' +
        'new one. In use:\n  ' +
        distinct.join('\n  '),
    ).toBeLessThanOrEqual(MAX_BREAKPOINTS)
  })

  it('the theme contract is documented where it is easy to get wrong', () => {
    const boot = walk('.', ['index.html']).find((f) => f.path === 'index.html')
    expect(boot, 'index.html not found').toBeDefined()

    // "auto" is the ABSENCE of data-theme, not a value. Writing
    // data-theme="auto" matches no theme block, silently pins light, and
    // disables system following. This asserts the boot script removes it.
    expect(
      boot!.text.includes('removeAttribute'),
      'The pre-paint theme script must REMOVE data-theme for system/auto rather\n' +
        'than setting it to "auto": brand-tokens.css selects the auto branch with\n' +
        ':root:not([data-theme]), so any value there defeats it silently.',
    ).toBe(true)
  })
})
