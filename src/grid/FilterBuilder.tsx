/**
 * Building a filter, as an AST.
 *
 * The output is a shared-grammar expression, not a string — the same shape a
 * permission rule is written in. A string filter would need a parser wherever it
 * is read, and a second parser is a second grammar: at that point a saved view
 * and a permission rule can disagree about what `status = 'open'` means, on the
 * same register, with no error anywhere.
 *
 * Two things this refuses to do, and both are the point:
 *
 * **It offers no operator the store cannot serve on that field.** A control that
 * lets a user build a filter the index cannot answer produces a view that is
 * either slow forever or silently post-filtered. The Blueprint says which fields
 * are filterable and sortable; this reads that rather than guessing from type.
 *
 * **It offers no subject reference.** "Where owner is me" is a permission rule,
 * not a view: a view is opened by whoever holds the link, so a filter reading the
 * signed-in user makes one saved view a different query per viewer. The server
 * refuses it too; not offering it is how the user finds out before they try.
 */

import { useCallback, useMemo, useState } from 'react'
import type { Blueprint, BlueprintField } from './contract'

type Operator = 'eq' | 'neq' | 'lt' | 'lte' | 'gt' | 'gte' | 'contains'

interface Clause {
  fieldId: string
  op: Operator
  value: string
}

const LABELS: Record<Operator, string> = {
  eq: 'is',
  neq: 'is not',
  lt: 'is less than',
  lte: 'is at most',
  gt: 'is more than',
  gte: 'is at least',
  contains: 'contains',
}

/**
 * Which operators a field can actually be filtered by.
 *
 * Driven by the compiled Blueprint, not by the field's type. A number field with
 * no typed sort slot cannot be range-filtered by the store however numeric it
 * is, and offering the control anyway is how a user builds a view that quietly
 * scans.
 */
function operatorsFor(field: BlueprintField): Operator[] {
  const equality: Operator[] = field.filterable ? ['eq', 'neq'] : []
  const ranges: Operator[] =
    field.sortable && (field.storage === 'number' || field.storage === 'timestamp')
      ? ['gte', 'lte', 'gt', 'lt']
      : []
  // `contains` is honest about being a post-filter: it is offered only where
  // something else already narrows the scan, i.e. never as the only clause.
  return [...equality, ...ranges]
}

function coerce(raw: string, field: BlueprintField): unknown {
  if (field.storage === 'number') {
    const parsed = Number(raw.replace(/,/g, ''))
    return Number.isFinite(parsed) ? parsed : raw
  }
  if (field.storage === 'boolean') return raw === 'true'
  return raw
}

function toAst(clauses: Clause[], blueprint: Blueprint): Record<string, unknown> | null {
  const usable = clauses.filter((c) => c.fieldId !== '' && c.value !== '')
  if (usable.length === 0) return null

  const terms = usable.map((clause) => {
    const field = blueprint.fields.find((f) => f.id === clause.fieldId)
    return {
      type: 'binary',
      op: clause.op,
      left: { type: 'field', id: clause.fieldId },
      right: { type: 'literal', value: field ? coerce(clause.value, field) : clause.value },
    }
  })

  if (terms.length === 1) return terms[0] as Record<string, unknown>
  // AND only. An OR across different fields cannot be pushed down — Firestore
  // has no disjunction over the tokens Frame indexes — so the query compiler
  // sends the whole thing to the in-memory residual. Offering it here would let
  // a user build a view that scans, with no indication that it does.
  return { type: 'logical', op: 'and', operands: terms }
}

export interface FilterBuilderProps {
  blueprint: Blueprint
  onApply: (filter: Record<string, unknown> | null) => void
  onSaveView?: (name: string, filter: Record<string, unknown> | null) => void
  busy?: boolean
}

export function FilterBuilder({ blueprint, onApply, onSaveView, busy = false }: FilterBuilderProps) {
  const filterable = useMemo(
    () => blueprint.fields.filter((f) => operatorsFor(f).length > 0),
    [blueprint.fields],
  )
  const [clauses, setClauses] = useState<Clause[]>([])
  const [viewName, setViewName] = useState('')

  const update = useCallback((index: number, patch: Partial<Clause>) => {
    setClauses((prev) => prev.map((c, i) => (i === index ? { ...c, ...patch } : c)))
  }, [])

  const add = useCallback(() => {
    const first = filterable[0]
    if (first === undefined) return
    setClauses((prev) => [
      ...prev,
      { fieldId: first.id, op: operatorsFor(first)[0] ?? 'eq', value: '' },
    ])
  }, [filterable])

  const ast = useMemo(() => toAst(clauses, blueprint), [clauses, blueprint])

  if (filterable.length === 0) {
    // Stated rather than shown as an empty builder: "no field on this Blueprint
    // is declared filterable" is actionable by the steward; a control that
    // produces nothing is not.
    return (
      <p style={{ font: 'var(--text-body-small)', color: 'var(--color-text-secondary)' }}>
        No field on {blueprint.name} is declared filterable, so there is nothing the index can
        answer. A steward can mark fields as filterable on the Blueprint.
      </p>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      {clauses.map((clause, index) => {
        const field = blueprint.fields.find((f) => f.id === clause.fieldId)
        const operators = field ? operatorsFor(field) : []
        return (
          <div key={index} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <select
              className="ops-select"
              aria-label="Field"
              value={clause.fieldId}
              onChange={(e) => {
                const next = blueprint.fields.find((f) => f.id === e.target.value)
                update(index, {
                  fieldId: e.target.value,
                  // Reset the operator: the previous one may not be offered for
                  // the new field, and a stale value would build a filter the
                  // store cannot serve.
                  op: next ? (operatorsFor(next)[0] ?? 'eq') : 'eq',
                  value: '',
                })
              }}
            >
              {filterable.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label}
                </option>
              ))}
            </select>

            <select
              className="ops-select"
              aria-label="Condition"
              value={clause.op}
              onChange={(e) => update(index, { op: e.target.value as Operator })}
            >
              {operators.map((op) => (
                <option key={op} value={op}>
                  {LABELS[op]}
                </option>
              ))}
            </select>

            {field?.options ? (
              <select
                className="ops-select"
                aria-label="Value"
                value={clause.value}
                onChange={(e) => update(index, { value: e.target.value })}
              >
                <option value="">Choose…</option>
                {field.options.map((o) => (
                  // The label is shown, the key is stored — the key is an
                  // internal identifier the user never chose.
                  <option key={o.key} value={o.key}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className="ops-input"
                aria-label="Value"
                type={field?.storage === 'number' ? 'number' : 'text'}
                value={clause.value}
                onChange={(e) => update(index, { value: e.target.value })}
              />
            )}

            <button
              type="button"
              className="btn btn--ghost btn--sm"
              aria-label="Remove condition"
              onClick={() => setClauses((prev) => prev.filter((_, i) => i !== index))}
            >
              Remove
            </button>
          </div>
        )
      })}

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <button type="button" className="btn btn--ghost btn--sm" onClick={add} disabled={busy}>
          Add condition
        </button>
        <button
          type="button"
          className="btn btn--primary btn--sm"
          onClick={() => onApply(ast)}
          disabled={busy}
        >
          Apply
        </button>
        {clauses.length > 0 && (
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => {
              setClauses([])
              onApply(null)
            }}
            disabled={busy}
          >
            Clear
          </button>
        )}

        {onSaveView !== undefined && (
          <>
            <input
              className="ops-input"
              aria-label="View name"
              placeholder="Save as a view…"
              value={viewName}
              onChange={(e) => setViewName(e.target.value)}
              style={{ maxWidth: '14rem' }}
            />
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              disabled={busy || viewName.trim() === ''}
              onClick={() => {
                onSaveView(viewName.trim(), ast)
                setViewName('')
              }}
            >
              Save view
            </button>
          </>
        )}
      </div>

      {clauses.length > 1 && (
        // Said plainly, because a builder that silently ANDs is one where a user
        // eventually assumes it ORs and reports the register as wrong.
        <p style={{ font: 'var(--text-body-small)', color: 'var(--color-text-secondary)', margin: 0 }}>
          All conditions must match.
        </p>
      )}
    </div>
  )
}
