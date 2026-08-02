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

const COLLAPSE_KEY = 'frame-sidebar-collapsed'

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
  const homeHref = href.workspace(workspaceId)

  // Collapse follows Bob's shell: a persisted preference, toggled by the same
  // panel glyph, collapsing to an icon rail rather than disappearing — the
  // rail keeps every destination one click away, which is what makes
  // collapsing feel like reclaiming space instead of losing the map.
  const [collapsed, setCollapsed] = useState(
    () => globalThis.localStorage?.getItem(COLLAPSE_KEY) === '1',
  )

  const toggle = () => {
    setCollapsed((current) => {
      const next = !current
      try {
        globalThis.localStorage?.setItem(COLLAPSE_KEY, next ? '1' : '0')
      } catch {
        /* private mode: the preference just does not persist */
      }
      return next
    })
  }

  /** A nav entry that renders as icon+label expanded and icon-with-tooltip in
   * the rail. One function so the two modes cannot drift. */
  const item = (
    key: string,
    to: string,
    active: boolean,
    label: string,
    icon: ReactNode,
  ) => (
    <a
      key={key}
      className={`sidebar__link${active ? ' sidebar__link--active' : ''}`}
      href={to}
      {...(collapsed ? { title: label, 'aria-label': label } : {})}
    >
      {icon}
      {!collapsed && <span className="sidebar__label">{label}</span>}
    </a>
  )

  return (
    <nav className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}`} aria-label="Workspace">
      <div className="sidebar__header">
        {/* The brand is a way home, like Bob's. In the rail the logo yields its
            spot to the toggle (also Bob's behaviour) and Home stays reachable
            through the nav item below. */}
        {!collapsed && (
          <a className="sidebar__brand" href={homeHref} aria-label="Home">
            <span className="sidebar__mark" aria-hidden="true">
              F
            </span>
            <span className="sidebar__wordmark">Frame</span>
          </a>
        )}
        <button
          type="button"
          className="sidebar__toggle"
          onClick={toggle}
          aria-expanded={!collapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <Icon.Panel />
        </button>
      </div>

      <div className="sidebar__scroll scrollable">
        {item(
          'home',
          homeHref,
          route.kind === 'workspace',
          'Home',
          <Icon.Home className="sidebar__icon" />,
        )}

        <section className="sidebar__section">
          {!collapsed && (
            <h2 className="sidebar__heading">
              <span>Registers</span>
            </h2>
          )}

          {!collapsed && registers === null && <p className="sidebar__empty">Loading…</p>}

          {!collapsed && registers?.length === 0 && (
            // Not a blank space. A workspace with no Blueprints is a normal
            // starting state, and saying so is the difference between "new" and
            // "broken".
            <p className="sidebar__empty">
              No registers yet. A steward publishes a Blueprint and it appears
              here — no deploy.
            </p>
          )}

          {registers?.map((register) =>
            item(
              register.id,
              href.register(workspaceId, register.id),
              register.id === activeBlueprint && route.kind !== 'fields',
              register.name,
              <Icon.Table className="sidebar__icon" />,
            ),
          )}
        </section>

        <section className="sidebar__section">
          {!collapsed && (
            <h2 className="sidebar__heading">
              <span>Data</span>
            </h2>
          )}
          {item(
            'corporate',
            href.corporate(workspaceId),
            route.kind === 'corporate',
            'Corporate data',
            <Icon.Warehouse className="sidebar__icon" />,
          )}
        </section>
      </div>

      <div className="sidebar__footer">
        {item(
          'harness',
          href.harness(),
          route.kind === 'harness',
          'Grid harness',
          <Icon.Grid className="sidebar__icon" />,
        )}
        {item(
          'tokens',
          href.tokens(),
          route.kind === 'tokens',
          'Design tokens',
          <Icon.Fields className="sidebar__icon" />,
        )}
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
