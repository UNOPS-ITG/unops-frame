/**
 * Where you are in Frame, parsed from the URL.
 *
 * Still hash-based and still not a router library. The reason has changed
 * though: it used to be "there are no real routes yet", and now it is that
 * every route here is a plain function of a string, the whole set fits on one
 * screen, and a library would add a dependency and a rendering model to solve a
 * problem that is currently four regexes.
 *
 * What matters more than the mechanism is that a route is **parsed once into a
 * typed value**. A component asking `route.kind === 'register'` cannot then read
 * a workspace id that is undefined, which is the failure mode of passing raw
 * strings around and checking them at each use.
 */

export type Route =
  | { kind: 'workspace'; workspaceId: string }
  | { kind: 'register'; workspaceId: string; blueprintId: string; viewId?: string }
  | { kind: 'fields'; workspaceId: string; blueprintId: string }
  | { kind: 'corporate'; workspaceId: string }
  | { kind: 'tokens' }
  | { kind: 'harness' }

export const DEFAULT_WORKSPACE = 'ws-demo'

/**
 * The one place a URL becomes a Route.
 *
 * Unrecognised hashes fall back to the workspace rather than to a 404 screen.
 * A governed register is not a public website: someone arriving at a stale link
 * wants the thing they were looking at, and an error page that offers no way
 * forward is worse than landing one level up.
 */
export function parseRoute(hash: string): Route {
  const legacy = parseLegacy(hash)
  if (legacy) return legacy

  const path = hash.replace(/^#\/?/, '')
  const segments = path.split('/').filter(Boolean)

  if (segments[0] === 'tokens') return { kind: 'tokens' }
  if (segments[0] === 'harness') return { kind: 'harness' }

  if (segments[0] === 'w' && segments[1]) {
    const workspaceId = segments[1]

    if (segments[2] === 'corporate') return { kind: 'corporate', workspaceId }

    if (segments[2] === 'b' && segments[3]) {
      const blueprintId = segments[3]
      if (segments[4] === 'fields') return { kind: 'fields', workspaceId, blueprintId }
      if (segments[4] === 'v' && segments[5]) {
        return { kind: 'register', workspaceId, blueprintId, viewId: segments[5] }
      }
      return { kind: 'register', workspaceId, blueprintId }
    }

    return { kind: 'workspace', workspaceId }
  }

  return { kind: 'workspace', workspaceId: DEFAULT_WORKSPACE }
}

/**
 * The pre-shell URL shapes, still honoured.
 *
 * `#register/ws/bp` and `#view/ws/bp/v` were the routes before there was an
 * application around the grid. They are kept working rather than retired
 * because they are printed by the seed script, opened by the demo harness, and
 * — more to the point — pasted into chat messages by people. A link that used
 * to work and now silently lands somewhere else is worse than one that 404s.
 */
function parseLegacy(hash: string): Route | null {
  const view = /^#view\/([^/]+)\/([^/]+)\/([^/]+)$/.exec(hash)
  if (view?.[1] && view[2] && view[3]) {
    return { kind: 'register', workspaceId: view[1], blueprintId: view[2], viewId: view[3] }
  }

  const register = /^#register\/([^/]+)\/([^/]+)$/.exec(hash)
  if (register?.[1] && register[2]) {
    return { kind: 'register', workspaceId: register[1], blueprintId: register[2] }
  }

  if (hash === '#tokens') return { kind: 'tokens' }
  return null
}

/** Building a URL, so no component concatenates one by hand. */
export const href = {
  workspace: (ws: string) => `#/w/${ws}`,
  register: (ws: string, bp: string) => `#/w/${ws}/b/${bp}`,
  view: (ws: string, bp: string, view: string) => `#/w/${ws}/b/${bp}/v/${view}`,
  fields: (ws: string, bp: string) => `#/w/${ws}/b/${bp}/fields`,
  corporate: (ws: string) => `#/w/${ws}/corporate`,
  tokens: () => '#/tokens',
  harness: () => '#/harness',
}

export function workspaceOf(route: Route): string {
  return 'workspaceId' in route ? route.workspaceId : DEFAULT_WORKSPACE
}

export function navigate(to: string): void {
  globalThis.location.hash = to
}
