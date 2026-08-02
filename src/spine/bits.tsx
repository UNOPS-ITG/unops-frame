/**
 * The spine's shared pieces: the preview pill, state chips, and the sentence.
 *
 * The sentence renderer is the load-bearing one. An automation record (AU-1)
 * is structured data; rendering it as prose-with-typed-chips is what makes
 * "automation as data" something a non-technical builder can READ — the
 * bet the whole recipe surface (AU-14) rests on. The renderer never parses
 * text; the record arrives already segmented.
 */

import type { RecipeSlot, WorkflowDef, WorkflowState } from '@/fixtures/spine/contracts'
import { stateOf } from '@/fixtures/spine/store'
import './spine.css'

/** The honesty marker for fixture-fed surfaces. It disappears with the
 * fixtures; the title says exactly what is and is not real. */
export function PreviewPill({ what }: { what: string }) {
  return (
    <span
      className="spine-preview"
      title={`${what} is fed by fixture data while the engine is built frontend-first. What you see is the intended product; the plumbing behind it is being verified with you before it is built.`}
    >
      engine preview
    </span>
  )
}

export function StateChip({ state, hero }: { state: WorkflowState; hero?: boolean }) {
  return (
    <span className={`state-chip state-chip--${state.role}${hero ? ' state-chip--hero' : ''}`}>
      {state.label}
    </span>
  )
}

/** A state chip looked up by key, for call sites that hold only the value.
 * Unknown keys render as plain text rather than a wrong colour. */
export function StateChipFor({ workflow, value }: { workflow: WorkflowDef; value: unknown }) {
  const state = stateOf(workflow, value)
  if (state === null) return <span>{typeof value === 'string' ? value : ''}</span>
  return <StateChip state={state} />
}

function Slot({ slot, workflow }: { slot: RecipeSlot; workflow?: WorkflowDef | undefined }) {
  // A state slot wears the state's own role colour — the same chip the grid
  // and the workflow panel use, so "Mitigating" means one thing everywhere.
  if (slot.kind === 'state' && workflow !== undefined) {
    const state = workflow.states.find((s) => s.label === slot.value)
    if (state !== undefined) {
      return <span className={`slot state-chip state-chip--${state.role}`}>{state.label}</span>
    }
  }
  return <span className={`slot slot--${slot.kind}`}>{slot.value}</span>
}

/** The sentence: plain segments as text, slots as typed chips. */
export function Sentence({
  segments,
  workflow,
}: {
  segments: readonly (string | RecipeSlot)[]
  workflow?: WorkflowDef | undefined
}) {
  return (
    <p className="recipe__sentence">
      {segments.map((segment, i) =>
        typeof segment === 'string' ? (
          <span key={i}>{segment}</span>
        ) : (
          <Slot key={i} slot={segment} workflow={workflow} />
        ),
      )}
    </p>
  )
}
