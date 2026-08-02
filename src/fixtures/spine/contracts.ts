/**
 * The application spine's wire shapes, drafted as fixtures.
 *
 * These types are the API contract the spine engines will serve — written
 * client-first per the frontend-first method, so the backend arrives to a
 * shape the product has already been judged in, and the swap is mechanical
 * rather than a rework. Each shape names the PRD requirements it drafts:
 *
 * - `WorkflowDef` / `TransitionDef` — AU-10 state machines bound to a select
 *   field, with AU-15's `allowSelfApproval` default-false on gated steps.
 * - `FormDef` — FM-1 named forms generated from the Blueprint, FM-2's
 *   tighten-only overrides, FM-3's repeatable child sections.
 * - `RecipeDef` — AU-1 automation records rendered per AU-14's sentence
 *   gallery, with AU-16 expression parameters carried as grammar strings.
 * - `PendingTask` — AU-4/AU-4a's single pending-task record, both classes.
 * - `ActivityEntry` — PM-7's typed audit classes as the activity drawer
 *   reads them, deltas already trimmed by the server's Decision (PM-10).
 * - `ExtensionDef` — BP-28's locked-base workspace extensions, rendered
 *   transparently as columns and child collections.
 *
 * Nothing here decides anything — same rule as `grid/contract.ts`. When the
 * engines exist these shapes move to that file (or are served per-Blueprint)
 * and the fixture module dies; the components must not care which happened.
 */

/** One workflow state, bound to an option of the Blueprint's state field.
 * The chip colours come from the option's own display attributes (BP-2):
 * a status vocabulary is coloured once in the model, not per surface. */
export interface WorkflowState {
  readonly key: string
  readonly label: string
  /** Which status-role token family renders this state. The token system is
   * the vocabulary; a state names a role, never a colour. */
  readonly role: 'draft' | 'progress' | 'active' | 'closed' | 'danger' | 'warning'
  /** Terminal states offer no outbound transitions and say so. */
  readonly terminal?: boolean
}

export interface TransitionGate {
  /** Who may decide. Display strings for now; PM-1 principals later. */
  readonly approvers: string
  /** AU-15: the actor whose action raised the task may not decide it.
   * Default false — carried explicitly so the UI can explain a refusal. */
  readonly allowSelfApproval: boolean
}

export interface TransitionDef {
  readonly id: string
  readonly from: string
  readonly to: string
  /** The verb on the button: "Start mitigation", never "open→mitigating". */
  readonly label: string
  /** Present when the transition is approval-gated (AU-4). The transition
   * then *requests* rather than performs, and the decision lives in the
   * inbox as a PendingTask. */
  readonly gate?: TransitionGate
  /** A grammar condition the engine will evaluate (AU-10: gates read only
   * data Frame holds). Shown to the user as the reason a doorway is shut. */
  readonly condition?: { readonly expression: string; readonly explains: string }
}

export interface WorkflowDef {
  /** The Blueprint field whose options are the states (AU-10: states drive
   * board lanes; here they drive the grid's chip column). */
  readonly stateField: string
  readonly states: readonly WorkflowState[]
  readonly transitions: readonly TransitionDef[]
}

/** A form field entry: which Blueprint field, plus tighten-only overrides
 * (FM-1/FM-2 — a form may require more, never less; hide, never reveal). */
export interface FormFieldRef {
  readonly fieldId: string
  readonly required?: boolean
  readonly helpText?: string
}

export interface FormSection {
  readonly title: string
  readonly hint?: string
  readonly fields: readonly FormFieldRef[]
}

/** FM-3: a repeatable section bound to a child collection. The columns are
 * the child Blueprint's fields, drafted inline until children are served. */
export interface ChildSection {
  readonly collectionId: string
  readonly title: string
  readonly hint?: string
  readonly addLabel: string
  readonly columns: readonly {
    readonly id: string
    readonly label: string
    readonly type: 'text' | 'date' | 'number'
    readonly required?: boolean
  }[]
}

export interface FormDef {
  readonly id: string
  readonly name: string
  /** The submit button and the confirmation both use it: a form is an act,
   * and "Submit" is nobody's act. */
  readonly verb: string
  readonly intro: string
  readonly sections: readonly FormSection[]
  readonly childSection?: ChildSection
  /** What FM-7 does on landing: the initial state, stated so the form can
   * honestly tell the submitter what happens next. */
  readonly landing: { readonly stateKey: string; readonly explains: string }
}

/** One slot in a recipe sentence. `kind` picks the chip's rendering; `value`
 * is the display form. An `expression` slot is AU-16: a grammar expression
 * at row scope, shown as code rather than prose because it IS the contract. */
export interface RecipeSlot {
  readonly kind: 'field' | 'value' | 'principal' | 'state' | 'expression' | 'form'
  readonly value: string
}

/** AU-1: an automation is a structured record. The sentence is its honest
 * rendering — trigger, condition, actions in order — and the slots are the
 * parameters a team edits. AU-14 ships these as a code-first gallery. */
export interface RecipeDef {
  readonly id: string
  readonly title: string
  /** The sentence as segments: plain strings and typed slots, interleaved.
   * Rendering never re-parses prose; the record is already structured. */
  readonly sentence: readonly (string | RecipeSlot)[]
  readonly trigger: string
  readonly enabled: boolean
  /** AU-6 observability, abbreviated: the gallery states that runs are
   * logged per recipe, because an automation you cannot see run is one you
   * turn off the first time it surprises you. */
  readonly runs30d: number
  readonly lastRun: string | null
  /** Set when this entry is a gallery template rather than an installed
   * automation — instantiating copies it into the workspace (AU-14). */
  readonly template?: boolean
}

/** AU-4/AU-4a: approvals and update requests are two classes of ONE record. */
export interface PendingTask {
  readonly id: string
  readonly kind: 'approval' | 'update'
  readonly title: string
  readonly detail: string
  /** Who raised it — compared against the acting persona for AU-15. */
  readonly requestedBy: string
  readonly requestedAt: string
  readonly waitingOn: string
  readonly allowSelfApproval: boolean
  /** What approving performs: the transition this task is the gate of.
   * The write happens through the one write path when decided. */
  readonly performs?: {
    readonly rowId: string
    readonly blueprintId: string
    readonly stateField: string
    readonly toState: string
  }
  /** For update requests: the fields the responder is asked to complete. */
  readonly asksFor?: readonly string[]
  readonly status: 'waiting' | 'approved' | 'rejected' | 'answered'
}

/** PM-7's classes, as the drawer renders them. A delta on a restricted field
 * arrives as `withheld: true` with no values — trimmed by the same Decision
 * that trims the grid, never by the client. */
export interface ActivityEntry {
  readonly id: string
  readonly cls: 'change' | 'governance' | 'access'
  readonly at: string
  /** Who acted, with channel (PM-9 attribution): "Maya K. · grid",
   * "recipe: High exposure approval · automation". */
  readonly actor: string
  readonly channel: 'grid' | 'form' | 'api' | 'import' | 'automation' | 'system'
  readonly summary: string
  readonly deltas?: readonly {
    readonly fieldLabel: string
    readonly before?: string
    readonly after?: string
    readonly withheld?: boolean
  }[]
}

/** BP-28: a locked base plus workspace additions. One-to-one fields render
 * as columns that feel native and disclose their home on inspection;
 * one-to-many collections render as child grids in the detail panel. */
export interface ExtensionDef {
  readonly owner: string
  readonly fields: readonly {
    readonly id: string
    readonly label: string
    readonly type: 'text' | 'select' | 'date'
    readonly options?: readonly { key: string; label: string }[]
  }[]
  readonly collections: readonly {
    readonly id: string
    readonly title: string
    readonly columns: readonly { readonly id: string; readonly label: string }[]
    readonly rows: readonly Readonly<Record<string, string>>[]
  }[]
}

/** BP-1a's per-view-type field maps, drafted. A view type is offered only
 * where its map is satisfiable; where it is not, the switcher names the
 * missing fields instead of rendering an empty view — the vision's honesty
 * caveat, enforced in the contract shape itself. */
export interface ViewMaps {
  readonly board?: { readonly laneField: string }
  readonly calendar?: { readonly dateField: string }
  readonly gantt?: { readonly startField: string; readonly endField: string }
}

/** One field of a drafted app (BP-16's typing wizard / AI-1's draft): the
 * subset of BP-3 a creator confronts at birth. */
export interface DraftField {
  readonly id: string
  readonly label: string
  readonly type: 'text' | 'number' | 'date' | 'select' | 'user' | 'corporate_reference'
  readonly required?: boolean
  readonly options?: readonly string[]
  /** Names the corporate dimension a reference binds (PRD 14) — the draft
   * says "this column KNOWS the supplier" rather than offering free text. */
  readonly binds?: string
}

/** An adoptable application template (AC-7): the Blueprint plus its working
 * parts, packaged as one act of adoption. The gallery is code-first
 * configuration; the four pilot registers are its first entries. */
export interface AppTemplate {
  readonly id: string
  readonly name: string
  readonly tagline: string
  readonly fields: readonly DraftField[]
  readonly states: readonly WorkflowState[]
  readonly starterRecipes: readonly string[]
  readonly hasChildCollections: readonly string[]
  /** BP-28: what a workspace typically extends this base with — shown so
   * adopting reads as "locked base + your additions", not "fork". */
  readonly extendsWith?: string
}

/** What the describe-it path returns: a reviewable draft, never a created
 * thing (AI-1: rendered for edit before creation). */
export interface AppDraft {
  readonly name: string
  readonly purpose: string
  readonly fields: readonly DraftField[]
  readonly states: readonly WorkflowState[]
  readonly starterRecipes: readonly string[]
  readonly fromTemplate?: string
}

/** Everything the spine knows about one register, as one object — the shape
 * a future `GET .../blueprints/{bp}/spine` (or the Blueprint itself, once
 * AU-10/FM-1 land in metadata) would return. */
export interface SpineDef {
  readonly blueprintId: string
  /** The app's one-line reason to exist, shown as the Overview hero. Drafts
   * a Blueprint `description` (BP-1); an app that cannot say what it is for
   * is a table with navigation. */
  readonly purpose: string
  /** What the main collection is CALLED in this app — "Risks", never
   * "Table". An app navigates entities; "table" is the grid talking. */
  readonly entityLabel: string
  /** Child collections surfaced as app pages of their own: the flat
   * cross-parent rendering (BP-8 — "all deliverables due this month,
   * regardless of agreement") that makes an app read as multiple tables
   * joined, not one table with chrome. Row content is derived per parent
   * by the fixture until children are served. */
  readonly childTables: readonly {
    readonly id: string
    readonly label: string
    readonly columns: readonly { readonly id: string; readonly label: string }[]
  }[]
  readonly workflow: WorkflowDef
  readonly forms: readonly FormDef[]
  readonly recipes: readonly RecipeDef[]
  readonly viewMaps?: ViewMaps
  readonly extension?: ExtensionDef
}
