/**
 * A Blueprint's fields, as published.
 *
 * Read-only, and that is the current honest state rather than a design choice
 * to defend: Blueprint authoring is a governed publish with coherence
 * validation and a version bump, and a fields page that let someone edit a
 * field inline would be a second authoring path around all of it.
 *
 * What it is *for* is the questions a person asks while using a register and
 * cannot answer from the grid: why can I not sort by this column, why is this
 * one always empty for me, what is this field actually storing. Each of those
 * is a property of the compiled Blueprint, and each is shown.
 */

import { useEffect, useState } from 'react'
import { ApiError, getBlueprint } from '@/api/client'
import type { Blueprint, BlueprintField } from '@/grid/contract'
import { Failed, Loading } from '@/registers/states'
import { Icon } from './icons'
import './FieldsPage.css'

export interface FieldsPageProps {
  workspaceId: string
  blueprintId: string
}

export function FieldsPage({ workspaceId, blueprintId }: FieldsPageProps) {
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    getBlueprint(workspaceId, blueprintId)
      .then((b) => {
        if (cancelled) return
        setBlueprint(b)
        // Cleared on success rather than at the start of the effect: clearing
        // up front repaints the failure state away and leaves a blank screen
        // for the length of the request, so a retry looks like it did nothing.
        setError(null)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : 'The Blueprint could not be read')
      })
    return () => {
      cancelled = true
    }
  }, [workspaceId, blueprintId, attempt])

  if (error !== null) {
    return (
      <Failed
        title="This Blueprint could not be read"
        detail={error}
        onRetry={() => setAttempt((a) => a + 1)}
      />
    )
  }
  if (blueprint === null) return <Loading label="Reading the Blueprint" />

  const unsortable = new Set(blueprint.unassignableSorts)

  return (
    <div className="fields">
      <div className="fields__inner">
        <p className="fields__lead">
          Everything below is compiled metadata. The grid, the REST surface, the
          CSV import and the permission rules are all generated from it — there
          is no Python and no React written for this register anywhere.
        </p>

        {unsortable.size > 0 && (
          // Answered here rather than at the moment a sort silently does
          // nothing. Sort slots are a fixed, declared resource: a register can
          // out-declare them, and when it does, the honest place to say so is
          // where someone is looking at the fields.
          <div className="notice notice--warning">
            <div className="notice__body">
              <span className="notice__title">
                {unsortable.size} field{unsortable.size === 1 ? '' : 's'} cannot be sorted by the
                store.
              </span>{' '}
              Sort slots are a declared, finite resource, and this Blueprint asks
              for more than it has. Sorting by these columns is refused rather
              than silently ignored.
            </div>
          </div>
        )}

        <table className="fields__table">
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">Type</th>
              <th scope="col">Rules</th>
              <th scope="col">Index</th>
            </tr>
          </thead>
          <tbody>
            {blueprint.fields.map((field) => (
              <tr key={field.id}>
                <th scope="row" className="fields__name">
                  <span className="fields__label">
                    {field.label}
                    {blueprint.titleField === field.id && (
                      <span className="fields__badge" title="Shown as the row's title">
                        title
                      </span>
                    )}
                  </span>
                  <code className="fields__id">{field.id}</code>
                  {field.helpText && <span className="fields__help">{field.helpText}</span>}
                </th>
                <td>
                  <span className="fields__type">{field.type}</span>
                  {field.variant && <span className="fields__variant">{field.variant}</span>}
                  {/* The storage type, because it is what determines how the
                      value sorts, filters and exports — and it is not always
                      what the type name suggests. */}
                  <span className="fields__storage">stored as {field.storage}</span>
                </td>
                <td>
                  <Rules field={field} />
                </td>
                <td>
                  {unsortable.has(field.id) ? (
                    <span className="fields__flag fields__flag--warn">no sort slot</span>
                  ) : field.sortable ? (
                    <span className="fields__flag">sortable</span>
                  ) : null}
                  {field.filterable && <span className="fields__flag">filterable</span>}
                  {field.indexed && <span className="fields__flag">indexed</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Rules({ field }: { field: BlueprintField }) {
  const rules: string[] = []
  if (field.required) rules.push('required')
  if (field.readOnly) rules.push('read only')
  // Distinct from read-only, and the distinction matters: set-once accepts a
  // value on create and refuses every later change, which is what a reference
  // number needs and what "read only" cannot express.
  if (field.setOnce) rules.push('set once')

  return (
    <>
      {rules.map((rule) => (
        <span key={rule} className="fields__flag">
          {rule}
        </span>
      ))}
      {field.restricted && (
        <span className="fields__flag fields__flag--restricted">
          <Icon.Lock className="fields__glyph" />
          sensitivity {field.sensitivity}
        </span>
      )}
      {rules.length === 0 && !field.restricted && <span className="fields__none">—</span>}
    </>
  )
}
