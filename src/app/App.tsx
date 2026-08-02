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
import { ChildCollectionPage } from '@/spine/ChildCollectionPage'
import { CreatedAppPage } from '@/spine/CreatedAppPage'
import { InboxPage } from '@/spine/InboxPage'
import { OverviewPage } from '@/spine/OverviewPage'
import { RecipesPage } from '@/spine/RecipesPage'
import { RecordPage } from '@/spine/RecordPage'
import { spineFor, useSpineStore } from '@/fixtures/spine/store'
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

  // Above the harness early-returns: hooks must run on every render.
  const createdApps = useSpineStore((s) => s.createdApps)

  // Harnesses, unchromed. See the module note.
  if (route.kind === 'tokens') return <TokenGallery />
  if (route.kind === 'harness') return <GridDemo />

  const workspaceId = workspaceOf(route)

  return (
    <AppShell
      route={route}
      workspaceId={workspaceId}
      title={titleOf(route)}
      actions={actionsFor(route, createdApps)}
    >
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
  const createdApps = useSpineStore((s) => s.createdApps)
  if (
    route.kind !== 'register' &&
    route.kind !== 'recipes' &&
    route.kind !== 'fields' &&
    route.kind !== 'record' &&
    route.kind !== 'collection'
  ) {
    return null
  }
  const { workspaceId, blueprintId } = route
  const spine = spineFor(blueprintId)
  if (spine === null && createdApps[blueprintId] === undefined) return null

  const active =
    route.kind === 'recipes'
      ? 'recipes'
      : route.kind === 'fields'
        ? 'fields'
        : route.kind === 'collection'
          ? `c:${route.collectionId}`
          : route.kind === 'record'
            ? 'entity' // a record belongs to its collection
            : route.section === 'overview'
              ? 'overview'
              : 'entity' // every data view — table, board, calendar, gantt

  const tab = (key: string, to: string, label: string, icon: React.ReactNode) => (
    <a key={key} className={`appnav__tab${active === key ? ' appnav__tab--active' : ''}`} href={to}>
      {icon}
      {label}
    </a>
  )

  // An app navigates its ENTITIES — "Risks", "Mitigation actions" — never
  // "Table". The child collections are pages of their own (BP-8): multiple
  // tables joined is what makes this an app rather than a grid with chrome.
  return (
    <nav className="appnav" aria-label="App navigation">
      {tab('overview', href.register(workspaceId, blueprintId), 'Overview', <Icon.Home />)}
      {tab('entity', href.table(workspaceId, blueprintId), spine?.entityLabel ?? 'Rows', <Icon.Table />)}
      {spine?.childTables.map((t) =>
        tab(`c:${t.id}`, href.collection(workspaceId, blueprintId, t.id), t.label, <Icon.Fields />),
      )}
      <span className="appnav__spacer" aria-hidden="true" />
      {tab('recipes', href.recipes(workspaceId, blueprintId), 'Automations', <Icon.Bolt />)}
      {tab('fields', href.fields(workspaceId, blueprintId), 'Fields', <Icon.Fields />)}
    </nav>
  )
}

function Page({ route }: { route: Route }) {
  // Session-born apps render from their reviewed draft until the
  // Blueprint-create engine persists them.
  const createdApps = useSpineStore((s) => s.createdApps)
  if (
    (route.kind === 'register' || route.kind === 'recipes' || route.kind === 'fields') &&
    createdApps[route.blueprintId] !== undefined
  ) {
    return <CreatedAppPage app={createdApps[route.blueprintId]!} route={route} />
  }

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
          // Keyed on the register AND the saved view — but NOT the data-view
          // mode, so switching table→board→gantt keeps the fetched page,
          // filter and selection: that is what makes morphing lossless.
          key={`${route.workspaceId}/${route.blueprintId}/${route.viewId ?? ''}`}
          workspaceId={route.workspaceId}
          blueprintId={route.blueprintId}
          viewId={route.viewId}
          dataView={route.section === 'overview' ? 'table' : route.section}
        />
      )
    }
    case 'fields':
      return <FieldsPage workspaceId={route.workspaceId} blueprintId={route.blueprintId} />
    case 'record': {
      const spine = spineFor(route.blueprintId)
      if (spine === null) return null
      return (
        <RecordPage
          key={`${route.workspaceId}/${route.blueprintId}/${route.rowId}`}
          workspaceId={route.workspaceId}
          blueprintId={route.blueprintId}
          rowId={route.rowId}
          spine={spine}
        />
      )
    }
    case 'collection': {
      const spine = spineFor(route.blueprintId)
      if (spine === null) return null
      return (
        <ChildCollectionPage
          key={`${route.workspaceId}/${route.blueprintId}/${route.collectionId}`}
          workspaceId={route.workspaceId}
          blueprintId={route.blueprintId}
          collectionId={route.collectionId}
          spine={spine}
        />
      )
    }
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
      // The app's own name is not known until it loads, and a header that
      // flickers from an id to a name is worse than one that waits. The page
      // states the name; the shell states where you are.
      return 'App'
    case 'fields':
      return 'Fields'
    case 'recipes':
      return 'Automations'
    case 'record':
      return 'Record'
    case 'collection':
      return 'Collection'
    case 'inbox':
      return 'Inbox'
    case 'corporate':
      return 'Corporate data'
    default:
      return 'Workspace'
  }
}

function actionsFor(route: Route, createdApps: Record<string, unknown>) {
  // App-family navigation lives in the app tabs (RegisterTabs); the header
  // keeps links only for apps that have no tabs — neither a spine nor a
  // session draft.
  const hasTabs = (bp: string) => spineFor(bp) !== null || createdApps[bp] !== undefined
  if (route.kind === 'register' && !hasTabs(route.blueprintId)) {
    return (
      <a className="btn btn--secondary btn--sm" href={href.fields(route.workspaceId, route.blueprintId)}>
        <Icon.Fields />
        Fields
      </a>
    )
  }
  if ((route.kind === 'fields' || route.kind === 'recipes') && !hasTabs(route.blueprintId)) {
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
