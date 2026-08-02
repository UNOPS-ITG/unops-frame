/**
 * One row, opened.
 *
 * The grid shows a hundred rows badly-legibly; this shows one row well. It is
 * also where the governed treatments have room to be explained rather than
 * merely indicated: the grid can only afford an em-dash for a withheld field,
 * and here it can say the word and why.
 *
 * Field VALUES stay read-only, deliberately — an editable detail panel would
 * be a second write surface beside the grid's field-scoped edit model. The
 * row's *state* is different: a transition is an action, not a cell edit
 * (AU-10), so the workflow panel at the top performs and requests
 * transitions without contradicting that rule. Activity sits beside the
 * fields as a tab: what a row is and what happened to it are the two
 * questions people open a row to answer.
 */

import { useState } from 'react'
import { formatValue, WITHHELD_LABEL } from '@/grid/cells'
import { isCorporateValue, isRestricted, type Blueprint, type Row } from '@/grid/contract'
import { Icon } from '@/app/icons'
import { activityFeed, spineFor, useSpineStore } from '@/fixtures/spine/store'
import { ActivityFeed } from '@/spine/ActivityFeed'
import { WorkflowPanel } from '@/spine/WorkflowPanel'

export interface RowDetailProps {
  workspaceId: string
  blueprint: Blueprint
  /** Null when nothing is selected. The panel stays open and says so, rather
   * than closing — a panel that vanishes when the selection clears is a panel
   * the user has to re-open, and they did not ask for it to close. */
  row: Row | null
  onClose: () => void
}

export function RowDetail({ workspaceId, blueprint, row, onClose }: RowDetailProps) {
  const [tab, setTab] = useState<'fields' | 'activity'>('fields')
  const appended = useSpineStore((s) => s.appended)
  const draftChildren = useSpineStore((s) => s.draftChildren)

  if (row === null) {
    return (
      <aside className="detail" aria-label="Row detail">
        <div className="detail__header">
          <h2 className="detail__title">Details</h2>
          <button
            type="button"
            className="btn btn--ghost btn--icon btn--sm detail__close"
            onClick={onClose}
            aria-label="Close row detail"
          >
            <Icon.Close />
          </button>
        </div>
        <p className="detail__hint">Select a row to see it in full.</p>
      </aside>
    )
  }

  const spine = spineFor(blueprint.id)

  const title = blueprint.titleField
    ? formatValue(row.values[blueprint.titleField], fieldOf(blueprint, blueprint.titleField))
    : row.id

  const drafts = draftChildren[row.id] ?? []

  return (
    <aside className="detail" aria-label="Row detail">
      <div className="detail__header">
        <h2 className="detail__title">{title || row.id}</h2>
        <button
          type="button"
          className="btn btn--ghost btn--icon btn--sm detail__close"
          onClick={onClose}
          aria-label="Close row detail"
        >
          <Icon.Close />
        </button>
      </div>

      {spine !== null && (
        <WorkflowPanel workspaceId={workspaceId} spine={spine} row={row} rowTitle={title || row.id} />
      )}

      {spine !== null && (
        <div className="detail-tabs" role="tablist" aria-label="Row detail sections">
          <button
            type="button"
            role="tab"
            className="detail-tabs__tab"
            aria-selected={tab === 'fields'}
            onClick={() => setTab('fields')}
          >
            <Icon.Fields />
            Fields
          </button>
          <button
            type="button"
            role="tab"
            className="detail-tabs__tab"
            aria-selected={tab === 'activity'}
            onClick={() => setTab('activity')}
          >
            <Icon.History />
            Activity
          </button>
        </div>
      )}

      {tab === 'activity' && spine !== null ? (
        <ActivityFeed entries={activityFeed(row.id, row.values, appended)} />
      ) : (
        <div className="detail__fields scrollable">
          {blueprint.fields.map((field) => {
            const value = row.values[field.id]
            return (
              <div key={field.id} className="detail__field">
                <div className="detail__label">
                  <span>{field.label}</span>
                  {field.restricted && (
                    <span className="detail__badge" title="Sensitive field">
                      restricted
                    </span>
                  )}
                </div>
                <DetailValue value={value} field={field} />
              </div>
            )
          })}

          {/* FM-3's line items, captured at intake. Held by the spine store
              until child collections are served; labelled with their origin
              so nobody mistakes a draft for a persisted child row. */}
          {drafts.length > 0 && (
            <div className="detail__field">
              <div className="detail__label">
                <span>Mitigation actions</span>
                <span className="detail__badge">from intake · engine preview</span>
              </div>
              <div className="ext-table">
                <div className="ext-table__head" aria-hidden="true">
                  <span>Action</span>
                  <span>Due</span>
                  <span>Assignee</span>
                </div>
                {drafts.map((d, i) => (
                  <div key={i} className="ext-table__row">
                    <span>{d.values['action'] ?? ''}</span>
                    <span>{d.values['due'] ?? ''}</span>
                    <span>{d.values['assignee'] ?? ''}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* BP-28: the workspace's additions to a locked base, rendered as
              if native and disclosing their home on the label — "feels like
              added columns" with the provenance one glance away. */}
          {spine?.extension !== undefined && (
            <>
              {spine.extension.fields.map((f) => (
                <div key={f.id} className="detail__field">
                  <div className="detail__label">
                    <span>{f.label}</span>
                    <span
                      className="detail__ext-note"
                      title={`Added by ${spine.extension?.owner ?? 'this workspace'} as a workspace extension (BP-28). The organizational Blueprint underneath is locked; extensions live beside it and can never widen access to it.`}
                    >
                      · extension
                    </span>
                  </div>
                  <span className="detail__value detail__value--empty">Not recorded</span>
                </div>
              ))}
              {spine.extension.collections.map((c) => (
                <div key={c.id} className="detail__field">
                  <div className="detail__label">
                    <span>{c.title}</span>
                    <span className="detail__ext-note">· extension collection</span>
                  </div>
                  <div className="ext-table">
                    <div className="ext-table__head" aria-hidden="true">
                      {c.columns.map((col) => (
                        <span key={col.id}>{col.label}</span>
                      ))}
                    </div>
                    {c.rows.map((r, i) => (
                      <div key={i} className="ext-table__row">
                        {c.columns.map((col) => (
                          <span key={col.id}>{r[col.id] ?? ''}</span>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </aside>
  )
}

function DetailValue({
  value,
  field,
}: {
  value: Row['values'][string]
  field: Blueprint['fields'][number]
}) {
  if (isRestricted(value)) {
    // Says the word. The grid has room only for an em-dash; here there is space
    // to make "withheld" unmistakable, which is the difference between a reader
    // knowing a value exists and assuming none was recorded.
    return (
      <span className="detail__value detail__value--withheld">
        <Icon.Lock className="detail__glyph" />
        {WITHHELD_LABEL}
      </span>
    )
  }

  if (isCorporateValue(value)) {
    const orphaned = value.state === 'orphaned' || value.state === 'quarantined'
    return (
      <div className="detail__value">
        {value.label ?? value.key}
        {orphaned && (
          <div className="detail__badge" style={{ marginBlockStart: 'var(--spacing-1)' }}>
            This reference no longer resolves — the source was withdrawn upstream.
            The stored value is kept.
          </div>
        )}
        {!orphaned && value.stale && (
          <div className="detail__badge" style={{ marginBlockStart: 'var(--spacing-1)' }}>
            Label taken more than 90 days ago.
          </div>
        )}
      </div>
    )
  }

  const formatted = formatValue(value, field)
  if (formatted === '') {
    // "Not recorded", not blank. A blank cell and an unrecorded value look the
    // same and mean different things.
    return <span className="detail__value detail__value--empty">Not recorded</span>
  }

  return <div className="detail__value">{formatted}</div>
}

function fieldOf(blueprint: Blueprint, fieldId: string): Blueprint['fields'][number] {
  const found = blueprint.fields.find((f) => f.id === fieldId)
  if (found) return found
  // A title field that no longer exists. Returning a shape rather than throwing
  // keeps a Blueprint mid-edit renderable; the value simply comes back blank.
  return {
    id: fieldId,
    label: fieldId,
    type: 'text',
    variant: null,
    storage: 'string',
    required: false,
    readOnly: true,
    setOnce: false,
    sensitivity: 0,
    restricted: false,
    indexed: false,
    sortable: false,
    filterable: false,
    options: null,
    default: null,
    helpText: null,
    dimension: null,
    writable: true,
  }
}
