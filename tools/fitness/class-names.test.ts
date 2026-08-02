import { describe, expect, it } from 'vitest'
import { walk } from './walk'

/**
 * Every class name a component asks for must exist.
 *
 * This check exists because of a real and embarrassing bug rather than as a
 * general tidiness rule. The button system is BEM — `.btn--secondary`, with two
 * dashes — and half the components were written as `btn-secondary`. CSS does not
 * complain about a selector that never matches, TypeScript has no opinion about
 * the contents of a string, and the lint rules are about code rather than
 * markup. So every one of those buttons rendered as unstyled inline text, and
 * the first report of it was a screenshot of the running product.
 *
 * That is the whole failure mode worth guarding: a class-name mistake has *no
 * failing signal anywhere*. It does not throw, it does not fail to compile, and
 * it does not fail a test — it just quietly produces a worse-looking product
 * than the one that was written. A machine comparing the two sides is the only
 * thing that catches it.
 *
 * The check is deliberately one-directional. An unused CSS class is fine —
 * `buttons.css` is a shared system and carries variants nothing has needed yet.
 * A class used and never defined is not.
 */

/** Classes that come from somewhere other than this repo's CSS. */
const EXTERNAL = new Set([
  // Glide Data Grid's own DOM, styled by the package.
  'gdg-cell',
  'gdg-growing-entry',
  'click-outside-ignore',
])

/**
 * A plausible class token.
 *
 * Restrictive on purpose: `className` expressions also contain fragments of
 * code, and a loose pattern turns every one of those into a false failure —
 * which is how a check like this gets deleted rather than fixed.
 */
const CLASS_TOKEN = /^[a-z][a-z0-9]*(?:[-_]{1,2}[a-z0-9]+)*$/

function definedClasses(): Set<string> {
  const defined = new Set<string>()
  for (const file of walk('src', ['.css'])) {
    // Every `.foo` in a selector position. Over-collects from inside strings and
    // url() values, which is the safe direction: it can only make the check more
    // permissive, never invent a failure.
    for (const match of file.text.matchAll(/\.(-?[A-Za-z_][\w-]*)/g)) {
      if (match[1]) defined.add(match[1])
    }
  }
  return defined
}

/**
 * The text of every `className` attribute value, brace-balanced.
 *
 * A line-by-line regex is not enough: the attributes most likely to carry a
 * conditional modifier are exactly the ones wrapped across several lines, so a
 * per-line scan would skip the cases with the highest chance of a typo.
 */
function classNameExpressions(text: string): { value: string; offset: number }[] {
  const out: { value: string; offset: number }[] = []
  const attribute = /class(?:Name)?\s*=\s*/g

  for (const match of text.matchAll(attribute)) {
    const start = match.index + match[0].length
    const opener = text[start]

    if (opener === '"' || opener === "'") {
      const end = text.indexOf(opener, start + 1)
      // Quotes kept, so both forms reach the literal scanner as literals.
      if (end > start) out.push({ value: text.slice(start, end + 1), offset: start })
      continue
    }
    if (opener !== '{') continue

    let depth = 0
    for (let i = start; i < text.length; i += 1) {
      const char = text[i]
      if (char === '{') depth += 1
      else if (char === '}') {
        depth -= 1
        if (depth === 0) {
          out.push({ value: text.slice(start + 1, i), offset: start })
          break
        }
      }
    }
  }

  return out
}

/**
 * Strings that are being *compared* rather than rendered.
 *
 * `route.kind === 'harness' ? 'x--active' : ''` contains two string literals and
 * only one of them is a class. Dropping comparison operands is what keeps the
 * check from failing on every conditional modifier in the codebase — the exact
 * construct it most needs to see inside.
 */
function withoutComparisons(source: string): string {
  return source
    .replace(/[!=]==?\s*(['"])(?:\\.|(?!\1).)*\1/g, ' ')
    .replace(/(['"])(?:\\.|(?!\1).)*\1\s*[!=]==?/g, ' ')
}

function usedClasses(): Map<string, string[]> {
  const used = new Map<string, string[]>()

  for (const file of walk('src', ['.tsx', '.ts'])) {
    for (const expression of classNameExpressions(file.text)) {
      const line = file.text.slice(0, expression.offset).split('\n').length
      const source = withoutComparisons(expression.value)

      // Every string literal that survived, with `${...}` holes turned into
      // separators so an interpolated value never fuses two class names.
      for (const literal of source.matchAll(/"([^"]*)"|'([^']*)'|`([^`]*)`/g)) {
        const body = (literal[1] ?? literal[2] ?? literal[3] ?? '').replace(/\$\{[^}]*\}/g, ' ')
        for (const token of body.split(/\s+/)) {
          if (!CLASS_TOKEN.test(token)) continue
          const at = `${file.path}:${line}`
          const seen = used.get(token)
          if (seen) seen.push(at)
          else used.set(token, [at])
        }
      }
    }
  }

  return used
}

describe('class names', () => {
  it('every class a component uses is defined in CSS', () => {
    const defined = definedClasses()
    const used = usedClasses()

    // A check that silently stops looking is worse than no check. If the
    // attribute scanner breaks, this fails rather than passing vacuously.
    expect(
      used.size,
      'no className attributes found — the scanner is not looking at anything',
    ).toBeGreaterThan(20)

    const undefinedClasses: string[] = []
    for (const [token, locations] of [...used].sort()) {
      if (defined.has(token) || EXTERNAL.has(token)) continue
      undefinedClasses.push(`${token}  (${locations.slice(0, 3).join(', ')})`)
    }

    expect(
      undefinedClasses,
      'These class names are used and never defined, so they style nothing.\n' +
        'Nothing else catches this: CSS ignores a selector that never matches,\n' +
        'TypeScript has no opinion about the contents of a string, and the element\n' +
        'still renders — just unstyled. The most common cause is BEM spelling:\n' +
        'a modifier is TWO dashes (btn--secondary, not btn-secondary) and an\n' +
        'element is TWO underscores (sidebar__link).\n' +
        'If the class genuinely comes from a third-party package, add it to\n' +
        'EXTERNAL in this file with a note saying which one.\n' +
        'Undefined classes:',
    ).toEqual([])
  })
})
