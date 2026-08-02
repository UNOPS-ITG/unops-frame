/**
 * The application.
 *
 * One job: turn the URL into a page, inside one shell. Everything that decides
 * anything is elsewhere — the server evaluates permissions, the pages own their
 * own loading and failure states, and the shell owns the chrome.
 *
 * The two harness surfaces (`#/tokens`, `#/harness`) render *outside* the shell
 * deliberately. They exist to look at raw tokens and a grid with no server, and
 * wrapping them in application chrome would make each of them a test of the
 * chrome as well as of the thing it is meant to isolate.
 */

import { useEffect, useState } from 'react'
import { useThemeStore } from '@/styles/theme'
import { GridDemo } from '@/grid/GridDemo'
import { CorporatePage } from '@/corporate/CorporatePage'
import { RegisterPage } from '@/registers/RegisterPage'
import { InboxPage } from '@/spine/InboxPage'
import { OverviewPage } from '@/spine/OverviewPage'
import { RecipesPage } from '@/spine/RecipesPage'
import { spineFor } from '@/fixtures/spine/store'
import { AppShell } from './AppShell'
import { FieldsPage } from './FieldsPage'
import { TokenGallery } from './TokenGallery'
import { WorkspacePage } from './WorkspacePage'
import { href, parseRoute, workspaceOf, type Route } from './routes'
import { Icon } from './icons'

export function App() {
  const init = useThemeStore((s) => s.init)
  const [route, setRoute] = useState<Route>(() => parseRoute(globalThis.location?.hash ?? ''))

  // Returns a teardown for the prefers-color-scheme listener.
  useEffect(() => init(), [init])

  useEffect(() => {
    const onHashChange = () => setRoute(parseRoute(globalThis.location.hash))
    globalThis.addEventListener('hashchange', onHashChange)
    return () => globalThis.removeEventListener('hashchange', onHashChange)
  }, [])

  // Harnesses, unchromed. See the module note.
  if (route.kind === 'tokens') return <TokenGallery />
  if (route.kind === 'harness') return <GridDemo />

  const workspaceId = workspaceOf(route)

  return (
    <AppShell route={route} workspaceId={workspaceId} title={titleOf(route)} actions={actionsFor(route)}>
      <RegisterTabs route={route} />
      <Page route={route} />
    </AppShell>
  )
}

/**
 * The register's view navigation — what makes it an APP with views rather
 * than a grid with escape hatches. Present on every register-family page
 * so the user never loses the map; absent on registers without a spine,
 * which have only the table today and honestly say so by having no tabs.
 */
function RegisterTabs({ route }: { route: Route }) {
  if (route.kind !== 'register' && route.kind !== 'recipes' && route.kind !== 'fields') return null
  const { workspaceId, blueprintId } = route
  if (spineFor(blueprintId) === null) return null

  const active =
    route.kind === 'recipes'
      ? 'recipes'
      : route.kind === 'fields'
        ? 'fields'
        : route.section === 'table'
          ? 'table'
          : 'overview'

  const tab = (key: string, to: string, label: string, icon: React.ReactNode) => (
    <a key={key} className={`appnav__tab${active === key ? ' appnav__tab--active' : ''}`} href={to}>
      {icon}
      {label}
    </a>
  )

  return (
    <nav className="appnav" aria-label="Register views">
      {tab('overview', href.register(workspaceId, blueprintId), 'Overview', <Icon.Home />)}
      {tab('table', href.table(workspaceId, blueprintId), 'Table', <Icon.Table />)}
      {tab('recipes', href.recipes(workspaceId, blueprintId), 'Automations', <Icon.Bolt />)}
      {tab('fields', href.fields(workspaceId, blueprintId), 'Fields', <Icon.Fields />)}
    </nav>
  )
}

function Page({ route }: { route: Route }) {
  switch (route.kind) {
    case 'register': {
      // The overview is the landing — the grid is the table section. A
      // register without a spine has no overview yet and lands on its
      // table, which is simply the truth of what it has.
      const spine = spineFor(route.blueprintId)
      if (route.section === 'overview' && spine !== null) {
        return (
          <OverviewPage
            key={`${route.workspaceId}/${route.blueprintId}/overview`}
            workspaceId={route.workspaceId}
            blueprintId={route.blueprintId}
            spine={spine}
          />
        )
      }
      return (
        <RegisterPage
          // Keyed on the register AND the view. Without the key, switching
          // registers reuses the component, and its filter, selected row and
          // open picker all survive into a Blueprint where none of them mean
          // anything.
          key={`${route.workspaceId}/${route.blueprintId}/${route.viewId ?? ''}`}
          workspaceId={route.workspaceId}
          blueprintId={route.blueprintId}
          viewId={route.viewId}
        />
      )
    }
    case 'fields':
      return <FieldsPage workspaceId={route.workspaceId} blueprintId={route.blueprintId} />
    case 'recipes':
      return (
        <RecipesPage
          workspaceId={route.workspaceId}
          blueprintId={route.blueprintId}
          spine={spineFor(route.blueprintId)}
        />
      )
    case 'inbox':
      return <InboxPage workspaceId={route.workspaceId} />
    case 'corporate':
      return <CorporatePage workspaceId={route.workspaceId} />
    case 'workspace':
      return <WorkspacePage workspaceId={route.workspaceId} />
    default:
      // The harness routes never reach here — App returns them unchromed above.
      // Exhaustive rather than a fallback, so adding a route without a page is
      // a type error rather than a blank screen.
      return null
  }
}

function titleOf(route: Route): string {
  switch (route.kind) {
    case 'register':
      // The Blueprint's own name is not known until it loads, and a header that
      // flickers from an id to a name is worse than one that waits. The page
      // states the name; the shell states where you are.
      return 'Register'
    case 'fields':
      return 'Fields'
    case 'recipes':
      return 'Automations'
    case 'inbox':
      return 'Inbox'
    case 'corporate':
      return 'Corporate data'
    default:
      return 'Workspace'
  }
}

function actionsFor(route: Route) {
  // Register-family navigation lives in the app tabs (RegisterTabs); the
  // header keeps links only for registers that have no spine and so no tabs.
  if (route.kind === 'register' && spineFor(route.blueprintId) === null) {
    return (
      <a className="btn btn--secondary btn--sm" href={href.fields(route.workspaceId, route.blueprintId)}>
        <Icon.Fields />
        Fields
      </a>
    )
  }
  if ((route.kind === 'fields' || route.kind === 'recipes') && spineFor(route.blueprintId) === null) {
    return (
      <a
        className="btn btn--secondary btn--sm"
        href={href.register(route.workspaceId, route.blueprintId)}
      >
        <Icon.Table />
        Back to the grid
      </a>
    )
  }
  return null
}
