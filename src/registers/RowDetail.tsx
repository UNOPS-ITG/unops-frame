/**
 * One row, opened.
 *
 * The grid shows a hundred rows badly-legibly; this shows one row well. It is
 * also where the governed treatments have room to be explained rather than
 * merely indicated: the grid can only afford an em-dash for a withheld field,
 * and here it can say the word and why.
 *
 * Read-only for now, deliberately. An editable detail panel is a second write
 * surface, and the field-scoped write path with per-cell conflict detection is
 * built for the grid's edit model. Adding a form that PUTs a whole row would
 * reintroduce exactly the whole-row save GR-8 forbids.
 */

import { formatValue, WITHHELD_LABEL } from '@/grid/cells'
import { isCorporateValue, isRestricted, type Blueprint, type Row } from '@/grid/contract'
import { Icon } from '@/app/icons'

export interface RowDetailProps {
  blueprint: Blueprint
  /** Null when nothing is selected. The panel stays open and says so, rather
   * than closing — a panel that vanishes when the selection clears is a panel
   * the user has to re-open, and they did not ask for it to close. */
  row: Row | null
  onClose: () => void
}

export function RowDetail({ blueprint, row, onClose }: RowDetailProps) {
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

  const title = blueprint.titleField
    ? formatValue(row.values[blueprint.titleField], fieldOf(blueprint, blueprint.titleField))
    : row.id

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
      </div>
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
