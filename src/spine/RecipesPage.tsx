/**
 * The register's automations, as sentences (AU-14).
 *
 * An automation is a structured record (AU-1), and the sentence is that
 * record rendered honestly — trigger, condition, actions, with the
 * parameters as typed chips. There is no canvas and no flowchart here, on
 * purpose (N3): a flow that needs branches and waits belongs to Workflow
 * Studio, and it graduates there mechanically because this record is data.
 * The gallery below the installed list is code-first configuration: a
 * vocabulary change that orphans a template fails CI, never a user.
 */

import { Icon } from '@/app/icons'
import { href } from '@/app/routes'
import type { RecipeDef, SpineDef } from '@/fixtures/spine/contracts'
import { useSpineStore } from '@/fixtures/spine/store'
import { PreviewPill, Sentence } from './bits'
import './spine.css'

function lastRunLabel(recipe: RecipeDef): string {
  if (recipe.lastRun === null) return 'never run'
  return `last ran ${new Date(recipe.lastRun).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })}`
}

export function RecipesPage({
  workspaceId,
  blueprintId,
  spine,
}: {
  workspaceId: string
  blueprintId: string
  spine: SpineDef | null
}) {
  const enabledOverride = useSpineStore((s) => s.recipeEnabled)
  const toggleRecipe = useSpineStore((s) => s.toggleRecipe)

  if (spine === null) {
    return (
      <div className="spine-page">
        <div className="spine-page__inner">
          <h2 className="spine-page__title">Automations</h2>
          <p className="spine-page__lede">
            This register has no automations yet. They arrive with the engine preview on the demo
            register first —{' '}
            <a href={href.register(workspaceId, blueprintId)}>back to the grid</a>.
          </p>
        </div>
      </div>
    )
  }

  const isOn = (r: RecipeDef) => enabledOverride[r.id] ?? r.enabled
  const installed = spine.recipes.filter((r) => r.template !== true || isOn(r))
  const gallery = spine.recipes.filter((r) => r.template === true && !isOn(r))

  return (
    <div className="spine-page">
      <div className="spine-page__inner">
        <div className="spine-page__head">
          <h2 className="spine-page__title">Automations</h2>
          <PreviewPill what="The automation engine" />
        </div>
        <p className="spine-page__lede">
          An automation is a record you can read: a trigger, its conditions, and actions from a
          closed vocabulary — no scripts, ever, at any tier. Every run is logged per recipe, and a
          recipe that outgrows this page graduates to Workflow Studio as data, not as a rewrite.
        </p>

        {installed.map((r) => (
          <RecipeCard
            key={r.id}
            recipe={r}
            spine={spine}
            on={isOn(r)}
            onToggle={() => toggleRecipe(r.id)}
          />
        ))}

        {gallery.length > 0 && (
          <>
            <h3 className="spine-page__section">From the gallery — one click to adopt</h3>
            {gallery.map((r) => (
              <RecipeCard
                key={r.id}
                recipe={r}
                spine={spine}
                on={false}
                gallery
                onToggle={() => toggleRecipe(r.id)}
              />
            ))}
          </>
        )}
      </div>
    </div>
  )
}

function RecipeCard({
  recipe,
  spine,
  on,
  gallery = false,
  onToggle,
}: {
  recipe: RecipeDef
  spine: SpineDef
  on: boolean
  gallery?: boolean
  onToggle: () => void
}) {
  return (
    <article className="recipe" aria-label={recipe.title}>
      <div className="recipe__top">
        <h3 className="recipe__title">{recipe.title}</h3>
        <span className="recipe__trigger">{recipe.trigger}</span>
      </div>

      <Sentence segments={recipe.sentence} workflow={spine.workflow} />

      <div className="recipe__meta">
        {!gallery && (
          <>
            <span>{recipe.runs30d.toLocaleString()} runs in 30 days</span>
            <span>{lastRunLabel(recipe)}</span>
          </>
        )}
        {gallery && <span>Adopting copies this record into the register — yours to edit after.</span>}
        <span className="recipe__meta-spacer" />
        {gallery ? (
          <button type="button" className="btn btn--secondary btn--sm" onClick={onToggle}>
            <Icon.Plus />
            Add to this register
          </button>
        ) : (
          <label className="recipe__switch">
            <input type="checkbox" checked={on} onChange={onToggle} />
            <span className="recipe__track" aria-hidden="true" />
            {on ? 'On' : 'Off'}
          </label>
        )}
      </div>
    </article>
  )
}
