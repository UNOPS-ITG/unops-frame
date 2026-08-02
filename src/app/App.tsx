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
      <Page route={route} />
    </AppShell>
  )
}

function Page({ route }: { route: Route }) {
  switch (route.kind) {
    case 'register':
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
    case 'fields':
      return <FieldsPage workspaceId={route.workspaceId} blueprintId={route.blueprintId} />
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
    case 'corporate':
      return 'Corporate data'
    default:
      return 'Workspace'
  }
}

function actionsFor(route: Route) {
  if (route.kind === 'register') {
    return (
      <a className="btn btn--secondary btn--sm" href={href.fields(route.workspaceId, route.blueprintId)}>
        <Icon.Fields />
        Fields
      </a>
    )
  }
  if (route.kind === 'fields') {
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
