import { create } from 'zustand'

export type ThemePreference = 'system' | 'light' | 'grey' | 'dark'
export type ResolvedTheme = 'light' | 'grey' | 'dark'

const STORAGE_KEY = 'frame-theme'

/**
 * "system" is the ABSENCE of data-theme, not a value.
 *
 * brand-tokens.css selects its auto branch with
 * `@media (prefers-color-scheme: dark) { :root:not([data-theme]) { … } }`,
 * so writing data-theme="system" (or "auto") matches no theme block at all:
 * the page silently falls back to the light values in :root and stops
 * following the OS. Removing the attribute is the only correct encoding, and
 * it is the single easiest thing to get wrong in this file.
 */
function applyToDocument(preference: ThemePreference): void {
  const root = document.documentElement
  if (preference === 'system') {
    root.removeAttribute('data-theme')
  } else {
    root.setAttribute('data-theme', preference)
  }
}

function systemPrefersDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

function resolve(preference: ThemePreference): ResolvedTheme {
  if (preference !== 'system') return preference
  return systemPrefersDark() ? 'dark' : 'light'
}

function readStored(): ThemePreference {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === 'light' || raw === 'grey' || raw === 'dark' || raw === 'system') return raw
  } catch {
    // Storage can be unavailable (private mode, blocked cookies). System is a
    // safe default and the pre-paint script in index.html made the same call.
  }
  return 'system'
}

interface ThemeState {
  preference: ThemePreference
  resolved: ResolvedTheme
  /** Bumped whenever the rendered theme changes, so canvas consumers can re-read. */
  revision: number
  setPreference: (next: ThemePreference) => void
  init: () => () => void
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  preference: 'system',
  resolved: 'light',
  revision: 0,

  setPreference: (next) => {
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Non-fatal: the theme still applies for this session.
    }

    const commit = () => {
      applyToDocument(next)
      set((s) => ({ preference: next, resolved: resolve(next), revision: s.revision + 1 }))
    }

    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!reducedMotion && typeof document.startViewTransition === 'function') {
      // view-transitions.css animates a circular wipe from the top centre.
      // Interrupting one rejects the promise; that is expected, not an error.
      document.startViewTransition(commit).finished.catch(() => {})
    } else {
      commit()
    }
  },

  init: () => {
    const stored = readStored()
    applyToDocument(stored)
    set({ preference: stored, resolved: resolve(stored), revision: get().revision + 1 })

    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      // Only meaningful while following the system; an explicit choice wins.
      if (get().preference !== 'system') return
      set((s) => ({ resolved: resolve('system'), revision: s.revision + 1 }))
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  },
}))
