/**
 * The register's front door: an application home, not a grid.
 *
 * The owner's correction that produced this page, recorded so it is never
 * un-learned: "user clicks on risk register, sees a giant grid — that's
 * it." An app answers three questions before showing a single row: what
 * needs ME (the attention rail), what state is the WORK in (tiles and the
 * distribution bar), and how does work GET IN (the intake actions). The
 * table is one view among views, one tab away.
 *
 * Every count on this page is a real server answer with PM-5 annotation —
 * state totals come from three filtered queries whose `annotation.total`
 * includes withheld rows, and the page says so with the lock rather than
 * quietly showing a smaller number. The five queries this costs are the
 * draft contract for a future register-summary endpoint; the shape is what
 * matters, and it is deliberately "annotated totals", never client sums.
 */

import { useEffect, useMemo, useState } from 'react'
import { getBlueprint, queryRows, type QueryOptions } from '@/api/client'
import { Icon } from '@/app/icons'
import { href, navigate } from '@/app/routes'
import type { Blueprint, Row } from '@/grid/contract'
import { formatValue } from '@/grid/cells'
import type { SpineDef, WorkflowState } from '@/fixtures/spine/contracts'
import { activityFor } from '@/fixtures/spine/risk'
import { useSpineStore } from '@/fixtures/spine/store'
import { ActivityFeed } from './ActivityFeed'
import { GeneratedForm } from './GeneratedForm'
import { PreviewPill, StateChip } from './bits'
import './spine.css'

interface StateCount {
  readonly state: WorkflowState
  /** annotation.total for the state filter: visible + withheld, honest. */
  readonly total: number
  readonly withheld: number
  readonly certainty: 'exact' | 'estimated'
}

function eq(fieldId: string, value: unknown): Record<string, unknown> {
  return {
    type: 'binary',
    op: 'eq',
    left: { type: 'field', id: fieldId },
    right: { type: 'literal', value },
  }
}

function sortBy(fieldId: string, direction: 'asc' | 'desc'): NonNullable<QueryOptions['sort']> {
  return [{ fieldId, direction }]
}

export function OverviewPage({
  workspaceId,
  blueprintId,
  spine,
}: {
  workspaceId: string
  blueprintId: string
  spine: SpineDef
}) {
  const tasks = useSpineStore((s) => s.tasks)
  const enabledOverride = useSpineStore((s) => s.recipeEnabled)
  const spineGeneration = useSpineStore((s) => s.generation)

  const [blueprint, setBlueprint] = useState<Blueprint | null>(null)
  const [counts, setCounts] = useState<StateCount[] | null>(null)
  const [stale, setStale] = useState<readonly Row[] | null>(null)
  const [largest, setLargest] = useState<readonly Row[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)

  const waiting = tasks.filter((t) => t.status === 'waiting')
  const recipesOn = spine.recipes.filter((r) => enabledOverride[r.id] ?? r.enabled)
  const runs30d = recipesOn.reduce((sum, r) => sum + r.runs30d, 0)

  useEffect(() => {
    let cancelled = false
    const stateField = spine.workflow.stateField

    Promise.all([
      getBlueprint(workspaceId, blueprintId),
      Promise.all(
        spine.workflow.states.map(async (state) => {
          // limit 500, not 1: the annotation's scope is what was SCANNED,
          // so a tiny limit reports a tiny "total". A full-scan count is
          // fine at demo scale and is exactly the number a register-summary
          // endpoint will one day return in one call.
          const page = await queryRows(workspaceId, blueprintId, {
            filter: eq(stateField, state.key),
            limit: 500,
          })
          return {
            state,
            total: page.annotation.total,
            withheld: page.annotation.withheld,
            certainty: page.annotation.certainty,
          } satisfies StateCount
        }),
      ),
      // Longest-unreviewed first: the queue a review cadence exists to empty.
      queryRows(workspaceId, blueprintId, { sort: sortBy('reviewed', 'asc'), limit: 4 }),
      queryRows(workspaceId, blueprintId, { sort: sortBy('exposure', 'desc'), limit: 4 }),
    ])
      .then(([bp, stateCounts, staleRows, topRows]) => {
        if (cancelled) return
        setBlueprint(bp)
        setCounts(stateCounts)
        setStale(staleRows.rows)
        setLargest(topRows.rows)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'The overview could not load')
      })
    return () => {
      cancelled = true
    }
  }, [workspaceId, blueprintId, spine, spineGeneration])

  const distribution = useMemo(() => {
    if (counts === null) return null
    const sum = counts.reduce((s, c) => s + c.total, 0)
    return { sum, withheld: counts.reduce((s, c) => s + c.withheld, 0) }
  }, [counts])

  // The register-level pulse reuses the row-level scripted history — enough
  // to judge the feel of an app that tells you what happened while you were
  // away; the real feed is PM-7's change stream scoped to the Blueprint.
  const pulse = useMemo(() => activityFor({ owner: 'M. Osei' }).slice(0, 3), [])

  if (error !== null) {
    return (
      <div className="spine-page">
        <div className="spine-page__inner">
          <h2 className="spine-page__title">This register could not be opened</h2>
          <p className="spine-page__lede">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="spine-page">
      <div className="overview">
        {/* The hero says what the app is FOR; the shell header already says
            its name, so repeating it here would be furniture. */}
        <header className="overview__hero">
          <p className="overview__eyebrow">
            {blueprint?.tier ?? 'team'} tier · governed app
            <PreviewPill what="The overview's task list, automation pulse and recent activity" />
          </p>
          <h2 className="overview__purpose">{spine.purpose}</h2>
          <div className="overview__acts">
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => setFormOpen(true)}
              disabled={blueprint === null}
            >
              <Icon.Plus />
              {spine.forms[0]?.name ?? 'New row'}
            </button>
            <a className="btn btn--secondary" href={href.table(workspaceId, blueprintId)}>
              <Icon.Table />
              Open the table
            </a>
            <a className="btn btn--ghost" href={href.recipes(workspaceId, blueprintId)}>
              <Icon.Bolt />
              {recipesOn.length} automations on
            </a>
          </div>
        </header>

        {/* State of the work: real annotated totals. Tiles, then the same
            numbers as one thin segmented bar — identity is carried by the
            state chip AND the label, never colour alone. */}
        <section className="overview__stats" aria-label="State of the work">
          <div className="overview__tiles">
            {(counts ?? spine.workflow.states.map((state) => ({ state, total: null }))).map((c) => (
              <a
                key={c.state.key}
                className="tile"
                href={href.table(workspaceId, blueprintId)}
                aria-label={`${c.state.label} rows`}
              >
                <span className="tile__value">
                  {'total' in c && c.total !== null ? c.total.toLocaleString() : '—'}
                </span>
                <StateChip state={c.state} />
              </a>
            ))}
            <a
              className={`tile${waiting.length > 0 ? ' tile--attention' : ''}`}
              href={href.inbox(workspaceId)}
              aria-label="Tasks waiting on you"
            >
              <span className="tile__value">{waiting.length}</span>
              <span className="tile__label">
                <Icon.Inbox className="tile__glyph" />
                waiting on you
              </span>
            </a>
          </div>

          {counts !== null && distribution !== null && distribution.sum > 0 && (
            <figure className="dist" aria-label="Distribution by state">
              <div className="dist__bar">
                {counts.map(
                  (c) =>
                    c.total > 0 && (
                      <span
                        key={c.state.key}
                        className={`dist__seg dist__seg--${c.state.role}`}
                        style={{ flexGrow: c.total }}
                        title={`${c.state.label}: ${c.total.toLocaleString()}`}
                      />
                    ),
                )}
              </div>
              <figcaption className="dist__legend">
                {counts.map((c) => (
                  <span key={c.state.key} className="dist__key">
                    <span className={`dist__dot dist__seg--${c.state.role}`} aria-hidden="true" />
                    {c.state.label} {c.total.toLocaleString()}
                  </span>
                ))}
                {distribution.withheld > 0 && (
                  <span className="dist__withheld" title="Counted in every total above, not shown to you — the numbers are honest about what they include.">
                    <Icon.Lock className="tile__glyph" />
                    includes {distribution.withheld.toLocaleString()} withheld
                  </span>
                )}
              </figcaption>
            </figure>
          )}
        </section>

        <div className="overview__panels">
          {/* What needs YOU — the reason an app beats a spreadsheet. */}
          <section className="panel" aria-label="Needs attention">
            <h3 className="panel__title">Needs attention</h3>
            <AttentionList
              title="Longest unreviewed"
              rows={stale}
              blueprint={blueprint}
              valueField="reviewed"
              onOpen={() => navigate(href.table(workspaceId, blueprintId))}
            />
            <AttentionList
              title="Largest exposure"
              rows={largest}
              blueprint={blueprint}
              valueField="exposure"
              onOpen={() => navigate(href.table(workspaceId, blueprintId))}
            />
          </section>

          <section className="panel" aria-label="Waiting on you">
            <div className="panel__head">
              <h3 className="panel__title">Waiting on you</h3>
              <a className="panel__more" href={href.inbox(workspaceId)}>
                Inbox
                <Icon.Chevron />
              </a>
            </div>
            {waiting.length === 0 ? (
              <p className="panel__empty">Nothing — the good kind of empty.</p>
            ) : (
              waiting.map((t) => (
                <a key={t.id} className="panel__task" href={href.inbox(workspaceId)}>
                  <span className={`task__kind task__kind--${t.kind}`}>
                    {t.kind === 'approval' ? 'Approval' : 'Update'}
                  </span>
                  <span className="panel__task-title">{t.title}</span>
                  <span className="panel__task-meta">from {t.requestedBy.replace(/@.*/, '')}</span>
                </a>
              ))
            )}
          </section>

          <section className="panel" aria-label="While you were away">
            <div className="panel__head">
              <h3 className="panel__title">While you were away</h3>
              <span className="panel__more panel__more--static">
                {runs30d.toLocaleString()} automation runs · 30d
              </span>
            </div>
            <ActivityFeed entries={pulse} />
          </section>
        </div>
      </div>

      {formOpen && blueprint !== null && spine.forms[0] !== undefined && (
        <GeneratedForm
          workspaceId={workspaceId}
          blueprint={blueprint}
          spine={spine}
          form={spine.forms[0]}
          onCreated={() => navigate(href.table(workspaceId, blueprintId))}
          onClose={() => setFormOpen(false)}
        />
      )}
    </div>
  )
}

function AttentionList({
  title,
  rows,
  blueprint,
  valueField,
  onOpen,
}: {
  title: string
  rows: readonly Row[] | null
  blueprint: Blueprint | null
  valueField: string
  onOpen: () => void
}) {
  if (rows === null || blueprint === null) {
    return <p className="panel__empty">Loading…</p>
  }
  const titleField = blueprint.titleField ?? 'title'
  const field = blueprint.fields.find((f) => f.id === valueField)
  return (
    <div className="panel__group">
      <h4 className="panel__subtitle">{title}</h4>
      {rows.map((row) => (
        <button key={row.id} type="button" className="panel__row" onClick={onOpen}>
          <span className="panel__row-title">
            {formatValue(row.values[titleField], blueprint.fields.find((f) => f.id === titleField) ?? blueprint.fields[0]!) || row.id}
          </span>
          <span className="panel__row-value">
            {field !== undefined ? formatValue(row.values[valueField], field) : ''}
          </span>
        </button>
      ))}
    </div>
  )
}
