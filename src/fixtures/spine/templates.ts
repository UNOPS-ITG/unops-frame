/**
 * The app gallery and the language drafter — the two ways an app is born.
 *
 * The gallery entries are the four pilot registers from
 * `specs/pilots/paper-catalog.md`, packaged as AC-7 application templates:
 * a locked base Blueprint plus its states, starter recipes and child
 * collections, adopted in one act. The drafter is AI-1's shape — describe
 * the work, get a reviewable draft, never an auto-created thing — served
 * here by keyword matching because the fixture's job is to let the owner
 * judge the *journey*; the model call behind it is the engine's job.
 */

import type { AppDraft, AppTemplate, DraftField, WorkflowState } from './contracts'

const TRIAGE_STATES: readonly WorkflowState[] = [
  { key: 'new', label: 'New', role: 'draft' },
  { key: 'active', label: 'Active', role: 'progress' },
  { key: 'done', label: 'Done', role: 'closed', terminal: true },
]

export const APP_TEMPLATES: readonly AppTemplate[] = [
  {
    id: 'contract-management',
    name: 'Contract management',
    tagline:
      'Contracts from the corporate warehouse — read-only where they should be — plus your performance and logistics tracking on top.',
    fields: [
      { id: 'contract', label: 'Contract', type: 'corporate_reference', required: true, binds: 'Contracts' },
      { id: 'manager', label: 'Contract manager', type: 'user', required: true },
      { id: 'performance', label: 'Performance', type: 'select', options: ['Good', 'Watch', 'Poor'] },
      { id: 'delivery_status', label: 'Delivery status', type: 'select', options: ['On track', 'Delayed', 'Blocked'] },
      { id: 'next_review', label: 'Next review', type: 'date' },
    ],
    states: [
      { key: 'active', label: 'Active', role: 'progress' },
      { key: 'review', label: 'Under review', role: 'warning' },
      { key: 'closed', label: 'Closed', role: 'closed', terminal: true },
    ],
    starterRecipes: [
      'When the contract end date is 60 days away, notify the manager',
      'When performance is set to Poor, open an issue and notify the supervisor',
      'Quarterly performance review reminder on active goods contracts',
    ],
    hasChildCollections: ['Deliveries'],
    extendsWith: 'goods-contract fields (locations, warehouse) shown only where the contract type needs them',
  },
  {
    id: 'asset-management',
    name: 'Asset management',
    tagline: 'Every asset from arrival to disposal: receipt, issue to users, condition, verification.',
    fields: [
      { id: 'asset_tag', label: 'Asset tag', type: 'text', required: true },
      { id: 'description', label: 'Description', type: 'text', required: true },
      { id: 'supplier', label: 'Supplier', type: 'corporate_reference', binds: 'Suppliers' },
      { id: 'custodian', label: 'Custodian', type: 'user' },
      { id: 'condition', label: 'Condition', type: 'select', options: ['Good', 'Fair', 'Damaged'] },
      { id: 'last_verified', label: 'Last verified', type: 'date' },
    ],
    states: [
      { key: 'in_transit', label: 'In transit', role: 'draft' },
      { key: 'in_storage', label: 'In storage', role: 'active' },
      { key: 'issued', label: 'Issued', role: 'progress' },
      { key: 'under_repair', label: 'Under repair', role: 'warning' },
      { key: 'disposed', label: 'Disposed', role: 'closed', terminal: true },
    ],
    starterRecipes: [
      'When an asset is not verified for 12 months, task the custodian',
      'When condition is set to Damaged, move to Under repair and open a repair log entry',
      'Disposal needs approval and generates the disposal certificate',
    ],
    hasChildCollections: ['Assignment history', 'Verification records'],
  },
  {
    id: 'project-management',
    name: 'Project management',
    tagline:
      'The project header and figures come from the warehouse; risks, issues, tasks and reporting live here.',
    fields: [
      { id: 'project', label: 'Project', type: 'corporate_reference', required: true, binds: 'Projects' },
      { id: 'manager', label: 'Project manager', type: 'user', required: true },
      { id: 'phase', label: 'Phase', type: 'select', options: ['Inception', 'Delivery', 'Closure'] },
      { id: 'next_report_due', label: 'Next report due', type: 'date' },
    ],
    states: TRIAGE_STATES,
    starterRecipes: [
      'When a high-severity risk is added, notify the project manager',
      'Monthly reporting task and meeting pack generation',
      'When expenditure crosses the budget threshold, alert the manager',
    ],
    hasChildCollections: ['Risk register', 'Issue register', 'Tasks', 'Reporting schedule'],
  },
  {
    id: 'fleet-management',
    name: 'Fleet management',
    tagline:
      'The asset template with vehicle fields and a maintenance log added on top — the base stays locked, your additions live beside it.',
    fields: [
      { id: 'plate', label: 'Plate', type: 'text', required: true },
      { id: 'model', label: 'Model', type: 'text' },
      { id: 'odometer', label: 'Odometer (km)', type: 'number' },
      { id: 'next_service_km', label: 'Next service (km)', type: 'number' },
      { id: 'insurance_expiry', label: 'Insurance expiry', type: 'date' },
    ],
    states: [
      { key: 'in_service', label: 'In service', role: 'active' },
      { key: 'maintenance', label: 'In maintenance', role: 'warning' },
      { key: 'retired', label: 'Retired', role: 'closed', terminal: true },
    ],
    starterRecipes: [
      'When the odometer passes the next service point, open a maintenance job',
      'On service completion, set the next service point from the current reading',
      'Insurance and registration renewal reminders',
    ],
    hasChildCollections: ['Maintenance log', 'Fuel log'],
    extendsWith: 'built as asset management + a workspace extension (BP-28): the asset base is adopted, not copied',
  },
]

/**
 * AI-1's describe-it path, fixture edition: a few recognisable shapes and
 * one honest generic. The engine behind this is a model call through the
 * estate gateway; the CONTRACT — text in, reviewable draft out, nothing
 * created until a person says so — is what this function drafts.
 */
export function draftFromDescription(text: string): AppDraft {
  const t = text.toLowerCase()

  // A template claims the draft only when the description IS that domain —
  // its noun among the opening words — never merely because the domain is
  // mentioned in passing ("…per project" is not a project-management app).
  const opening = t.split(/\s+/).slice(0, 4).join(' ')
  const template =
    APP_TEMPLATES.find((tpl) => opening.includes(tpl.id.split('-')[0]!)) ??
    (opening.includes('vehicle') || opening.includes('truck')
      ? APP_TEMPLATES[3]
      : opening.includes('supplier') || opening.includes('vendor')
        ? APP_TEMPLATES[0]
        : undefined)

  if (template !== undefined) {
    return {
      name: template.name,
      purpose: template.tagline,
      fields: template.fields,
      states: template.states,
      starterRecipes: template.starterRecipes,
      fromTemplate: template.id,
    }
  }

  // The generic tracker: what BP-16's typing wizard starts anyone with.
  const fields: DraftField[] = [
    { id: 'title', label: 'Title', type: 'text', required: true },
    { id: 'owner', label: 'Owner', type: 'user' },
    { id: 'due', label: 'Due', type: 'date' },
    { id: 'notes', label: 'Notes', type: 'text' },
  ]
  if (t.includes('amount') || t.includes('budget') || t.includes('cost')) {
    fields.splice(2, 0, { id: 'amount', label: 'Amount (USD)', type: 'number' })
  }
  if (t.includes('project')) {
    fields.splice(1, 0, { id: 'project', label: 'Project', type: 'corporate_reference', binds: 'Projects' })
  }
  return {
    name: titleFrom(text),
    purpose: text.trim(),
    fields,
    states: TRIAGE_STATES,
    starterRecipes: ['When the due date approaches, notify the owner'],
  }
}

function titleFrom(text: string): string {
  const words = text
    .replace(/[^\p{L}\p{N} ]/gu, '')
    .split(/\s+/)
    .filter((w) => w.length > 2)
    .slice(0, 3)
  if (words.length === 0) return 'New tracker'
  return words
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : w.toLowerCase()))
    .join(' ')
}
