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
  if (typeof secret !== 'string' || secret === '') return {}

  const headers: Record<string, string> = { 'X-Dev-Auth-Bypass': secret }
  // Lets one browser act as a chosen persona, which is what makes the
  // "two people, one URL" demonstration reproducible without two real Google
  // accounts. The server still refuses any identity not on its allow-list, so
  // this selects among sanctioned identities rather than asserting one.
  const persona = globalThis.sessionStorage?.getItem('frame-dev-persona')
  if (persona) headers['X-Dev-Auth-Email'] = persona
  return headers
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

/** What the sidebar lists. The full Blueprint is the same shape, so this is a
 * narrowing rather than a second endpoint. */
export type BlueprintSummary = Pick<Blueprint, 'id' | 'name' | 'version' | 'tier'>

export function listBlueprints(workspaceId: string): Promise<Blueprint[]> {
  return request(`/workspaces/${workspaceId}/blueprints`)
}

// --- corporate data -------------------------------------------------------

export interface CorporateAttribute {
  name: string
  label: string
  dataType: string
  role: string
  isBusinessKey: boolean
  restricted: boolean
}

export interface CorporateDimension {
  id: string
  label: string
  description: string | null
  businessDomain: string | null
  dataSteward: string | null
  businessKey: string | null
  disclosure: 'open' | 'entitled'
  bindable: boolean
  reasons: string[]
  attributes: CorporateAttribute[]
}

export interface CorporateFact {
  id: string
  label: string
  description: string | null
  businessDomain: string | null
  dataSteward: string | null
  grain: string[]
  disclosure: 'open' | 'entitled'
  bindable: boolean
  reasons: string[]
  measures: { name: string; label: string; dataType: string; restricted: boolean }[]
}

/**
 * A page of the catalogue.
 *
 * `matched` is separate from `items.length` on purpose: a truncated list that
 * does not say so reads as the whole answer, and someone then concludes the
 * relation they wanted does not exist.
 */
export interface CataloguePage<T> {
  items: T[]
  /** Everything in scope, before the search term. */
  total: number
  /** What the term matched, which may exceed what was returned. */
  matched: number
}

export interface CatalogueQuery {
  bindableOnly?: boolean
  q?: string
  limit?: number
}

/**
 * Searched and paged on the server, and without column lists.
 *
 * The real warehouse is 555 dimensions and 388 facts; returning every one with
 * its columns is 2.1 MB to render a browse page. Columns arrive from the detail
 * endpoint when a relation is actually opened.
 */
export function listDimensions(
  workspaceId: string,
  { bindableOnly = true, q = '', limit }: CatalogueQuery = {},
  signal?: AbortSignal,
): Promise<CataloguePage<CorporateDimension>> {
  return request(
    `/workspaces/${workspaceId}/corporate/dimensions?${catalogueParams(bindableOnly, q, limit)}`,
    signal ? { signal } : {},
  )
}

export function listFacts(
  workspaceId: string,
  { bindableOnly = true, q = '', limit }: CatalogueQuery = {},
  signal?: AbortSignal,
): Promise<CataloguePage<CorporateFact>> {
  return request(
    `/workspaces/${workspaceId}/corporate/facts?${catalogueParams(bindableOnly, q, limit)}`,
    signal ? { signal } : {},
  )
}

function catalogueParams(bindableOnly: boolean, q: string, limit: number | undefined): string {
  const params = new URLSearchParams({ bindableOnly: String(bindableOnly) })
  if (q !== '') params.set('q', q)
  if (limit !== undefined) params.set('limit', String(limit))
  return params.toString()
}

/** One dimension, with its columns. */
export function getDimension(
  workspaceId: string,
  dimensionId: string,
): Promise<CorporateDimension> {
  return request(
    `/workspaces/${workspaceId}/corporate/dimensions/${encodeURIComponent(dimensionId)}`,
  )
}

/** One fact, with its measures. */
export function getFact(workspaceId: string, factId: string): Promise<CorporateFact> {
  return request(`/workspaces/${workspaceId}/corporate/facts/${encodeURIComponent(factId)}`)
}

export interface LookupRow {
  key: string
  label: string
}

export interface LookupResult {
  rows: LookupRow[]
  /** The limit was reached. Shown, because a picker listing the first 25 of 900
   * matches and saying so is usable, and one that implies 25 is all of them is
   * misleading. */
  truncated: boolean
  context: string
}

/**
 * The picker's typeahead, resolved in the caller's own warehouse context.
 *
 * Debounced by the caller, never per keystroke. At BigQuery's best-case
 * ~300–400ms per interactive query, a query per keystroke is not slow, it is
 * unusable — and the latency is not fixable warehouse-side, because results are
 * not cached for tables under row-level security.
 */
export function searchDimension(
  workspaceId: string,
  dimensionId: string,
  prefix: string,
  limit = 25,
  signal?: AbortSignal,
): Promise<LookupResult> {
  const params = new URLSearchParams({ q: prefix, limit: String(limit) })
  return request(
    `/workspaces/${workspaceId}/corporate/dimensions/${encodeURIComponent(dimensionId)}/search?${params}`,
    signal ? { signal } : {},
  )
}

export interface Connection {
  connected: boolean
  email: string | null
  grantedAt: string | null
  scopes: string[]
}

export function getConnection(): Promise<Connection> {
  return request('/corporate/connection')
}

export function disconnect(): Promise<Connection> {
  return request('/corporate/connection', { method: 'DELETE' })
}

/** The consent flow is a redirect, so it cannot go through `fetch`. */
export function connectUrl(): string {
  return `${BASE}/corporate/connection/start`
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

export interface SavedView {
  id: string
  name: string
  scope: 'personal' | 'shared' | 'default'
  author: string
  filter: Record<string, unknown> | null
  sort: { fieldId: string; direction: 'asc' | 'desc' }[]
  columns: { fieldId: string; width?: number; hidden?: boolean }[]
  groupBy: string | null
  rowHeight: string
  blueprintVersion: number
  isMine: boolean
  /** Non-fatal problems, carried on the view rather than only reported at save
   * time — the person who opens a view is rarely the person who saved it. */
  warnings: { code: string; message: string; fieldId: string | null }[]
}

export function listViews(workspaceId: string, blueprintId: string): Promise<SavedView[]> {
  return request(`/workspaces/${workspaceId}/blueprints/${blueprintId}/views`)
}

export interface NewView {
  name: string
  scope?: 'personal' | 'shared' | 'default'
  filter?: Record<string, unknown> | null
  sort?: { fieldId: string; direction: 'asc' | 'desc' }[]
}

/**
 * Save a view.
 *
 * Defaults to `personal`, because a view saved to try something out should not
 * appear in a colleague's list. Sharing is a separate, deliberate act.
 */
export function createView(
  workspaceId: string,
  blueprintId: string,
  view: NewView,
): Promise<SavedView> {
  return request(`/workspaces/${workspaceId}/blueprints/${blueprintId}/views`, {
    method: 'POST',
    body: JSON.stringify({
      name: view.name,
      scope: view.scope ?? 'personal',
      filter: view.filter ?? null,
      sort: view.sort ?? [],
      columns: [],
    }),
  })
}

/**
 * Rows through a saved view.
 *
 * The demonstration endpoint: two principals calling this with the same view id
 * get the same query and different results, because the query is the view's and
 * the Decision is theirs.
 */
export function readViewRows(
  workspaceId: string,
  blueprintId: string,
  viewId: string,
  options: { limit?: number; cursor?: string | null } = {},
): Promise<RowPage> {
  const params = new URLSearchParams({ limit: String(options.limit ?? 100) })
  if (options.cursor) params.set('cursor', options.cursor)
  return request(
    `/workspaces/${workspaceId}/blueprints/${blueprintId}/views/${viewId}/rows?${params}`,
  )
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

export interface ImportResult {
  dryRun: boolean
  parsedRows: number
  validRows: number
  writtenRows: number
  unmappedColumns: string[]
  errors: { line: number; fieldId: string | null; message: string; code: string }[]
  truncatedErrors: number
}

/**
 * Import a CSV.
 *
 * Defaults to a dry run and the UI is built around that: an import that reports
 * its failures only after writing half the file is one the user cannot safely
 * retry, because they cannot tell which rows landed.
 */
export function importCsv(
  workspaceId: string,
  blueprintId: string,
  csv: string,
  dryRun = true,
): Promise<ImportResult> {
  return request(`/workspaces/${workspaceId}/blueprints/${blueprintId}/rows/import`, {
    method: 'POST',
    body: JSON.stringify({ csv, dryRun }),
  })
}

export interface ExportResult {
  csv: string
  visible: number
  withheld: number
  certainty: string
}

export async function exportCsv(
  workspaceId: string,
  blueprintId: string,
  filter: Record<string, unknown> | null = null,
): Promise<ExportResult> {
  const response = await fetch(
    `${BASE}/workspaces/${workspaceId}/blueprints/${blueprintId}/rows/export`,
    {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...devHeaders() },
      body: JSON.stringify({ filter, sort: [], limit: 100, cursor: null }),
    },
  )
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => ({}))
    throw new ApiError(
      response.status,
      typeof body === 'object' && body !== null ? (body as Record<string, unknown>) : {},
    )
  }
  return {
    csv: await response.text(),
    // Read from headers as well as the file trailer, so the UI can state the
    // count without parsing CSV it is about to hand straight to the user.
    visible: Number(response.headers.get('X-Frame-Rows-Visible') ?? 0),
    withheld: Number(response.headers.get('X-Frame-Rows-Withheld') ?? 0),
    certainty: response.headers.get('X-Frame-Count-Certainty') ?? 'exact',
  }
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
