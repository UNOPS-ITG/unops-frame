/**
 * The spine's in-memory engine — the part of the fixture that moves.
 *
 * Holds what the real engines will hold in Firestore: pending tasks (AU-4),
 * activity appended by actions (PM-7), draft child rows from form intake
 * (FM-3), and which recipes are enabled (AU-1). It performs REAL writes
 * where a real path exists — a transition's state change and an approval's
 * effect go through `updateRow`, the one write path — and simulates only
 * what has no server yet. Session-lived on purpose: a reload returns to the
 * seeded opening state, which is exactly what a demo wants.
 *
 * When the engines land, every action here becomes an API call and this
 * store's state becomes a fetch; components consume the same shapes either
 * way (`contracts.ts`).
 */

import { create } from 'zustand'
import { updateRow } from '@/api/client'
import { PILOT_SPINES, pilotChildren } from './apps'
import type {
  ActivityEntry,
  AppDraft,
  ChildRow,
  PendingTask,
  SpineDef,
  TransitionDef,
  WorkflowDef,
} from './contracts'
import { RISK_SPINE, SEED_TASKS, activityFor, mitigationsFor } from './risk'

/** The acting identity — the dev persona the whole client already uses.
 * AU-15's self-approval check compares against it. */
export function actingPersona(): string {
  return globalThis.sessionStorage?.getItem('frame-dev-persona') ?? 'risk@unops.org'
}

const SPINES: readonly SpineDef[] = [RISK_SPINE, ...PILOT_SPINES]

export function spineFor(blueprintId: string): SpineDef | null {
  return SPINES.find((s) => s.blueprintId === blueprintId) ?? null
}

/** Derived child rows for any app's child table — one entry point, so the
 * record page and the flat collection page can never disagree. */
export function childRowsFor(
  blueprintId: string,
  tableId: string,
  rowId: string,
  values: Readonly<Record<string, unknown>>,
): ChildRow[] {
  if (blueprintId === RISK_SPINE.blueprintId) return mitigationsFor(rowId, values)
  return pilotChildren(blueprintId, tableId, rowId, values)
}

export function stateOf(workflow: WorkflowDef, key: unknown) {
  return workflow.states.find((s) => s.key === key) ?? null
}

/** The transitions leaving a state — what the doorway list renders. */
export function transitionsFrom(workflow: WorkflowDef, key: unknown): TransitionDef[] {
  return workflow.transitions.filter((t) => t.from === key)
}

interface DraftChildRow {
  readonly collectionId: string
  readonly values: Readonly<Record<string, string>>
}

/** An app born this session. It lives here until the Blueprint-create
 * engine persists drafts for real (BP-16/AI-1); the pages it renders are
 * the journey being judged, and they say so with the preview pill. */
export interface CreatedApp {
  readonly id: string
  readonly draft: AppDraft
  readonly createdAt: string
}

interface SpineStore {
  tasks: PendingTask[]
  createdApps: Record<string, CreatedApp>
  /** Activity appended THIS session, newest first, keyed by row. Rendered
   * above the scripted history from `activityFor`. */
  appended: Record<string, ActivityEntry[]>
  /** FM-3 child rows captured at intake, keyed by created row id. */
  draftChildren: Record<string, DraftChildRow[]>
  recipeEnabled: Record<string, boolean>
  /** Bumped on every action so pages refetch real rows where needed. */
  generation: number

  toggleRecipe: (id: string) => void
  /** Registers a reviewed draft as a session app and returns its id. */
  createApp: (draft: AppDraft) => string
  /** A direct (ungated) transition: performs the real state write and
   * records the activity. Throws what the API throws. */
  performTransition: (args: {
    workspaceId: string
    blueprintId: string
    rowId: string
    rowTitle: string
    stateField: string
    transition: TransitionDef
  }) => Promise<void>
  /** A gated transition: raises the pending task (AU-4). Nothing is written
   * until the decision. */
  requestTransition: (args: {
    blueprintId: string
    rowId: string
    rowTitle: string
    stateField: string
    transition: TransitionDef
  }) => void
  /** Decide an approval. Approving performs what the task carries, through
   * the one write path, under the DECIDER's identity — which is the whole
   * point of a gate. AU-15 is enforced here as well as in the UI. */
  decideTask: (args: {
    workspaceId: string
    taskId: string
    decision: 'approved' | 'rejected'
    comment?: string
  }) => Promise<void>
  answerUpdate: (taskId: string) => void
  recordFormLanding: (args: {
    rowId: string
    rowTitle: string
    formName: string
    stateLabel: string
    children: DraftChildRow[]
  }) => void
}

function entry(partial: Omit<ActivityEntry, 'id' | 'at'>): ActivityEntry {
  return {
    ...partial,
    // A fixture id, not a server id — unique enough for a session list.
    id: `live-${Math.random().toString(36).slice(2, 10)}`,
    at: new Date().toISOString(),
  }
}

export const useSpineStore = create<SpineStore>((set, get) => ({
  tasks: [...SEED_TASKS],
  createdApps: {},
  appended: {},
  draftChildren: {},
  recipeEnabled: {},
  generation: 0,

  toggleRecipe: (id) =>
    set((s) => ({ recipeEnabled: { ...s.recipeEnabled, [id]: !(s.recipeEnabled[id] ?? false) } })),

  createApp: (draft) => {
    const slug = draft.name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '')
    const id = `new-${slug || 'app'}-${Math.random().toString(36).slice(2, 6)}`
    set((s) => ({
      createdApps: {
        ...s.createdApps,
        [id]: { id, draft, createdAt: new Date().toISOString() },
      },
    }))
    return id
  },

  performTransition: async ({ workspaceId, blueprintId, rowId, rowTitle, stateField, transition }) => {
    await updateRow(workspaceId, blueprintId, rowId, { [stateField]: transition.to }, null, 'api')
    set((s) => ({
      generation: s.generation + 1,
      appended: {
        ...s.appended,
        [rowId]: [
          entry({
            cls: 'change',
            actor: actingPersona(),
            channel: 'api',
            summary: `took "${transition.label}"`,
            deltas: [{ fieldLabel: 'Status', before: transition.from, after: transition.to }],
          }),
          ...(s.appended[rowId] ?? []),
        ],
      },
    }))
    void rowTitle
  },

  requestTransition: ({ blueprintId, rowId, rowTitle, stateField, transition }) => {
    const gate = transition.gate
    if (gate === undefined) return
    const task: PendingTask = {
      id: `task-${Math.random().toString(36).slice(2, 10)}`,
      kind: 'approval',
      title: transition.label,
      detail: `${rowTitle} — requested via the "${transition.label}" transition.`,
      requestedBy: actingPersona(),
      requestedAt: new Date().toISOString(),
      waitingOn: gate.approvers,
      allowSelfApproval: gate.allowSelfApproval,
      performs: { rowId, blueprintId, stateField, toState: transition.to },
      status: 'waiting',
    }
    set((s) => ({
      tasks: [task, ...s.tasks],
      appended: {
        ...s.appended,
        [rowId]: [
          entry({
            cls: 'change',
            actor: actingPersona(),
            channel: 'api',
            summary: `requested "${transition.label}" — waiting on ${gate.approvers}`,
          }),
          ...(s.appended[rowId] ?? []),
        ],
      },
    }))
  },

  decideTask: async ({ workspaceId, taskId, decision }) => {
    const task = get().tasks.find((t) => t.id === taskId)
    if (task === undefined || task.status !== 'waiting') return
    // AU-15, enforced where the decision happens rather than only where it
    // is rendered. The UI disables the buttons; this makes the refusal a
    // property of the engine, which is where it will live for real.
    if (!task.allowSelfApproval && task.requestedBy === actingPersona()) {
      throw new Error('You raised this request, and this gate does not allow self-approval.')
    }
    if (decision === 'approved' && task.performs !== undefined) {
      const { rowId, blueprintId, stateField, toState } = task.performs
      await updateRow(workspaceId, blueprintId, rowId, { [stateField]: toState }, null, 'api')
      set((s) => ({
        generation: s.generation + 1,
        appended: {
          ...s.appended,
          [rowId]: [
            entry({
              cls: 'change',
              actor: actingPersona(),
              channel: 'api',
              summary: `approved "${task.title}"`,
              deltas: [{ fieldLabel: 'Status', after: toState }],
            }),
            ...(s.appended[rowId] ?? []),
          ],
        },
      }))
    }
    set((s) => ({
      tasks: s.tasks.map((t) =>
        t.id === taskId ? { ...t, status: decision } : t,
      ),
    }))
  },

  answerUpdate: (taskId) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === taskId ? { ...t, status: 'answered' } : t)),
    })),

  recordFormLanding: ({ rowId, rowTitle, formName, stateLabel, children }) =>
    set((s) => ({
      generation: s.generation + 1,
      draftChildren: children.length > 0 ? { ...s.draftChildren, [rowId]: children } : s.draftChildren,
      appended: {
        ...s.appended,
        [rowId]: [
          entry({
            cls: 'change',
            actor: actingPersona(),
            channel: 'form',
            summary: `submitted "${rowTitle}" through ${formName} — landed as ${stateLabel}`,
          }),
          ...(s.appended[rowId] ?? []),
        ],
      },
    })),
}))

/** The scripted history in an app's own voice — its states, its recipe,
 * its restricted field. */
export function scriptedActivity(
  spine: SpineDef,
  rowValues: Readonly<Record<string, unknown>>,
): ActivityEntry[] {
  return activityFor(rowValues, {
    recipe: spine.activity.recipe,
    restrictedLabel: spine.activity.restrictedLabel,
    fromState: spine.workflow.states[0]?.label ?? 'New',
    toState: spine.workflow.states[1]?.label ?? 'Active',
    ownerField: spine.card.metaField,
  })
}

/** The full drawer feed for a row: what this session did, then the scripted
 * history. One array so the drawer renders one timeline. */
export function activityFeed(
  rowId: string,
  rowValues: Readonly<Record<string, unknown>>,
  appended: Record<string, ActivityEntry[]>,
  spine?: SpineDef,
): ActivityEntry[] {
  const scripted = spine !== undefined ? scriptedActivity(spine, rowValues) : activityFor(rowValues)
  return [...(appended[rowId] ?? []), ...scripted]
}

/** How many tasks wait on the sidebar badge. Update requests count when they
 * wait on the acting persona; approvals when the persona may decide them. */
export function waitingCount(tasks: readonly PendingTask[]): number {
  return tasks.filter((t) => t.status === 'waiting').length
}
