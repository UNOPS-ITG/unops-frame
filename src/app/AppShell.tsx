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
import { useSpineStore, waitingCount } from '@/fixtures/spine/store'
import { NewAppWizard } from '@/spine/NewAppWizard'
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
  const createdApps = useSpineStore((s) => s.createdApps)

  // The app's real name, from the list the sidebar already loaded rather
  // than from a second fetch or a callback out of the page. A page reporting its
  // own title upward means the child setting the parent's state during render —
  // which React warns about — or an effect, which paints the placeholder first
  // and the name a frame later. Session-born apps come from the spine store.
  const named =
    'blueprintId' in route
      ? (createdApps[route.blueprintId]?.draft.name ??
        registers?.find((r) => r.id === route.blueprintId)?.name)
      : undefined

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

  // The one always-visible creator, like Bob's "New conversation". It opens
  // the app wizard: describe the work or adopt a template, review, create.
  const [creating, setCreating] = useState(false)
  const createdApps = useSpineStore((s) => s.createdApps)

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

      <div className="sidebar__cta-wrap">
        <button
          type="button"
          className={`sidebar__cta${collapsed ? ' sidebar__cta--rail' : ''}`}
          onClick={() => setCreating(true)}
          {...(collapsed ? { title: 'New app', 'aria-label': 'New app' } : {})}
        >
          {collapsed ? <Icon.Plus /> : 'New app'}
        </button>
        {creating && <NewAppWizard workspaceId={workspaceId} onClose={() => setCreating(false)} />}
      </div>

      <div className="sidebar__scroll scrollable">
        {item(
          'home',
          homeHref,
          route.kind === 'workspace',
          'Home',
          <Icon.Home className="sidebar__icon" />,
        )}

        <InboxLink workspaceId={workspaceId} active={route.kind === 'inbox'} collapsed={collapsed} />

        <section className="sidebar__section">
          {!collapsed && (
            <h2 className="sidebar__heading">
              <Icon.Table className="sidebar__heading-icon" />
              <span>Apps</span>
            </h2>
          )}

          <div className="sidebar__group">
            {!collapsed && registers === null && <p className="sidebar__empty">Loading…</p>}

            {!collapsed && registers?.length === 0 && Object.keys(createdApps).length === 0 && (
              // Not a blank space. A workspace with no apps is a normal
              // starting state, and saying so is the difference between "new"
              // and "broken".
              <p className="sidebar__empty">
                No apps yet. Describe one with "New app" and it appears here —
                no deploy, no ticket.
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

            {Object.values(createdApps).map((app) =>
              item(
                app.id,
                href.register(workspaceId, app.id),
                app.id === activeBlueprint,
                app.draft.name,
                <Icon.Bolt className="sidebar__icon" />,
              ),
            )}
          </div>
        </section>

        <section className="sidebar__section">
          {!collapsed && (
            <h2 className="sidebar__heading">
              <Icon.Warehouse className="sidebar__heading-icon" />
              <span>Data</span>
            </h2>
          )}
          <div className="sidebar__group">
            {item(
              'corporate',
              href.corporate(workspaceId),
              route.kind === 'corporate',
              'Corporate data',
              <Icon.Warehouse className="sidebar__icon" />,
            )}
          </div>
        </section>

        <section className="sidebar__section">
          {!collapsed && (
            <h2 className="sidebar__heading">
              <Icon.Grid className="sidebar__heading-icon" />
              <span>Development</span>
            </h2>
          )}
          <div className="sidebar__group">
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
        </section>
      </div>

      <UserArea collapsed={collapsed} />
    </nav>
  )
}

/**
 * The inbox entry, with what is waiting counted on it (AU-4a: approvals and
 * update requests are one pending-task record, so this is ONE number).
 * Separate from the `item` helper only because of the badge; the collapsed
 * behaviour is identical.
 */
function InboxLink({
  workspaceId,
  active,
  collapsed,
}: {
  workspaceId: string
  active: boolean
  collapsed: boolean
}) {
  const count = useSpineStore((s) => waitingCount(s.tasks))
  const label = count > 0 ? `Inbox, ${count} waiting` : 'Inbox'
  return (
    <a
      className={`sidebar__link${active ? ' sidebar__link--active' : ''}`}
      href={href.inbox(workspaceId)}
      {...(collapsed ? { title: label, 'aria-label': label } : {})}
    >
      <Icon.Inbox className="sidebar__icon" />
      {!collapsed && <span className="sidebar__label">Inbox</span>}
      {!collapsed && count > 0 && <span className="sidebar__badge">{count}</span>}
    </a>
  )
}

const PERSONA_KEY = 'frame-dev-persona'
const PERSONAS = ['risk@unops.org', 'dev@unops.org']

/**
 * The fixed user area at the sidebar's foot — Bob's organization: avatar and
 * identity below the scroll, separated by a hairline, present in the rail as
 * the avatar alone.
 *
 * Development only, and eliminated from a production bundle by
 * `import.meta.env.DEV`: today the identity shown IS the dev persona switch,
 * because the product's central claim is that two people see different things,
 * and a demonstration that needs two Google accounts is one nobody runs. The
 * server still refuses any identity not on its allow-list. When real sign-in
 * state reaches the client, this area shows it and the select goes.
 */
function UserArea({ collapsed }: { collapsed: boolean }) {
  const [persona, setPersona] = useState(
    () => globalThis.sessionStorage?.getItem(PERSONA_KEY) ?? PERSONAS[0],
  )

  if (!import.meta.env.DEV) return null

  const initial = (persona ?? '?').charAt(0).toUpperCase()

  return (
    <div className="sidebar__user">
      <span className="sidebar__avatar" aria-hidden="true" title={persona}>
        {initial}
      </span>
      {!collapsed && (
        <>
          <select
            className="sidebar__user-select"
            aria-label="Viewing as"
            value={persona}
            onChange={(e) => {
              globalThis.sessionStorage?.setItem(PERSONA_KEY, e.target.value)
              setPersona(e.target.value)
              // A full reload, deliberately. Identity changes what every open
              // request may return, and patching a page in place after it
              // changes would leave the previous person's rows on screen
              // beside the new person's header.
              globalThis.location.reload()
            }}
          >
            {PERSONAS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <span className="sidebar__dev-pill" title="Development persona switch">
            dev
          </span>
        </>
      )}
    </div>
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
