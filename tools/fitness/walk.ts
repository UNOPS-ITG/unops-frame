import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs'
import { join, relative, sep } from 'node:path'

const IGNORED_DIRS = new Set([
  'node_modules',
  'dist',
  '.git',
  'vendor',
  'coverage',
  'playwright-report',
  'venv',
  '.venv',
  '__pycache__',
])

export interface SourceFile {
  /** Repo-relative path, always with forward slashes. */
  path: string
  text: string
}

export function walk(root: string, extensions: string[]): SourceFile[] {
  if (!existsSync(root)) return []
  const out: SourceFile[] = []

  const visit = (dir: string): void => {
    for (const entry of readdirSync(dir)) {
      if (IGNORED_DIRS.has(entry)) continue
      const full = join(dir, entry)
      if (statSync(full).isDirectory()) {
        visit(full)
      } else if (extensions.some((e) => entry.endsWith(e))) {
        out.push({
          path: relative(process.cwd(), full).split(sep).join('/'),
          text: readFileSync(full, 'utf8'),
        })
      }
    }
  }

  visit(root)
  return out
}

/**
 * Strip comments so a rule about code does not fire on prose explaining the
 * rule. Crude on purpose: it over-strips inside string literals containing
 * "//", which for these checks fails safe (we miss a violation rather than
 * inventing one), and the alternative is a parser we do not need.
 */
export function stripComments(text: string): string {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
}

/**
 * A check whose subject does not exist yet must say so out loud. A fitness
 * suite that passes vacuously and silently is worse than no suite at all,
 * because it reports green while protecting nothing.
 */
export function pendingSubject(name: string, path: string): string {
  return `[fitness] "${name}" is not yet enforced: ${path} does not exist. This becomes active automatically when it does.`
}
