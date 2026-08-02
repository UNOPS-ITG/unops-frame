/**
 * Making an app — the moment the whole product claims to be about.
 *
 * Two doors in, one review, one act. Describe the work in your own words
 * and get a draft (AI-1's contract: text in, reviewable model out, nothing
 * created until a person says so), or adopt one of the four pilot
 * templates (AC-7: the app arrives with its states, starter automations
 * and child collections working, its base locked, your additions beside
 * it — BP-28). Either way the draft is confronted before it exists:
 * fields are renamed and removed here, in the one place a creator is
 * already paying attention, which is BP-16's typing wizard doing its job.
 *
 * The word "Blueprint" appears nowhere. A user makes an APP; the Blueprint
 * is what the engine writes down about it.
 */

import { useState } from 'react'
import { Icon } from '@/app/icons'
import { href, navigate } from '@/app/routes'
import type { AppDraft, DraftField } from '@/fixtures/spine/contracts'
import { APP_TEMPLATES, draftFromDescription } from '@/fixtures/spine/templates'
import { useSpineStore } from '@/fixtures/spine/store'
import { PreviewPill, StateChip } from './bits'
import './spine.css'

const FIELD_TYPES: DraftField['type'][] = ['text', 'number', 'date', 'select', 'user', 'corporate_reference']

const TYPE_LABEL: Record<DraftField['type'], string> = {
  text: 'Text',
  number: 'Number',
  date: 'Date',
  select: 'Select',
  user: 'Person',
  corporate_reference: 'Corporate data',
}

export function NewAppWizard({ workspaceId, onClose }: { workspaceId: string; onClose: () => void }) {
  const createApp = useSpineStore((s) => s.createApp)
  const [draft, setDraft] = useState<AppDraft | null>(null)
  const [description, setDescription] = useState('')

  const create = () => {
    if (draft === null) return
    const id = createApp(draft)
    onClose()
    navigate(href.register(workspaceId, id))
  }

  return (
    <div
      className="picker__backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className="wizard"
        role="dialog"
        aria-label="New app"
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose()
        }}
      >
        <div className="gform__header">
          <div className="gform__eyebrow">
            <span>New app</span>
            <PreviewPill what="Drafting and creation" />
          </div>
          <h2 className="gform__title">
            {draft === null ? 'What are you tracking?' : 'Here is your app — check it before it exists'}
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
          {draft === null ? (
            <p className="gform__intro">
              Say it the way you would to a colleague, or start from an app the organization
              already runs. Either way you review the model before anything is created.
            </p>
          ) : (
            <p className="gform__intro">
              Rename or remove what does not fit — the app is yours before it is anyone's.
              Everything here can change later; nothing here needs IT.
            </p>
          )}
        </div>

        {draft === null ? (
          <div className="gform__body scrollable">
            <section className="gform__section">
              <h3 className="gform__section-title">Describe it</h3>
              <textarea
                className="ops-textarea"
                rows={3}
                placeholder='e.g. "Track vendor security assessments with a reviewer, a risk rating and a 30-day follow-up"'
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                aria-label="Describe what you are tracking"
              />
              <div className="wizard__draft-row">
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  disabled={description.trim().length < 8}
                  onClick={() => setDraft(draftFromDescription(description))}
                >
                  <Icon.Bolt />
                  Draft my app
                </button>
                <span className="gform__help">
                  A draft, not a fait accompli — you see every field before it exists.
                </span>
              </div>
            </section>

            <section className="gform__section">
              <h3 className="gform__section-title">Or start from a working app</h3>
              <p className="gform__section-hint">
                Adopting binds you to the shared model — upstream improvements arrive
                automatically, and your additions live safely beside the locked base.
              </p>
              <div className="wizard__gallery">
                {APP_TEMPLATES.map((tpl) => (
                  <button
                    key={tpl.id}
                    type="button"
                    className="wizard__tpl"
                    onClick={() =>
                      setDraft({
                        name: tpl.name,
                        purpose: tpl.tagline,
                        fields: tpl.fields,
                        states: tpl.states,
                        starterRecipes: tpl.starterRecipes,
                        fromTemplate: tpl.id,
                      })
                    }
                  >
                    <span className="wizard__tpl-name">{tpl.name}</span>
                    <span className="wizard__tpl-tag">{tpl.tagline}</span>
                    <span className="wizard__tpl-meta">
                      <span className="wizard__tpl-states">
                        {tpl.states.map((s) => (
                          <StateChip key={s.key} state={s} />
                        ))}
                      </span>
                    </span>
                    <span className="wizard__tpl-meta">
                      {tpl.fields.length} fields · {tpl.starterRecipes.length} automations
                      {tpl.hasChildCollections.length > 0 && ` · ${tpl.hasChildCollections.join(', ')}`}
                    </span>
                    {tpl.extendsWith !== undefined && (
                      <span className="wizard__tpl-ext">{tpl.extendsWith}</span>
                    )}
                  </button>
                ))}
              </div>
            </section>
          </div>
        ) : (
          <ReviewStep draft={draft} onChange={setDraft} />
        )}

        <div className="gform__footer">
          {draft === null ? (
            <span className="gform__landing">
              No forms to fill for IT, no deploy, no wait — an app is a model you describe.
            </span>
          ) : (
            <>
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => setDraft(null)}>
                Start over
              </button>
              <span className="gform__landing">
                Creates in this workspace as yours — share and promote when it earns it.
              </span>
              <button type="button" className="btn btn--primary btn--sm" onClick={create}>
                <Icon.Check />
                Create {draft.name}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function ReviewStep({ draft, onChange }: { draft: AppDraft; onChange: (d: AppDraft) => void }) {
  const setField = (index: number, patch: Partial<DraftField>) =>
    onChange({
      ...draft,
      fields: draft.fields.map((f, i) => (i === index ? { ...f, ...patch } : f)),
    })

  return (
    <div className="gform__body scrollable">
      <section className="gform__section">
        <div className="gform__grid">
          <label className="gform__field">
            <span className="gform__label">App name</span>
            <input
              className="ops-input"
              value={draft.name}
              aria-label="App name"
              onChange={(e) => onChange({ ...draft, name: e.target.value })}
            />
          </label>
          <label className="gform__field">
            <span className="gform__label">What it is for</span>
            <input
              className="ops-input"
              value={draft.purpose}
              aria-label="Purpose"
              onChange={(e) => onChange({ ...draft, purpose: e.target.value })}
            />
          </label>
        </div>
      </section>

      <section className="gform__section">
        <h3 className="gform__section-title">Fields</h3>
        <p className="gform__section-hint">
          A field marked "Corporate data" pulls from the organization's own registers — the
          column knows its supplier or project instead of holding typed text.
        </p>
        <div className="wizard__fields">
          {draft.fields.map((field, i) => (
            <div key={`${field.id}-${i}`} className="wizard__fieldrow">
              <input
                className="ops-input"
                value={field.label}
                aria-label={`Field ${i + 1} name`}
                onChange={(e) => setField(i, { label: e.target.value })}
              />
              <span className={`slot ${field.type === 'corporate_reference' ? 'slot--form' : 'slot--value'}`}>
                {TYPE_LABEL[field.type]}
                {field.binds !== undefined && ` · ${field.binds}`}
              </span>
              {field.required === true && <span className="gform__required">required</span>}
              <button
                type="button"
                className="btn btn--ghost btn--icon btn--sm"
                aria-label={`Remove ${field.label}`}
                onClick={() =>
                  onChange({ ...draft, fields: draft.fields.filter((_, x) => x !== i) })
                }
              >
                <Icon.Close />
              </button>
            </div>
          ))}
          <AddField
            onAdd={(f) => onChange({ ...draft, fields: [...draft.fields, f] })}
          />
        </div>
      </section>

      <section className="gform__section">
        <h3 className="gform__section-title">How work moves</h3>
        <div className="wizard__states">
          {draft.states.map((s, i) => (
            <span key={s.key} className="wizard__state">
              {i > 0 && <Icon.ArrowRight className="door__arrow" />}
              <StateChip state={s} />
            </span>
          ))}
        </div>
      </section>

      <section className="gform__section">
        <h3 className="gform__section-title">Starts with these automations</h3>
        <ul className="wizard__recipes">
          {draft.starterRecipes.map((r) => (
            <li key={r}>
              <Icon.Bolt className="detail__glyph" /> {r}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

function AddField({ onAdd }: { onAdd: (f: DraftField) => void }) {
  const [label, setLabel] = useState('')
  const [type, setType] = useState<DraftField['type']>('text')
  return (
    <div className="wizard__fieldrow wizard__fieldrow--add">
      <input
        className="ops-input"
        placeholder="Add a field…"
        value={label}
        aria-label="New field name"
        onChange={(e) => setLabel(e.target.value)}
      />
      <select
        className="ops-select"
        aria-label="New field type"
        value={type}
        onChange={(e) => setType(e.target.value as DraftField['type'])}
      >
        {FIELD_TYPES.map((t) => (
          <option key={t} value={t}>
            {TYPE_LABEL[t]}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="btn btn--secondary btn--sm"
        disabled={label.trim() === ''}
        onClick={() => {
          onAdd({ id: label.toLowerCase().replace(/[^a-z0-9]+/g, '_'), label: label.trim(), type })
          setLabel('')
        }}
      >
        <Icon.Plus />
        Add
      </button>
    </div>
  )
}
