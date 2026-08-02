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
import { ApiError, getBlueprint, queryRows, updateRow, type LookupRow } from '@/api/client'
import { Icon } from '@/app/icons'
import { href } from '@/app/routes'
import { CorporatePicker } from '@/corporate/CorporatePicker'
import { formatValue, WITHHELD_LABEL } from '@/grid/cells'
import {
  isCorporateValue,
  isRestricted,
  type Blueprint,
  type BlueprintField,
  type Row,
} from '@/grid/contract'
import type { SpineDef } from '@/fixtures/spine/contracts'
import { activityFeed, childRowsFor, useSpineStore } from '@/fixtures/spine/store'
import { FieldInput } from '@/registers/NewRow'
import { ActivityFeed } from './ActivityFeed'
import { WorkflowPanel } from './WorkflowPanel'
import { PreviewPill } from './bits'
import './spine.css'

type DraftValue = string | number | { key: string; label: string }

/** What Edit starts from: the row's current values coerced to what inputs
 * hold. Restricted stubs are EXCLUDED — they are not values, and BP-4
 * refuses them on the wire; a field the viewer cannot read simply is not
 * offered for edit. */
function draftFrom(row: Row, fields: readonly BlueprintField[]): Record<string, DraftValue> {
  const out: Record<string, DraftValue> = {}
  for (const field of fields) {
    const value = row.values[field.id]
    if (isRestricted(value)) continue
    if (isCorporateValue(value)) {
      out[field.id] = { key: value.key, label: value.label ?? value.key }
    } else if (typeof value === 'string' || typeof value === 'number') {
      // Dates arrive as ISO strings; date inputs want YYYY-MM-DD.
      out[field.id] =
        field.storage === 'timestamp' && typeof value === 'string'
          ? value.slice(0, 10)
          : value
    } else {
      out[field.id] = ''
    }
  }
  return out
}

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

  // GR-23's contract: the form view is read-only until Edit is an explicit
  // act. Saving goes through the SAME field-scoped write path as the grid —
  // the form view is a caller of BP-4's one writer, never a peer.
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Record<string, DraftValue>>({})
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [picking, setPicking] = useState<BlueprintField | null>(null)
  const [localGeneration, setLocalGeneration] = useState(0)

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
  }, [workspaceId, blueprintId, rowId, spineGeneration, localGeneration])

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

  const intakeChildren = draftChildren[row.id] ?? []

  const editableFields = headerFields.filter(
    (f) => f.writable && !f.readOnly && !isRestricted(row.values[f.id]),
  )

  const startEditing = () => {
    setDraft(draftFrom(row, editableFields))
    setFieldErrors({})
    setSaveError(null)
    setEditing(true)
  }

  const save = async () => {
    setSaving(true)
    setFieldErrors({})
    setSaveError(null)
    try {
      // Only what CHANGED goes on the wire, with the versions the client
      // read — that is what lets the server report a per-cell conflict
      // instead of silently last-writing.
      const changed: Record<string, unknown> = {}
      const versions: Record<string, number> = {}
      for (const field of editableFields) {
        const next = draft[field.id]
        const current = row.values[field.id]
        const currentComparable = isCorporateValue(current)
          ? current.key
          : field.storage === 'timestamp' && typeof current === 'string'
            ? current.slice(0, 10)
            : typeof current === 'string' || typeof current === 'number'
              ? String(current)
              : ''
        const nextComparable =
          typeof next === 'object' && next !== null ? next.key : String(next ?? '')
        if (nextComparable === currentComparable) continue
        changed[field.id] =
          typeof next === 'object' && next !== null
            ? { key: next.key, label: next.label }
            : next === ''
              ? null
              : next
        const version = row.fieldVersions[field.id]
        if (version !== undefined) versions[field.id] = version
      }
      if (Object.keys(changed).length === 0) {
        setEditing(false)
        return
      }
      await updateRow(workspaceId, blueprintId, row.id, changed, versions, 'form')
      setEditing(false)
      setLocalGeneration((g) => g + 1)
    } catch (e) {
      if (e instanceof ApiError && e.fieldErrors.length > 0) {
        setFieldErrors(Object.fromEntries(e.fieldErrors.map((f) => [f.fieldId, f.message])))
        setSaveError('Nothing was saved — the fields marked below need attention.')
      } else {
        setSaveError(e instanceof ApiError ? e.message : 'The record could not be saved')
      }
    } finally {
      setSaving(false)
    }
  }

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
        <div className="record__acts">
          {editing ? (
            <>
              <button type="button" className="btn btn--primary btn--sm" disabled={saving} onClick={() => void save()}>
                <Icon.Check />
                {saving ? 'Saving…' : 'Save changes'}
              </button>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                disabled={saving}
                onClick={() => setEditing(false)}
              >
                Cancel
              </button>
            </>
          ) : (
            editableFields.length > 0 && (
              <button type="button" className="btn btn--secondary btn--sm" onClick={startEditing}>
                <Icon.Fields />
                Edit
              </button>
            )
          )}
        </div>
      </header>

      {saveError !== null && (
        <div className="notice notice--error" role="alert">
          <div className="notice__body">{saveError}</div>
        </div>
      )}

      <div className="record__body">
        <div className="record__main">
          <section className="record__card" aria-label="Fields">
            <div className="record__fields">
              {headerFields.map((field) => {
                const value = row.values[field.id]
                const editable = editing && editableFields.some((f) => f.id === field.id)
                return (
                  <div key={field.id} className="record__field">
                    <span className="record__label">
                      {field.label}
                      {field.restricted && <span className="detail__badge">restricted</span>}
                    </span>
                    {editable ? (
                      <>
                        <FieldInput
                          field={field}
                          value={draft[field.id]}
                          onChange={(v) => setDraft((d) => ({ ...d, [field.id]: v }))}
                          onPick={() => setPicking(field)}
                        />
                        {fieldErrors[field.id] !== undefined && (
                          <span className="gform__error" role="alert">
                            {fieldErrors[field.id]}
                          </span>
                        )}
                      </>
                    ) : (
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
                    )}
                  </div>
                )
              })}
            </div>
          </section>

          {/* BP-28's one-to-one additions: fields in a section of their own,
              reading as native with their provenance one glance away. */}
          {spine.extension !== undefined && spine.extension.fields.length > 0 && (
            <section className="record__card" aria-label="Workspace additions">
              <div className="panel__head">
                <h3 className="panel__title">Workspace additions</h3>
                <span
                  className="detail__ext-note"
                  title={`Added by ${spine.extension.owner} as a workspace extension (BP-28); the app's base stays locked and extensions can never widen access to it.`}
                >
                  · extension
                </span>
              </div>
              <div className="record__fields">
                {spine.extension.fields.map((f) => (
                  <div key={f.id} className="record__field">
                    <span className="record__label">{f.label}</span>
                    <span className="record__value record__empty">Not recorded</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* The child collections, inline — the page's reason to exist. */}
          {spine.childTables.map((table) => {
            const template = `2.2fr ${table.columns
              .slice(1)
              .map(() => '1fr')
              .join(' ')}`
            const children = childRowsFor(spine.blueprintId, table.id, row.id, row.values)
            const intake = intakeChildren.filter((d) => d.collectionId === table.id)
            return (
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
                  <div className="rtable__head" style={{ gridTemplateColumns: template }}>
                    {table.columns.map((c) => (
                      <span key={c.id}>{c.label}</span>
                    ))}
                  </div>
                  {intake.map((d, i) => (
                    <div key={`intake-${i}`} className="rtable__row" style={{ gridTemplateColumns: template }}>
                      {table.columns.map((c, x) =>
                        c.id === 'state' ? (
                          <span key={c.id} className="slot slot--value">
                            from intake
                          </span>
                        ) : (
                          <span key={c.id}>{d.values[c.id] ?? (x === 0 ? '' : '')}</span>
                        ),
                      )}
                    </div>
                  ))}
                  {children.map((c, i) => (
                    <div key={i} className="rtable__row" style={{ gridTemplateColumns: template }}>
                      {table.columns.map((col) =>
                        col.id === 'state' ? (
                          <span key={col.id}>
                            {c.stateLabel !== undefined && (
                              <span className={`state-chip state-chip--${c.stateRole ?? 'draft'}`}>
                                {c.stateLabel}
                              </span>
                            )}
                          </span>
                        ) : (
                          <span key={col.id}>{c.values[col.id] ?? ''}</span>
                        ),
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )
          })}

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
            <ActivityFeed entries={activityFeed(row.id, row.values, appended, spine)} />
          </section>
        </aside>
      </div>

      {picking !== null && picking.dimension !== null && (
        <CorporatePicker
          workspaceId={workspaceId}
          dimensionId={picking.dimension}
          dimensionLabel={picking.label}
          onPick={(picked: LookupRow) => {
            setPicking((p) => {
              if (p !== null) setDraft((d) => ({ ...d, [p.id]: { key: picked.key, label: picked.label } }))
              return null
            })
          }}
          onClose={() => setPicking(null)}
        />
      )}
    </div>
  )
}
