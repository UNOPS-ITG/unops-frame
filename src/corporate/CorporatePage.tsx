/**
 * The corporate-data catalogue, as a person sees it.
 *
 * Two things live here, and the order is deliberate: the connection first,
 * because nothing below it works without one, then the catalogue.
 *
 * The catalogue is **discovered, not authored**. Nobody registers a dimension —
 * an admin registers a BigQuery project and a scheduled sweep reads the data
 * team's own metadata (`Metadata_Api`, plus `INFORMATION_SCHEMA` as ground
 * truth) and keeps this list current. So this page is a view onto a machine's
 * findings, and the two questions it has to answer are the ones a person
 * actually asks: *what can I bind to*, and *why not this one*.
 *
 * `reasons` is why the second question is answerable at all. The disclosure
 * classifier assigns `open` or `entitled` by mechanical probe and never by
 * assertion, and it records why. Without that, "why can I not pick from this?"
 * needs someone to re-run a probe with credentials the asker does not have.
 *
 * **Search is on the server**, and that is a measurement rather than a
 * preference: the real warehouse is 555 dimensions and 388 facts, and shipping
 * all of them with their column lists is 2.1 MB before anything renders.
 */

import { useEffect, useRef, useState } from 'react'
import {
  ApiError,
  disconnect,
  getConnection,
  getDimension,
  getFact,
  listDimensions,
  listFacts,
  connectUrl,
  type CataloguePage,
  type Connection,
  type CorporateDimension,
  type CorporateFact,
} from '@/api/client'
import { Icon } from '@/app/icons'
import { Empty, Failed, Loading } from '@/registers/states'
import './CorporatePage.css'

/** Long enough not to fire per character, short enough not to feel laggy. */
const DEBOUNCE_MS = 200

export interface CorporatePageProps {
  workspaceId: string
}

export function CorporatePage({ workspaceId }: CorporatePageProps) {
  const [term, setTerm] = useState('')
  const [dimensions, setDimensions] = useState<CataloguePage<CorporateDimension> | null>(null)
  const [facts, setFacts] = useState<CataloguePage<CorporateFact> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const inFlight = useRef<AbortController | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => {
      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller

      // Everything in the catalogue, not only what is bindable. A list that
      // silently omits the relation someone is looking for sends them to ask a
      // human why it is missing; showing it with its reason answers that here.
      // The full slim catalogue (no column lists — ~45 KB measured), because
      // the page groups by business domain and a section computed over a
      // truncated page shows counts that are quietly wrong.
      Promise.all([
        listDimensions(workspaceId, { bindableOnly: false, q: term, limit: 1000 }, controller.signal),
        listFacts(workspaceId, { bindableOnly: false, q: term, limit: 1000 }, controller.signal),
      ])
        .then(([d, f]) => {
          if (controller.signal.aborted) return
          setDimensions(d)
          setFacts(f)
          // Cleared on success rather than before the request: clearing up front
          // repaints the failure away and leaves a blank screen for the length
          // of the request, so a retry looks like it did nothing.
          setError(null)
        })
        .catch((e: unknown) => {
          if (controller.signal.aborted) return
          setDimensions({ items: [], total: 0, matched: 0 })
          setFacts({ items: [], total: 0, matched: 0 })
          setError(e instanceof ApiError ? e.message : 'The catalogue could not be read')
        })
    }, DEBOUNCE_MS)

    return () => clearTimeout(timer)
  }, [workspaceId, term, attempt])

  useEffect(() => () => inFlight.current?.abort(), [])

  if (dimensions === null || facts === null) return <Loading label="Reading the catalogue" />

  if (error !== null && dimensions.total === 0) {
    return (
      <Failed
        title="The catalogue could not be read"
        detail={error}
        onRetry={() => setAttempt((a) => a + 1)}
      />
    )
  }

  const nothingSwept = dimensions.total === 0 && facts.total === 0

  return (
    <div className="corporate">
      <div className="corporate__inner">
        <ConnectionCard />

        {nothingSwept ? (
          <Empty title="Nothing swept yet">
            An admin registers a BigQuery source and the scheduled sweep fills
            this in — reading the data team&rsquo;s own catalogue rather than
            asking anyone to re-describe it here.
          </Empty>
        ) : (
          <>
            <div className="corporate__search">
              <Icon.Search />
              <input
                className="ops-input"
                type="search"
                value={term}
                placeholder="Search the catalogue"
                aria-label="Search the catalogue"
                onChange={(e) => setTerm(e.target.value)}
              />
            </div>

            <Section
              title="Master data"
              page={dimensions}
              noun="dimension"
              searching={term.trim() !== ''}
              lead="A Blueprint field can look up any of these. Frame stores the key and,
                where the label is disclosable to everyone, a snapshot of it — which is
                what lets the grid filter, sort, group, export and search without touching
                the warehouse."
              renderItem={(d) => (
                <RelationCard
                  key={d.id}
                  workspaceId={workspaceId}
                  kind="dimension"
                  relation={d}
                  detail={
                    d.businessKey
                      ? `keyed by ${d.businessKey}`
                      : 'no business key — cannot be bound'
                  }
                />
              )}
            />

            <Section
              title="Corporate figures"
              page={facts}
              noun="fact"
              searching={term.trim() !== ''}
              lead={
                <>
                  Read at the grain the data team declared, never computed.{' '}
                  <strong>Frame never aggregates</strong>: a number here is the number
                  the warehouse holds.
                </>
              }
              renderItem={(f) => (
                <RelationCard
                  key={f.id}
                  workspaceId={workspaceId}
                  kind="fact"
                  relation={f}
                  detail={
                    f.grain.length > 0
                      ? `at ${f.grain.length} grain ${f.grain.length === 1 ? 'key' : 'keys'}`
                      : 'no declared grain — cannot be bound'
                  }
                />
              )}
            />
          </>
        )}
      </div>
    </div>
  )
}

/**
 * A catalogue section, grouped by business domain.
 *
 * 556 identical cards in one wall was the review's sharpest structural
 * finding. The data team already assigns every relation to a business domain,
 * so the catalogue speaks that language: eight scannable headers instead of
 * five hundred cards. Domains start collapsed; a search opens every matched
 * domain, because a result hidden behind a closed header is a search that
 * looks like it found nothing.
 */
function Section<T extends RelationLike>({
  title,
  page,
  noun,
  lead,
  searching,
  renderItem,
}: {
  title: string
  page: CataloguePage<T>
  noun: string
  lead: React.ReactNode
  searching: boolean
  renderItem: (item: T) => React.ReactNode
}) {
  const domains = new Map<string, T[]>()
  for (const item of page.items) {
    const domain = item.businessDomain ?? 'Unassigned'
    const bucket = domains.get(domain)
    if (bucket) bucket.push(item)
    else domains.set(domain, [item])
  }

  return (
    <section>
      <h2 className="corporate__section-title">
        {title}
        <span className="corporate__count">
          {page.matched.toLocaleString()} of {page.total.toLocaleString()} {noun}s
        </span>
      </h2>
      <p className="corporate__lead">{lead}</p>

      {page.items.length === 0 ? (
        <p className="corporate__lead" style={{ marginBlockStart: 'var(--spacing-3)' }}>
          No {noun} matches.
        </p>
      ) : (
        <div className="corporate__domains">
          {[...domains.entries()]
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([domain, items]) => (
              // Keyed on the search state as well as the name: `open` on
              // <details> is only an INITIAL value, so without the key a
              // search could never re-open a section the user had collapsed.
              <details key={`${domain}-${searching}`} className="domain" open={searching}>
                <summary className="domain__summary">
                  <Icon.Chevron className="domain__chevron" />
                  <span className="domain__name">{domain}</span>
                  <span className="domain__count">
                    {items.length.toLocaleString()} {items.length === 1 ? noun : `${noun}s`}
                  </span>
                </summary>
                <div className="relations">{items.map(renderItem)}</div>
              </details>
            ))}
        </div>
      )}
    </section>
  )
}

/**
 * Upstream catalogue text arrives with U+FFFD replacement characters where the
 * warehouse's own descriptions were mis-encoded ("OPS ��� FTA"). The original
 * bytes are gone — the honest render is a dash, not a guess, and definitely
 * not the replacement glyph, which reads as a Frame rendering bug.
 */
function clean(text: string): string {
  return text.replace(/�+/g, '–')
}

interface RelationLike {
  id: string
  label: string
  description: string | null
  businessDomain: string | null
  dataSteward: string | null
  disclosure: 'open' | 'entitled'
  bindable: boolean
  reasons: string[]
}

function RelationCard({
  workspaceId,
  kind,
  relation,
  detail,
}: {
  workspaceId: string
  kind: 'dimension' | 'fact'
  relation: RelationLike
  detail: string
}) {
  const [open, setOpen] = useState(false)
  const [loaded, setLoaded] = useState<{ columns: string[]; reasons: string[] } | null>(null)

  // Fetched on expand rather than with the list. Columns and the classifier's
  // reasons are the bulk of the payload — the reasons are probe transcripts,
  // and carrying them on every list row made the browse payload 417 KB — and
  // almost nobody opens a card, so listing them eagerly pays the whole cost
  // for the rare case.
  const expand = () => {
    setOpen((o) => !o)
    if (loaded !== null) return

    const load =
      kind === 'dimension'
        ? getDimension(workspaceId, relation.id).then((d) => ({
            columns: d.attributes.map(
              (a) => `${clean(a.label)}${a.restricted ? ' (restricted)' : ''}`,
            ),
            reasons: d.reasons,
          }))
        : getFact(workspaceId, relation.id).then((f) => ({
            columns: f.measures.map(
              (m) => `${clean(m.label)}${m.restricted ? ' (restricted)' : ''}`,
            ),
            reasons: f.reasons,
          }))

    load.then(setLoaded).catch(() => setLoaded({ columns: [], reasons: [] }))
  }

  return (
    <div className="relation">
      <button type="button" className="relation__trigger" aria-expanded={open} onClick={expand}>
        <span className="relation__head">
          <span className="relation__label">{relation.label}</span>
          <Disclosure value={relation.disclosure} />
        </span>

        {/* Suppressed when it merely repeats the label, which in the real
            catalogue it very often does — `Dimensions_Api.Absence` is labelled
            "Absence Code Table" and described "Absence Code Table". Printing
            both makes every card look like a rendering bug. */}
        {relation.description && relation.description !== relation.label && (
          <span className="relation__description">{clean(relation.description)}</span>
        )}

        <span className="relation__meta">
          <span>{relation.id}</span>
          {relation.businessDomain && <span>· {relation.businessDomain}</span>}
          <span>· {detail}</span>
        </span>
      </button>

      {open && (
        <div className="relation__detail">
          {/* One human sentence, not the probe transcript. The raw classifier
              output ("probe error: could not read row access policies…") is
              operator telemetry, and dumping it on a Blueprint author was the
              review's sharpest craft finding. It stays one click away — the
              classifier recorded it precisely so "why?" is answerable — but it
              is an answer to a question, not the greeting. */}
          <p className="relation__verdict">
            {relation.disclosure === 'open'
              ? 'Anyone signed in may see these values, so Frame serves them from its own snapshot at grid speed.'
              : 'Access varies by person — or could not be confirmed for everyone — so values resolve live in your own BigQuery context and are never cached.'}
            {!relation.bindable && ' Not currently bindable.'}
          </p>

          {relation.dataSteward && (
            <span className="relation__fact">Steward: {relation.dataSteward}</span>
          )}
          {loaded === null ? (
            <span className="relation__fact">Loading…</span>
          ) : loaded.columns.length > 0 ? (
            <span className="relation__fact">{loaded.columns.join(', ')}</span>
          ) : null}

          {loaded !== null && loaded.reasons.length > 0 && (
            <details className="relation__why">
              <summary>Why this classification?</summary>
              {loaded.reasons.map((reason) => (
                <span key={reason} className="relation__fact">
                  · {clean(reason)}
                </span>
              ))}
            </details>
          )}
        </div>
      )}
    </div>
  )
}

function Disclosure({ value }: { value: 'open' | 'entitled' }) {
  const open = value === 'open'
  return (
    <span
      className={`disclosure ${open ? 'disclosure--open' : 'disclosure--entitled'}`}
      title={
        open
          ? 'Every authenticated staff member may see these values, so Frame may cache a label.'
          : 'Values vary by principal, or the audience question could not be answered mechanically. Resolved live, in your own context, and never cached.'
      }
    >
      {open ? <Icon.Check /> : <Icon.Lock />}
      {open ? 'open' : 'entitled'}
    </span>
  )
}

/**
 * The BigQuery connection.
 *
 * Consent is the user's, granted once, and used in every workspace they work
 * in — so this is not workspace-scoped. Connecting opens a popup rather than
 * navigating, because losing an open register to an OAuth round trip is a real
 * cost for a step most people take once.
 */
function ConnectionCard() {
  const [connection, setConnection] = useState<Connection | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const refresh = () => {
    getConnection()
      .then(setConnection)
      .catch(() => setConnection({ connected: false, email: null, grantedAt: null, scopes: [] }))
  }

  useEffect(refresh, [])

  const connect = () => {
    const popup = globalThis.open(connectUrl(), 'frame-bigquery-consent', 'width=520,height=680')
    if (!popup) {
      setNotice('Your browser blocked the consent window. Allow popups for this site and try again.')
      return
    }
    // Polled rather than driven by a message from the popup: the callback page
    // is served by the API and closing itself is all it needs to do. A
    // postMessage handshake would be one more thing to get wrong for no gain.
    const timer = setInterval(() => {
      if (popup.closed) {
        clearInterval(timer)
        refresh()
      }
    }, 500)
  }

  if (connection === null) return null

  return (
    <div className="connection">
      <span className="connection__icon" aria-hidden="true">
        <Icon.Warehouse />
      </span>
      <div className="connection__body">
        <p className="connection__title">
          {connection.connected ? 'BigQuery connected' : 'BigQuery not connected'}
        </p>
        <p className="connection__detail">
          {connection.connected ? (
            <>
              Corporate data is read as {connection.email ?? 'you'}, so BigQuery&rsquo;s
              own row and column policies decide what you see. Frame implements
              none of it.
            </>
          ) : (
            <>
              Frame reads corporate data in your own context rather than as a
              service account — so the warehouse&rsquo;s policies are the
              enforcement point, and you see exactly what you are entitled to
              see. Read-only access is all Frame asks for.
            </>
          )}
        </p>
        {notice !== null && (
          <p className="connection__detail" role="alert">
            {notice}
          </p>
        )}
      </div>

      {connection.connected ? (
        <button
          type="button"
          className="btn btn--secondary btn--sm"
          disabled={busy}
          onClick={() => {
            setBusy(true)
            disconnect()
              .then(setConnection)
              .catch(() => setNotice('The connection could not be removed'))
              .finally(() => setBusy(false))
          }}
        >
          Disconnect
        </button>
      ) : (
        <button type="button" className="btn btn--primary btn--sm" onClick={connect}>
          Connect BigQuery
        </button>
      )}
    </div>
  )
}
