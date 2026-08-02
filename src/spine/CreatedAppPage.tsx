/**
 * A session-born app, opened.
 *
 * Created apps live in the spine store until the Blueprint-create engine
 * persists drafts (BP-16/AI-1), so their pages render from the reviewed
 * draft: the overview knows its purpose and model, the data views state
 * honestly that rows arrive with the engine, the automations tab lists the
 * starters, the fields tab shows the model. The point of all of it is the
 * ARRIVAL: a described app opens as an app, not as a config screen.
 */

import { Icon } from '@/app/icons'
import type { Route } from '@/app/routes'
import type { CreatedApp } from '@/fixtures/spine/store'
import { PreviewPill, StateChip } from './bits'
import './spine.css'

const TYPE_LABEL: Record<string, string> = {
  text: 'Text',
  number: 'Number',
  date: 'Date',
  select: 'Select',
  user: 'Person',
  corporate_reference: 'Corporate data',
}

export function CreatedAppPage({ app, route }: { app: CreatedApp; route: Route }) {
  const section =
    route.kind === 'recipes'
      ? 'recipes'
      : route.kind === 'fields'
        ? 'fields'
        : route.kind === 'register'
          ? route.section
          : 'overview'

  if (section === 'recipes') {
    return (
      <div className="spine-page">
        <div className="spine-page__inner">
          <div className="spine-page__head">
            <h2 className="spine-page__title">Automations</h2>
            <PreviewPill what="This app's automations" />
          </div>
          <p className="spine-page__lede">
            {app.draft.name} starts with these. They activate with the app when the engine
            persists it; edit or add more the same way you would on any app.
          </p>
          {app.draft.starterRecipes.map((r) => (
            <article key={r} className="recipe">
              <p className="recipe__sentence">
                <Icon.Bolt className="detail__glyph" /> {r}
              </p>
            </article>
          ))}
        </div>
      </div>
    )
  }

  if (section === 'fields') {
    return (
      <div className="spine-page">
        <div className="spine-page__inner">
          <div className="spine-page__head">
            <h2 className="spine-page__title">The model</h2>
            <PreviewPill what="This app's model" />
          </div>
          <p className="spine-page__lede">
            What you reviewed at creation, kept editable — no field here needed IT.
          </p>
          <div className="panel">
            {app.draft.fields.map((f) => (
              <div key={f.id} className="wizard__fieldrow">
                <span className="panel__row-title">{f.label}</span>
                <span className={`slot ${f.type === 'corporate_reference' ? 'slot--form' : 'slot--value'}`}>
                  {TYPE_LABEL[f.type] ?? f.type}
                  {f.binds !== undefined && ` · ${f.binds}`}
                </span>
                {f.required === true && <span className="gform__required">required</span>}
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (section !== 'overview') {
    // Table, board, calendar, gantt: no rows can land until the engine
    // persists the Blueprint. Said plainly, with what will change it.
    return (
      <div className="state">
        <h2 className="state__title">Rows land here</h2>
        <p className="state__body">
          {app.draft.name} exists in this session as a reviewed draft — the engine that persists
          it (and its rows, forms and views) is being built behind the checkpoint you are looking
          at. Everything around this tab is the real intended product.
        </p>
      </div>
    )
  }

  return (
    <div className="spine-page">
      <div className="overview">
        <header className="overview__hero">
          <p className="overview__eyebrow">
            your app · created this session
            <PreviewPill what="This app" />
          </p>
          <h2 className="overview__purpose">{app.draft.purpose || app.draft.name}</h2>
          <div className="overview__acts">
            <button type="button" className="btn btn--primary" disabled title="Rows arrive with the persistence engine — this draft is the review artifact.">
              <Icon.Plus />
              Add the first row
            </button>
          </div>
        </header>

        <section className="overview__stats" aria-label="State of the work">
          <div className="overview__tiles">
            {app.draft.states.map((state) => (
              <span key={state.key} className="tile">
                <span className="tile__value">0</span>
                <StateChip state={state} />
              </span>
            ))}
          </div>
        </section>

        <div className="overview__panels">
          <section className="panel" aria-label="The model">
            <h3 className="panel__title">The model you reviewed</h3>
            {app.draft.fields.slice(0, 6).map((f) => (
              <div key={f.id} className="panel__row" style={{ cursor: 'default' }}>
                <span className="panel__row-title">{f.label}</span>
                <span className="panel__row-value">{TYPE_LABEL[f.type] ?? f.type}</span>
              </div>
            ))}
          </section>
          <section className="panel" aria-label="Starts with">
            <h3 className="panel__title">Starts with</h3>
            {app.draft.starterRecipes.map((r) => (
              <p key={r} className="panel__empty">
                <Icon.Bolt className="detail__glyph" /> {r}
              </p>
            ))}
          </section>
          <section className="panel" aria-label="What happens next">
            <h3 className="panel__title">What happens next</h3>
            <p className="panel__empty">
              This app is yours, in this workspace. When it proves itself, promotion shares it —
              with your name on it — and other teams adopt it the way you adopted a template:
              locked base, their additions beside it.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
