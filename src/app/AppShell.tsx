/**
 * The application frame: sidebar, header, content.
 *
 * The header is a slot rather than something this component derives. A register
 * knows its own withheld count and a catalogue page knows how many relations it
 * found; a shell that tried to compute either would need to know about both,
 * and would be wrong about a third.
 */

import { useEffect, useState, type ReactNode } from 'react'
import { listBlueprints, type BlueprintSummary } from '@/api/client'
import { useThemeStore, type ThemePreference } from '@/styles/theme'
import { Icon } from './icons'
import { href, type Route } from './routes'
import './AppShell.css'

export interface AppShellProps {
  route: Route
  workspaceId: string
  title: ReactNode
  meta?: ReactNode
  actions?: ReactNode
  children: ReactNode
}

export function AppShell({ route, workspaceId, title, meta, actions, children }: AppShellProps) {
  const registers = useRegisters(workspaceId)

  // The register's real name, from the list the sidebar already loaded rather
  // than from a second fetch or a callback out of the page. A page reporting its
  // own title upward means the child setting the parent's state during render —
  // which React warns about — or an effect, which paints the placeholder first
  // and the name a frame later.
  const named =
    'blueprintId' in route ? registers?.find((r) => r.id === route.blueprintId)?.name : undefined

  return (
    <div className="shell">
      <Sidebar route={route} workspaceId={workspaceId} registers={registers} />
      <div className="shell__main">
        <header className="topbar">
          <h1 className="topbar__title">{named ?? title}</h1>
          {meta !== undefined && <div className="topbar__meta">{meta}</div>}
          <div className="topbar__spacer" />
          <div className="topbar__actions">
            {actions}
            <PersonaSwitch />
            <ThemeSwitch />
          </div>
        </header>
        <div className="shell__content">{children}</div>
      </div>
    </div>
  )
}

/**
 * The workspace's registers, loaded once for the whole shell.
 *
 * The sidebar lists them and the header names the open one, and both come from
 * here rather than from two requests — a Blueprint list fetched twice per
 * navigation is the kind of waste that only shows up under load.
 */
function useRegisters(workspaceId: string): BlueprintSummary[] | null {
  const [registers, setRegisters] = useState<BlueprintSummary[] | null>(null)

  useEffect(() => {
    let cancelled = false
    listBlueprints(workspaceId)
      .then((items) => {
        if (!cancelled) setRegisters(items)
      })
      .catch(() => {
        // A shell that cannot list registers is still a usable shell. The page
        // itself reports the failure with the context to explain it; two error
        // messages for one outage is noise.
        if (!cancelled) setRegisters([])
      })
    return () => {
      cancelled = true
    }
  }, [workspaceId])

  return registers
}

function Sidebar({
  route,
  workspaceId,
  registers,
}: {
  route: Route
  workspaceId: string
  registers: BlueprintSummary[] | null
}) {
  const activeBlueprint = 'blueprintId' in route ? route.blueprintId : undefined

  return (
    <nav className="sidebar" aria-label="Workspace">
      <div className="sidebar__brand">
        <span className="sidebar__mark" aria-hidden="true">
          F
        </span>
        <span className="sidebar__wordmark">Frame</span>
      </div>

      <div className="sidebar__scroll scrollable">
        <section className="sidebar__section">
          <h2 className="sidebar__heading">
            <span>Registers</span>
          </h2>

          {registers === null && <p className="sidebar__empty">Loading…</p>}

          {registers?.length === 0 && (
            // Not a blank space. A workspace with no Blueprints is a normal
            // starting state, and saying so is the difference between "new" and
            // "broken".
            <p className="sidebar__empty">
              No registers yet. A steward publishes a Blueprint and it appears
              here — no deploy.
            </p>
          )}

          {registers?.map((register) => (
            <a
              key={register.id}
              className={`sidebar__link${
                register.id === activeBlueprint && route.kind !== 'fields'
                  ? ' sidebar__link--active'
                  : ''
              }`}
              href={href.register(workspaceId, register.id)}
            >
              <Icon.Table className="sidebar__icon" />
              <span className="sidebar__label">{register.name}</span>
            </a>
          ))}
        </section>

        <section className="sidebar__section">
          <h2 className="sidebar__heading">
            <span>Data</span>
          </h2>
          <a
            className={`sidebar__link${
              route.kind === 'corporate' ? ' sidebar__link--active' : ''
            }`}
            href={href.corporate(workspaceId)}
          >
            <Icon.Warehouse className="sidebar__icon" />
            <span className="sidebar__label">Corporate data</span>
          </a>
        </section>
      </div>

      <div className="sidebar__footer">
        <a
          className={`sidebar__link${route.kind === 'harness' ? ' sidebar__link--active' : ''}`}
          href={href.harness()}
        >
          <Icon.Grid className="sidebar__icon" />
          <span className="sidebar__label">Grid harness</span>
        </a>
        <a
          className={`sidebar__link${route.kind === 'tokens' ? ' sidebar__link--active' : ''}`}
          href={href.tokens()}
        >
          <Icon.Fields className="sidebar__icon" />
          <span className="sidebar__label">Design tokens</span>
        </a>
      </div>
    </nav>
  )
}

const THEMES: ThemePreference[] = ['light', 'grey', 'dark']

function ThemeSwitch() {
  const preference = useThemeStore((s) => s.preference)
  const setPreference = useThemeStore((s) => s.setPreference)

  return (
    <div className="theme-switch" role="group" aria-label="Theme">
      {THEMES.map((theme) => (
        <button
          key={theme}
          type="button"
          className="theme-switch__option"
          aria-pressed={preference === theme}
          onClick={() => setPreference(theme)}
        >
          {theme}
        </button>
      ))}
    </div>
  )
}

const PERSONA_KEY = 'frame-dev-persona'
const PERSONAS = ['risk@unops.org', 'dev@unops.org']

/**
 * Development only, and eliminated from a production bundle by `import.meta.env.DEV`.
 *
 * It exists because the product's central claim is that two people see
 * different things, and a demonstration of that which requires two browsers and
 * two Google accounts is one nobody runs. The server still refuses any identity
 * not on its allow-list, so this selects among sanctioned identities rather than
 * asserting one.
 */
function PersonaSwitch() {
  const [persona, setPersona] = useState(
    () => globalThis.sessionStorage?.getItem(PERSONA_KEY) ?? PERSONAS[0],
  )

  if (!import.meta.env.DEV) return null

  return (
    <label className="persona">
      <span className="persona__label">Viewing as</span>
      <select
        className="ops-select"
        value={persona}
        onChange={(e) => {
          globalThis.sessionStorage?.setItem(PERSONA_KEY, e.target.value)
          setPersona(e.target.value)
          // A full reload, deliberately. Identity changes what every open
          // request may return, and patching a page in place after it changes
          // would leave the previous person's rows on screen beside the new
          // person's header.
          globalThis.location.reload()
        }}
      >
        {PERSONAS.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
    </label>
  )
}
