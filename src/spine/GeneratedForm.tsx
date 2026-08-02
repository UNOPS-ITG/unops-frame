/**
 * A named form, generated from the Blueprint (FM-1).
 *
 * There is no form designer and there will not be one: the form's fields ARE
 * Blueprint fields, its logic is the Blueprint's (BP-3a, declared once), and
 * a named form may only tighten — require more, show less — never loosen
 * (FM-2). What this component adds over the quick dialog is intake shape:
 * sections with intent, a repeatable child section whose line items travel
 * with the row in one transaction (FM-3), and an honest statement of what
 * submitting does (FM-7's landing state), because a form that says where the
 * row goes is intake, and one that does not is a message box.
 *
 * The row's base fields are written through the real API on the `form`
 * channel — the write is not a fixture. The child rows and the landing
 * automation are recorded through the spine store until their engines land.
 */

import { useMemo, useRef, useState } from 'react'
import { ApiError, createRow, type LookupRow } from '@/api/client'
import { Icon } from '@/app/icons'
import { CorporatePicker } from '@/corporate/CorporatePicker'
import type { Blueprint, BlueprintField } from '@/grid/contract'
import type { FormDef, SpineDef } from '@/fixtures/spine/contracts'
import { stateOf, useSpineStore } from '@/fixtures/spine/store'
import { FieldInput } from '@/registers/NewRow'
import { PreviewPill, StateChip } from './bits'
import './spine.css'

interface PickedRef {
  key: string
  label: string
}

type Draft = Record<string, string | number | PickedRef>

export function GeneratedForm({
  workspaceId,
  blueprint,
  spine,
  form,
  onCreated,
  onClose,
}: {
  workspaceId: string
  blueprint: Blueprint
  spine: SpineDef
  form: FormDef
  onCreated: (rowId: string) => void
  onClose: () => void
}) {
  const recordFormLanding = useSpineStore((s) => s.recordFormLanding)

  const fieldOf = useMemo(() => {
    const byId = new Map(blueprint.fields.map((f) => [f.id, f]))
    return (id: string) => byId.get(id)
  }, [blueprint])

  const [values, setValues] = useState<Draft>({})
  const [children, setChildren] = useState<Record<string, string>[]>([])
  const [picking, setPicking] = useState<BlueprintField | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const first = useRef<HTMLInputElement | HTMLSelectElement>(null)

  const landingState = stateOf(spine.workflow, form.landing.stateKey)
  const child = form.childSection

  const addChild = () => {
    if (child === undefined) return
    setChildren((rows) => [...rows, Object.fromEntries(child.columns.map((c) => [c.id, '']))])
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setErrors({})
    setMessage(null)
    try {
      // Base fields through the one write path, on the `form` channel
      // (PM-7 records how a write arrived). The landing state is FM-7's:
      // the form sets it, the submitter is told it will.
      const payload: Record<string, unknown> = Object.fromEntries(
        Object.entries(values).filter(([, v]) => v !== '' && v !== undefined),
      )
      payload[spine.workflow.stateField] = form.landing.stateKey
      const created = await createRow(workspaceId, blueprint.id, payload, 'form')

      // FM-3's line items and the intake automation, recorded in the spine
      // store until children and the engine are served for real.
      const kept = children.filter((row) => Object.values(row).some((v) => v.trim() !== ''))
      const titleValue = payload['title']
      recordFormLanding({
        rowId: created.id,
        rowTitle: typeof titleValue === 'string' && titleValue !== '' ? titleValue : created.id,
        formName: form.name,
        stateLabel: landingState?.label ?? form.landing.stateKey,
        children: kept.map((row) => ({ collectionId: child?.collectionId ?? '', values: row })),
      })
      onCreated(created.id)
      onClose()
    } catch (e) {
      if (e instanceof ApiError && e.fieldErrors.length > 0) {
        setErrors(Object.fromEntries(e.fieldErrors.map((f) => [f.fieldId, f.message])))
        setMessage('Nothing was submitted — the fields marked below need attention.')
      } else {
        setMessage(e instanceof ApiError ? e.message : 'The form could not be submitted')
      }
    } finally {
      setBusy(false)
    }
  }

  // The first field the form actually renders gets focus — computed ahead of
  // the render rather than flagged during it, which React (rightly) forbids.
  const firstFieldId = form.sections
    .flatMap((s) => s.fields)
    .map((ref) => fieldOf(ref.fieldId))
    .find((f) => f !== undefined && !f.readOnly && f.writable)?.id

  return (
    <div
      className="picker__backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <form
        className="gform"
        onSubmit={(e) => void submit(e)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose()
        }}
        aria-label={form.name}
      >
        <div className="gform__header">
          <div className="gform__eyebrow">
            <span>
              {blueprint.name} · internal form
            </span>
            <PreviewPill what="The form definition" />
          </div>
          <h2 className="gform__title">
            {form.name}
            <button
              type="button"
              className="btn btn--ghost btn--icon btn--sm"
              style={{ marginInlineStart: 'auto' }}
              onClick={onClose}
              aria-label="Close"
            >
              <Icon.Close />
            </button>
          </h2>
          <p className="gform__intro">{form.intro}</p>
        </div>

        <div className="gform__body scrollable">
          {form.sections.map((section) => (
            <section key={section.title} className="gform__section">
              <h3 className="gform__section-title">{section.title}</h3>
              {section.hint !== undefined && <p className="gform__section-hint">{section.hint}</p>}
              <div className="gform__grid">
                {section.fields.map((ref) => {
                  const field = fieldOf(ref.fieldId)
                  if (field === undefined || field.readOnly || !field.writable) return null
                  // FM-2: the form may REQUIRE more than the Blueprint,
                  // never less — union, not override.
                  const required = field.required || ref.required === true
                  const shown: BlueprintField = { ...field, required }
                  const takeFocus = field.id === firstFieldId
                  return (
                    <label key={field.id} className="gform__field">
                      <span className="gform__label">
                        {field.label}
                        {required && (
                          <span className="gform__required" aria-hidden="true">
                            required
                          </span>
                        )}
                      </span>
                      <FieldInput
                        field={shown}
                        value={values[field.id]}
                        onChange={(v) => setValues((prev) => ({ ...prev, [field.id]: v }))}
                        inputRef={takeFocus ? first : undefined}
                        onPick={() => setPicking(field)}
                      />
                      {(ref.helpText ?? field.helpText) !== null &&
                        (ref.helpText ?? field.helpText) !== undefined && (
                          <span className="gform__help">{ref.helpText ?? field.helpText}</span>
                        )}
                      {errors[field.id] !== undefined && (
                        <span className="gform__error" role="alert">
                          {errors[field.id]}
                        </span>
                      )}
                    </label>
                  )
                })}
              </div>
            </section>
          ))}

          {child !== undefined && (
            <section className="gform__section">
              <h3 className="gform__section-title">{child.title}</h3>
              {child.hint !== undefined && <p className="gform__section-hint">{child.hint}</p>}
              <div className="gform__children">
                <div className="gform__children-head" aria-hidden="true">
                  {child.columns.map((c) => (
                    <span key={c.id}>{c.label}</span>
                  ))}
                  <span />
                </div>
                {children.map((row, index) => (
                  <div key={index} className="gform__child">
                    {child.columns.map((c) => (
                      <input
                        key={c.id}
                        className="ops-input"
                        type={c.type === 'date' ? 'date' : c.type === 'number' ? 'number' : 'text'}
                        aria-label={`${c.label}, line ${index + 1}`}
                        value={row[c.id] ?? ''}
                        onChange={(e) =>
                          setChildren((rows) =>
                            rows.map((r, i) => (i === index ? { ...r, [c.id]: e.target.value } : r)),
                          )
                        }
                      />
                    ))}
                    <button
                      type="button"
                      className="btn btn--ghost btn--icon btn--sm"
                      aria-label={`Remove line ${index + 1}`}
                      onClick={() => setChildren((rows) => rows.filter((_, i) => i !== index))}
                    >
                      <Icon.Close />
                    </button>
                  </div>
                ))}
                <button type="button" className="gform__add-child" onClick={addChild}>
                  <Icon.Plus />
                  {child.addLabel}
                </button>
              </div>
            </section>
          )}
        </div>

        {message !== null && (
          <p className="gform__message" role="alert">
            {message}
          </p>
        )}

        <div className="gform__footer">
          <span className="gform__landing">
            {landingState !== null && <StateChip state={landingState} />}
            {form.landing.explains}
          </span>
          <button type="submit" className="btn btn--primary btn--sm" disabled={busy}>
            {busy ? 'Submitting…' : form.verb}
          </button>
          <button type="button" className="btn btn--ghost btn--sm" onClick={onClose} disabled={busy}>
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
            setPicking((p) => {
              if (p !== null) setValues((prev) => ({ ...prev, [p.id]: { key: row.key, label: row.label } }))
              return null
            })
          }}
          onClose={() => setPicking(null)}
        />
      )}
    </div>
  )
}
