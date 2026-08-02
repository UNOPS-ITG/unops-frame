/**
 * Adding a row.
 *
 * A small dialog rather than an empty row appended to the grid, and that is a
 * consequence of the write path rather than a visual preference. A blank row
 * committed on click would be refused by the server the moment a field is
 * required — leaving either a row that exists and is invalid, or an error with
 * nothing on screen to attach it to. Asking for the required fields first means
 * the create either succeeds or never happens.
 *
 * It is still not a form engine — no conditional visibility, no sections, no
 * validation of its own. It renders the writable fields and hands the values to
 * the one write path. Everything the server refuses comes back as a per-field
 * message rather than being pre-empted here, because a client that decided what
 * was allowed would be a second permission evaluator.
 *
 * Read-only fields are absent, not disabled. A disabled input for a field
 * nobody will ever be allowed to fill is a permanent, unexplained dead end.
 */

import { useEffect, useRef, useState } from 'react'
import { ApiError, createRow, type LookupRow } from '@/api/client'
import { Icon } from '@/app/icons'
import { CorporatePicker } from '@/corporate/CorporatePicker'
import type { Blueprint, BlueprintField } from '@/grid/contract'
import './NewRow.css'

/** What a corporate cell holds before it is written. The server decides whether
 * the label may be stored at all; the dialog just carries what was picked. */
interface PickedRef {
  key: string
  label: string
}

export interface NewRowProps {
  workspaceId: string
  blueprintId: string
  blueprint: Blueprint
  /** Carries the created row's id so the register can land on it — scroll,
   * flash, done. A create whose result never appears on screen reads as a
   * create that may not have happened. */
  onCreated: (rowId: string) => void
  onClose: () => void
}

/**
 * What the dialog asks for: every writable field, required ones first.
 *
 * It offered only the required fields at first, and that was wrong in a way
 * worth recording, because it looks like restraint. **A permission grant may be
 * conditioned on any field.** The demo register's create grant is conditioned
 * on `exposure`; a dialog that omitted it produced a row with no exposure, the
 * condition evaluated false, and the server refused the create — correctly, and
 * for a reason the user could not see or act on. Offering a field the row does
 * not strictly need is a small cost. Making creation impossible is not.
 *
 * Read-only fields are still excluded: `created_at` on a create form is a
 * question with one possible answer.
 */
function fieldsToAsk(blueprint: Blueprint): BlueprintField[] {
  // `writable` is the SERVER's answer to "could this person ever write this",
  // carried on the field. Filtering on it is rendering a decision, not making
  // one — and a field the caller will never be allowed to fill is a permanent,
  // unexplained dead end if it is offered.
  const writable = blueprint.fields.filter((f) => !f.readOnly && f.writable)
  // Required first, then declaration order. Someone filling this in top to
  // bottom should hit everything mandatory before anything optional.
  return [
    ...writable.filter((f) => f.required || f.id === blueprint.titleField),
    ...writable.filter((f) => !f.required && f.id !== blueprint.titleField),
  ]
}

export function NewRow({
  workspaceId,
  blueprintId,
  blueprint,
  onCreated,
  onClose,
}: NewRowProps) {
  const fields = fieldsToAsk(blueprint)
  // Strings and numbers only. A create dialog holds what a person typed, and
  // typing it as `unknown` means every read of it needs a cast that eventually
  // stringifies an object into the row.
  const [values, setValues] = useState<Record<string, string | number | PickedRef>>(() =>
    Object.fromEntries(fields.map((f) => [f.id, defaultFor(f)])),
  )
  const [picking, setPicking] = useState<BlueprintField | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const first = useRef<HTMLInputElement | HTMLSelectElement>(null)

  useEffect(() => {
    first.current?.focus()
  }, [])

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setErrors({})
    setMessage(null)

    try {
      // Empty strings are dropped rather than sent. An empty string is a value
      // — it means "explicitly blank" — and sending it for an untouched
      // optional field fails a validation the user never triggered.
      const payload = Object.fromEntries(
        Object.entries(values).filter(([, v]) => v !== '' && v !== undefined),
      )
      const created = await createRow(workspaceId, blueprintId, payload)
      onCreated(created.id)
      onClose()
    } catch (e) {
      if (e instanceof ApiError && e.fieldErrors.length > 0) {
        // Every offending field at once. Reporting one at a time makes a wide
        // form a guessing game.
        setErrors(Object.fromEntries(e.fieldErrors.map((f) => [f.fieldId, f.message])))
        setMessage('This row was not created.')
      } else {
        setMessage(e instanceof ApiError ? e.message : 'The row could not be created')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="picker__backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <form
        className="new-row"
        onSubmit={(e) => void submit(e)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose()
        }}
        aria-label={`Add a row to ${blueprint.name}`}
      >
        <div className="new-row__header">
          <h2 className="new-row__title">New row</h2>
          <button
            type="button"
            className="btn btn--ghost btn--icon btn--sm new-row__close"
            onClick={onClose}
            aria-label="Close"
          >
            <Icon.Close />
          </button>
        </div>

        <div className="new-row__fields scrollable">
          {fields.length === 0 && (
            <p className="new-row__hint">
              This register requires nothing up front. The row will be created
              empty and you can fill it in the grid.
            </p>
          )}

          {fields.map((field, index) => (
            <label key={field.id} className="new-row__field">
              <span className="new-row__label">
                {field.label}
                {field.required && (
                  <span className="new-row__required" aria-hidden="true">
                    required
                  </span>
                )}
              </span>

              <Input
                field={field}
                value={values[field.id]}
                onChange={(v) => setValues((prev) => ({ ...prev, [field.id]: v }))}
                inputRef={index === 0 ? first : undefined}
                onPick={() => setPicking(field)}
              />

              {field.helpText && <span className="new-row__help">{field.helpText}</span>}
              {errors[field.id] && (
                <span className="new-row__error" role="alert">
                  {errors[field.id]}
                </span>
              )}
            </label>
          ))}
        </div>

        {message !== null && (
          <p className="new-row__message" role="alert">
            {message}
          </p>
        )}

        <div className="new-row__actions">
          <button type="submit" className="btn btn--primary btn--sm" disabled={busy}>
            {busy ? 'Adding…' : 'Add row'}
          </button>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
        </div>
      </form>

      {picking !== null && picking.dimension !== null && (
        <CorporatePicker
          workspaceId={workspaceId}
          dimensionId={picking.dimension}
          dimensionLabel={picking.label}
          onPick={(row: LookupRow) => {
            setValues((prev) => ({ ...prev, [picking.id]: { key: row.key, label: row.label } }))
            setPicking(null)
          }}
          onClose={() => setPicking(null)}
        />
      )}
    </div>
  )
}

function Input({
  field,
  value,
  onChange,
  inputRef,
  onPick,
}: {
  field: BlueprintField
  value: string | number | PickedRef | undefined
  onChange: (value: string | number | PickedRef) => void
  inputRef?: React.Ref<HTMLInputElement | HTMLSelectElement> | undefined
  onPick?: () => void
}) {
  if (field.storage === 'corporate_ref') {
    // A button, never a text box. The value comes from a warehouse dimension of
    // hundreds of thousands of rows in this reader's own entitlements, and a
    // typed key is one nobody validated against it.
    const picked = typeof value === 'object' ? value : undefined
    return (
      <button
        type="button"
        className="btn btn--secondary btn--sm new-row__pick"
        aria-label={field.label}
        onClick={onPick}
      >
        <Icon.Search />
        {picked ? picked.label : `Choose from ${field.label}`}
      </button>
    )
  }

  // Narrowed once. A picked reference only reaches the corporate branch above,
  // and the remaining inputs hold text — but the union does not narrow on
  // `field.storage`, and `String()` over the object would put "[object Object]"
  // into the field.
  const text = typeof value === 'object' ? '' : String(value ?? '')

  if (field.options) {
    return (
      <select
        ref={inputRef as React.Ref<HTMLSelectElement>}
        className="ops-select"
        // Explicit, because a wrapping <label> contributes ALL its text to the
        // accessible name — so a select would be announced as its own label
        // followed by every option, and an input as "Risk required".
        aria-label={field.label}
        value={text}
        required={field.required}
        onChange={(e) => onChange(e.target.value)}
      >
        {/* Blank first, and only when the field is optional. A select that
            preselects the first option puts a value nobody chose into the row
            and calls it data. */}
        <option value="">{field.required ? 'Choose one…' : 'None'}</option>
        {field.options.map((o) => (
          <option key={o.key} value={o.key}>
            {o.label}
          </option>
        ))}
      </select>
    )
  }

  return (
    <input
      ref={inputRef as React.Ref<HTMLInputElement>}
      className="ops-input"
      aria-label={field.label}
      type={inputTypeFor(field)}
      value={text}
      required={field.required}
      onChange={(e) =>
        onChange(
          // Numbers stay numbers. A numeric field carrying "1234" as a string
          // sorts lexically, so 9 comes after 100 — which reads as a broken
          // sort rather than as a typed value.
          field.storage === 'number'
            ? e.target.value === ''
              ? ''
              : Number(e.target.value)
            : e.target.value,
        )
      }
    />
  )
}

/** A declared default, coerced to something an input can hold. Anything else —
 * a formula, an object — is not a starting value a person types over. */
function defaultFor(field: BlueprintField): string | number {
  const value = field.default
  return typeof value === 'string' || typeof value === 'number' ? value : ''
}

function inputTypeFor(field: BlueprintField): string {
  if (field.storage === 'number') return 'number'
  if (field.storage === 'timestamp') return field.type === 'datetime' ? 'datetime-local' : 'date'
  if (field.type === 'email') return 'email'
  if (field.type === 'url') return 'url'
  return 'text'
}
