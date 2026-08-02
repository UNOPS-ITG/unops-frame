/**
 * The API client.
 *
 * Hand-written and tiny, on purpose. A generated client would need a build step
 * keyed on a Blueprint version, and Frame's claim is that publishing a
 * Blueprint takes effect immediately — the per-Blueprint OpenAPI document
 * exists for *integrators*, who do want generated types and do accept a build.
 *
 * Every response here is already trimmed and annotated by the server. The
 * client's job is to carry it, not to interpret it.
 */

import type { Blueprint, Delta, RowPage } from '../grid/contract'

/**
 * Relative, and that is load-bearing rather than tidy.
 *
 * Vite proxies `/api` to the backend in development and the deployed frontend
 * is served behind the same origin as the API, so requests are same-origin in
 * both — which means the session cookie and the IAP assertion header behave
 * identically. An absolute `http://localhost:<port>` would make every local
 * request cross-origin and hide CORS and cookie problems until deployment.
 *
 * It also keeps `config/ports.mjs` out of the browser bundle. That module reads
 * `node:fs` and `process.env`, so importing it here would either fail to build
 * or drag a polyfill in.
 */
const BASE = '/api/v1'

/** How a write reached the server. Recorded on the audit entry (PM-7), because
 * "changed by Maya" and "changed by an import Maya started" are different facts
 * a reviewer needs to tell apart. */
export type Channel = 'grid' | 'form' | 'api' | 'import' | 'undo'

export class ApiError extends Error {
  // Written out rather than declared as constructor parameter properties:
  // `erasableSyntaxOnly` is on, so the build refuses syntax that emits code.
  readonly status: number
  readonly body: Record<string, unknown>

  constructor(status: number, body: Record<string, unknown>) {
    super(typeof body.detail === 'string' ? body.detail : `Request failed (${status})`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }

  /** A concurrent edit took the same cell (GR-8). The body names which fields
   * were lost and what won, so the UI can offer the value back rather than
   * discarding what the user typed. */
  get isConflict(): boolean {
    return this.status === 412
  }

  get conflictFields(): string[] {
    return Array.isArray(this.body.fields) ? (this.body.fields as string[]) : []
  }

  get currentValues(): Record<string, unknown> {
    return (this.body.current as Record<string, unknown>) ?? {}
  }

  /** Per-field validation failures, all of them. Reporting one at a time makes
   * a wide form a guessing game. */
  get fieldErrors(): { fieldId: string; message: string; code: string }[] {
    return Array.isArray(this.body.errors)
      ? (this.body.errors as { fieldId: string; message: string; code: string }[])
      : []
  }
}

/**
 * The local bypass header, in development builds only.
 *
 * `import.meta.env.DEV` is statically replaced at build time, so the whole
 * branch is eliminated from a production bundle — the header cannot be shipped
 * by accident. The server gates it independently (LOCAL environment, a secret,
 * and an allow-list of identities); this is the client half of a mechanism
 * whose security lives on the other side.
 */
function devHeaders(): Record<string, string> {
  if (!import.meta.env.DEV) return {}
  const secret = import.meta.env.VITE_DEV_AUTH_BYPASS_SECRET
  return typeof secret === 'string' && secret !== '' ? { 'X-Dev-Auth-Bypass': secret } : {}
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    // Same-origin, so the session cookie rides automatically. Stated explicitly
    // anyway, because the default varies by fetch implementation and a silent
    // change here presents as an unexplained 401.
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...devHeaders(), ...init.headers },
  })

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => ({}))
    throw new ApiError(
      response.status,
      typeof body === 'object' && body !== null ? (body as Record<string, unknown>) : {},
    )
  }
  return response.json() as Promise<T>
}

export function getBlueprint(workspaceId: string, blueprintId: string): Promise<Blueprint> {
  return request(`/workspaces/${workspaceId}/blueprints/${blueprintId}`)
}

export interface QueryOptions {
  filter?: Record<string, unknown>
  sort?: { fieldId: string; direction: 'asc' | 'desc' }[]
  limit?: number
  /** Opaque, and deliberately so. A cursor a client can read is a cursor a
   * client will construct, and a constructed cursor is an unvalidated store
   * position. */
  cursor?: string | null
}

export function queryRows(
  workspaceId: string,
  blueprintId: string,
  options: QueryOptions = {},
): Promise<RowPage> {
  return request(`/workspaces/${workspaceId}/blueprints/${blueprintId}/rows/query`, {
    method: 'POST',
    body: JSON.stringify({
      filter: options.filter ?? null,
      sort: options.sort ?? [],
      limit: options.limit ?? 100,
      cursor: options.cursor ?? null,
    }),
  })
}

/**
 * A field-scoped write.
 *
 * `values` carries only what changed, and `fieldVersions` carries what the
 * client believes it read. Sending the whole row cannot express last-write-wins
 * per cell, so two people editing different cells would lose an edit.
 */
export function updateRow(
  workspaceId: string,
  blueprintId: string,
  rowId: string,
  values: Record<string, unknown>,
  fieldVersions: Record<string, number> | null,
  channel: Channel = 'grid',
): Promise<{ id: string; changedFields: string[]; fieldVersions: Record<string, number> }> {
  return request(`/workspaces/${workspaceId}/blueprints/${blueprintId}/rows/${rowId}`, {
    method: 'PATCH',
    headers: { 'X-Frame-Channel': channel },
    body: JSON.stringify({ values, fieldVersions }),
  })
}

export function createRow(
  workspaceId: string,
  blueprintId: string,
  values: Record<string, unknown>,
  channel: Channel = 'grid',
): Promise<{ id: string; values: Record<string, unknown> }> {
  return request(`/workspaces/${workspaceId}/blueprints/${blueprintId}/rows`, {
    method: 'POST',
    headers: { 'X-Frame-Channel': channel },
    body: JSON.stringify({ values }),
  })
}

export interface DeltaPage {
  deltas: Delta[]
  since: string | null
  blueprintVersion: number
}

/**
 * What changed since a watermark.
 *
 * `knownRowIds` is what the client currently has on screen, and it is what
 * separates silence from a removal on the server: a row that turns invisible
 * and was never sent needs no delta, and sending one would disclose that
 * something the caller cannot see changed.
 */
export function pollDeltas(
  workspaceId: string,
  blueprintId: string,
  since: string | null,
  knownRowIds: readonly string[],
): Promise<DeltaPage> {
  return request(`/workspaces/${workspaceId}/blueprints/${blueprintId}/rows/deltas`, {
    method: 'POST',
    body: JSON.stringify({ since, knownRowIds: [...knownRowIds] }),
  })
}
