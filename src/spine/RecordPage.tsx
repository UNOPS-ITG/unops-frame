/**
 * One row, opened as a PAGE — the master-detail document.
 *
 * This is the vision's headline capability rendered at last (§3, GR-17):
 * a parent shows its header fields as a form, and its child collections as
 * REAL TABLES INLINE — mitigation actions under the risk, the decision log
 * beside it — because a governed record is a document with parts, not a
 * line in a grid. The grid is where you find the record; this is where the
 * record lives. Smartsheet cannot render this page at any price tier.
 *
 * The parent row is real (fetched, trimmed, annotated); the child rows are
 * fixture-derived per parent until BP-5/FM-3 children are served, and the
 * page says so. The workflow rail performs real writes.
 */

import { useEffect, useState } from 'react'
import { getBlueprint, queryRows } from '@/api/client'
import { Icon } from '@/app/icons'
import { href } from '@/app/routes'
import { formatValue, WITHHELD_LABEL } from '@/grid/cells'
import { isCorporateValue, isRestricted, type Blueprint, type Row } from '@/grid/contract'
import type { SpineDef } from '@/fixtures/spine/contracts'
import { mitigationsFor } from '@/fixtures/spine/risk'
import { activityFeed, useSpineStore } from '@/fixtures/spine/store'
import { ActivityFeed } from './ActivityFeed'
import { WorkflowPanel } from './WorkflowPanel'
import { PreviewPill } from './bits'
import './spine.css'

export function RecordPage({
  workspaceId,
  blueprintId,
  rowId,
  spine,
}: {
  workspaceId: string
  blueprintId: string
  rowId: string
  spine: SpineDef
}) {
  const spineGeneration = useSpineStore((s) => s.generation)
  const appended = useSpineStore((s) => s.appended)
  const draftChildren = useSpineStore((s) => s.draftChildren)

  const [blueprint, setBlueprint] = useState<Blueprint | null>(null)
  const [row, setRow] = useState<Row | null>(null)
  const [missing, setMissing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    // No single-row GET exists yet on the client — the page scan is the
    // fixture-stage stand-in and the argument for `GET .../rows/{id}` in
    // the generated API. The trim still happened server-side either way.
    Promise.all([
      getBlueprint(workspaceId, blueprintId),
      queryRows(workspaceId, blueprintId, { limit: 500 }),
    ])
      .then(([bp, page]) => {
        if (cancelled) return
        setBlueprint(bp)
        const found = page.rows.find((r) => r.id === rowId) ?? null
        setRow(found)
        setMissing(found === null)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'The record could not be opened')
      })
    return () => {
      cancelled = true
    }
  }, [workspaceId, blueprintId, rowId, spineGeneration])

  if (error !== null || missing) {
    return (
      <div className="state">
        <h2 className="state__title">This record could not be opened</h2>
        <p className="state__body">
          {error ??
            'Either it does not exist, or it is beyond your access — and the register does not say which, because that difference is itself information.'}
        </p>
        <a className="btn btn--secondary" href={href.table(workspaceId, blueprintId)}>
          Back to {spine.entityLabel}
        </a>
      </div>
    )
  }

  if (blueprint === null || row === null) {
    return (
      <div className="record">
        <div className="skeleton">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="skeleton__row" style={{ opacity: 1 - i * 0.15 }} />
          ))}
        </div>
      </div>
    )
  }

  const titleFieldId = blueprint.titleField ?? blueprint.fields[0]?.id ?? ''
  const titleField = blueprint.fields.find((f) => f.id === titleFieldId)
  const titleValue = row.values[titleFieldId]
  const title =
    titleField !== undefined && !isRestricted(titleValue)
      ? formatValue(titleValue, titleField) || row.id
      : row.id

  // Header fields: everything except the title and the state field — those
  // live in the masthead — laid out as the document's form.
  const headerFields = blueprint.fields.filter(
    (f) => f.id !== titleFieldId && f.id !== spine.workflow.stateField,
  )

  const fixtureChildren = mitigationsFor(row.id, row.values)
  const intakeChildren = draftChildren[row.id] ?? []

  return (
    <div className="record scrollable">
      <nav className="record__crumbs" aria-label="Breadcrumb">
        <a href={href.register(workspaceId, blueprintId)}>{blueprint.name}</a>
        <Icon.Chevron className="record__crumb-sep" />
        <a href={href.table(workspaceId, blueprintId)}>{spine.entityLabel}</a>
        <Icon.Chevron className="record__crumb-sep" />
        <span aria-current="page">{title}</span>
      </nav>

      <header className="record__masthead">
        <h2 className="record__title">{title}</h2>
      </header>

      <div className="record__body">
        <div className="record__main">
          <section className="record__card" aria-label="Fields">
            <div className="record__fields">
              {headerFields.map((field) => {
                const value = row.values[field.id]
                return (
                  <div key={field.id} className="record__field">
                    <span className="record__label">
                      {field.label}
                      {field.restricted && <span className="detail__badge">restricted</span>}
                    </span>
                    <span className="record__value">
                      {isRestricted(value) ? (
                        <span className="detail__value--withheld detail__value">
                          <Icon.Lock className="detail__glyph" />
                          {WITHHELD_LABEL}
                        </span>
                      ) : isCorporateValue(value) ? (
                        (value.label ?? value.key)
                      ) : (
                        formatValue(value, field) || <span className="record__empty">Not recorded</span>
                      )}
                    </span>
                  </div>
                )
              })}
            </div>
          </section>

          {/* The child collections, inline — the page's reason to exist. */}
          {spine.childTables.map((table) => (
            <section key={table.id} className="record__card" aria-label={table.label}>
              <div className="panel__head">
                <h3 className="panel__title">{table.label}</h3>
                <a className="panel__more" href={href.collection(workspaceId, blueprintId, table.id)}>
                  All {table.label.toLowerCase()}
                  <Icon.Chevron />
                </a>
                <PreviewPill what="Child rows" />
              </div>
              <div className="rtable">
                <div className="rtable__head" style={{ gridTemplateColumns: `2.2fr 1fr 1fr 1fr` }}>
                  {table.columns.map((c) => (
                    <span key={c.id}>{c.label}</span>
                  ))}
                </div>
                {intakeChildren.map((d, i) => (
                  <div key={`intake-${i}`} className="rtable__row" style={{ gridTemplateColumns: `2.2fr 1fr 1fr 1fr` }}>
                    <span>{d.values['action'] ?? ''}</span>
                    <span>{d.values['due'] ?? ''}</span>
                    <span>{d.values['assignee'] ?? ''}</span>
                    <span className="slot slot--value">from intake</span>
                  </div>
                ))}
                {fixtureChildren.map((c, i) => (
                  <div key={i} className="rtable__row" style={{ gridTemplateColumns: `2.2fr 1fr 1fr 1fr` }}>
                    <span>{c.action}</span>
                    <span>{c.due}</span>
                    <span>{c.assignee}</span>
                    <span>
                      <span
                        className={`state-chip state-chip--${c.state === 'Done' ? 'closed' : c.state === 'In progress' ? 'progress' : 'draft'}`}
                      >
                        {c.state}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </section>
          ))}

          {spine.extension !== undefined &&
            spine.extension.collections.map((c) => (
              <section key={c.id} className="record__card" aria-label={c.title}>
                <div className="panel__head">
                  <h3 className="panel__title">{c.title}</h3>
                  <span
                    className="detail__ext-note"
                    title={`Added by ${spine.extension?.owner ?? 'this workspace'} as a workspace extension (BP-28); the app's base stays locked.`}
                  >
                    · extension
                  </span>
                </div>
                <div className="rtable">
                  <div className="rtable__head" style={{ gridTemplateColumns: `2fr 1fr 1fr` }}>
                    {c.columns.map((col) => (
                      <span key={col.id}>{col.label}</span>
                    ))}
                  </div>
                  {c.rows.map((r, i) => (
                    <div key={i} className="rtable__row" style={{ gridTemplateColumns: `2fr 1fr 1fr` }}>
                      {c.columns.map((col) => (
                        <span key={col.id}>{r[col.id] ?? ''}</span>
                      ))}
                    </div>
                  ))}
                </div>
              </section>
            ))}
        </div>

        <aside className="record__rail" aria-label="Workflow and history">
          <WorkflowPanel workspaceId={workspaceId} spine={spine} row={row} rowTitle={title} />
          <section className="record__card record__card--flush" aria-label="Activity">
            <div className="panel__head record__rail-head">
              <h3 className="panel__title">
                <Icon.History className="detail__glyph" /> Activity
              </h3>
            </div>
            <ActivityFeed entries={activityFeed(row.id, row.values, appended)} />
          </section>
        </aside>
      </div>
    </div>
  )
}
