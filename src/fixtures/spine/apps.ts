/**
 * The pilot apps' spines: contract, asset, project and fleet management —
 * the four registers of `specs/pilots/paper-catalog.md`, each carried as a
 * full application definition so the workspace reads as a PORTFOLIO of
 * apps, not one demo and a gallery.
 *
 * Parent rows for all four are genuinely seeded into the emulator
 * (`scripts/seed-dev-register.mjs`) with their own permission rules, so
 * counts, trims and sorts are real server answers everywhere. Child rows
 * derive deterministically per parent from the parent's own values — the
 * same recipe as the risk app — until BP-5/FM-3 serve them.
 *
 * Project management is the flagship composition: three child tables
 * (risks, issues, tasks), because "an app is multiple tables joined" is
 * the claim these fixtures exist to make tangible.
 */

import type { ChildRow, SpineDef, WorkflowState } from './contracts'

/** Stable per-row seed so derived children never reshuffle. */
function seedOf(rowId: string): number {
  return [...rowId].reduce((n, ch) => (n * 31 + ch.charCodeAt(0)) % 997, 7)
}

function str(values: Readonly<Record<string, unknown>>, key: string, fallback: string): string {
  const v = values[key]
  return typeof v === 'string' && v !== '' ? v : fallback
}

function dateLabel(values: Readonly<Record<string, unknown>>, key: string): string {
  const v = values[key]
  if (typeof v !== 'string' || v === '') return ''
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString()
}

const DONE: WorkflowState['role'] = 'closed'
const RUN: WorkflowState['role'] = 'progress'
const PLAN: WorkflowState['role'] = 'draft'

function chip(state: 'Planned' | 'In progress' | 'Done'): Pick<ChildRow, 'stateLabel' | 'stateRole'> {
  return {
    stateLabel: state,
    stateRole: state === 'Done' ? DONE : state === 'In progress' ? RUN : PLAN,
  }
}

/* --- contract management -------------------------------------------------- */

export const CONTRACT_SPINE: SpineDef = {
  blueprintId: 'contracts',
  purpose:
    'Contracts from the corporate warehouse, with your performance and delivery tracking living on top — read-only where it should be.',
  entityLabel: 'Contracts',
  childTables: [
    {
      id: 'deliveries',
      label: 'Deliveries',
      columns: [
        { id: 'item', label: 'Item' },
        { id: 'due', label: 'Due' },
        { id: 'qty', label: 'Quantity' },
        { id: 'state', label: 'State' },
      ],
    },
  ],
  overview: {
    staleField: 'end',
    staleTitle: 'Ending soonest',
    bigField: 'contract_value',
    bigTitle: 'Largest value',
  },
  card: { metaField: 'manager', valueField: 'contract_value' },
  activity: { recipe: 'Poor performance escalation', restrictedLabel: 'Negotiation notes' },
  workflow: {
    stateField: 'status',
    states: [
      { key: 'active', label: 'Active', role: 'progress' },
      { key: 'review', label: 'Under review', role: 'warning' },
      { key: 'closed', label: 'Closed', role: 'closed', terminal: true },
    ],
    transitions: [
      { id: 'start-review', from: 'active', to: 'review', label: 'Start performance review' },
      { id: 'return', from: 'review', to: 'active', label: 'Return to active' },
      {
        id: 'close',
        from: 'review',
        to: 'closed',
        label: 'Close contract',
        gate: { approvers: 'Contracts committee', allowSelfApproval: false },
      },
    ],
  },
  viewMaps: {
    board: { laneField: 'status' },
    calendar: { dateField: 'end' },
    gantt: { startField: 'start', endField: 'end' },
  },
  forms: [
    {
      id: 'register-contract',
      name: 'Register a contract',
      verb: 'Register this contract',
      intro:
        'What you register lands as a governed record — manager, clock and review gates attached — not as a folder on a drive.',
      sections: [
        {
          title: 'The contract',
          fields: [
            { fieldId: 'title', required: true },
            { fieldId: 'manager', required: true },
            { fieldId: 'supplier' },
            { fieldId: 'contract_value', helpText: 'Total value in USD.' },
          ],
        },
        {
          title: 'Term',
          fields: [{ fieldId: 'start' }, { fieldId: 'end' }],
        },
      ],
      childSection: {
        collectionId: 'deliveries',
        title: 'Deliveries',
        hint: 'Line items travel with the contract — one transaction, not attachments.',
        addLabel: 'Add another delivery',
        columns: [
          { id: 'item', label: 'Item', type: 'text', required: true },
          { id: 'due', label: 'Due', type: 'date' },
          { id: 'qty', label: 'Quantity', type: 'number' },
        ],
      },
      landing: { stateKey: 'active', explains: 'Lands as Active, with the manager assigned.' },
    },
  ],
  recipes: [
    {
      id: 'con-ending',
      title: 'End-of-term alert',
      trigger: 'date-field approaching',
      sentence: [
        'When ',
        { kind: 'field', value: 'End' },
        ' is ',
        { kind: 'value', value: '60 days' },
        ' away, notify ',
        { kind: 'principal', value: 'Contract manager' },
        '.',
      ],
      enabled: true,
      runs30d: 9,
      lastRun: '2026-08-01T06:00:00Z',
    },
    {
      id: 'con-poor',
      title: 'Poor performance escalation',
      trigger: 'row updated',
      sentence: [
        'When ',
        { kind: 'field', value: 'Performance' },
        ' is set to ',
        { kind: 'value', value: 'Poor' },
        ', open an issue and notify ',
        { kind: 'principal', value: 'Supervisor' },
        '.',
      ],
      enabled: true,
      runs30d: 2,
      lastRun: '2026-07-22T10:02:00Z',
    },
    {
      id: 'con-quarterly',
      title: 'Quarterly review cadence',
      trigger: 'scheduled',
      sentence: [
        'Every quarter, on active goods contracts, create the review task and notify ',
        { kind: 'principal', value: 'Contract manager' },
        '.',
      ],
      enabled: true,
      runs30d: 31,
      lastRun: '2026-08-02T06:00:00Z',
    },
  ],
  extension: {
    owner: 'Logistics workspace',
    fields: [
      { id: 'x_warehouse', label: 'Warehouse', type: 'text' },
      { id: 'x_incoterm', label: 'Incoterm', type: 'text' },
    ],
    collections: [
      {
        id: 'x_amendments',
        title: 'Amendment log',
        columns: [
          { id: 'amendment', label: 'Amendment' },
          { id: 'by', label: 'By' },
          { id: 'on', label: 'On' },
        ],
        rows: [
          { amendment: 'Delivery schedule extended one quarter', by: 'Contracts committee', on: '2026-06-20' },
        ],
      },
    ],
  },
}

const DELIVERY_ITEMS = [
  'Generator sets, 50kVA',
  'Prefab office units',
  'Solar panel arrays',
  'Water treatment kits',
  'Cold-chain refrigerators',
]

function contractChildren(rowId: string, values: Readonly<Record<string, unknown>>): ChildRow[] {
  const seed = seedOf(rowId)
  const due = dateLabel(values, 'end')
  const closed = values['status'] === 'closed'
  return Array.from({ length: 2 + (seed % 2) }, (_, i) => ({
    values: {
      item: DELIVERY_ITEMS[(seed + i) % DELIVERY_ITEMS.length]!,
      due,
      qty: String(5 + ((seed * (i + 3)) % 40)),
    },
    ...chip(closed ? 'Done' : i === 0 ? 'In progress' : 'Planned'),
  }))
}

/* --- asset management ----------------------------------------------------- */

export const ASSET_SPINE: SpineDef = {
  blueprintId: 'assets',
  purpose:
    'Every asset from arrival to disposal — receipt, issue, condition and verification — with the audit trail attached to the asset, not to a spreadsheet tab.',
  entityLabel: 'Assets',
  childTables: [
    {
      id: 'assignments',
      label: 'Assignment history',
      columns: [
        { id: 'holder', label: 'Held by' },
        { id: 'from', label: 'From' },
        { id: 'to', label: 'To' },
        { id: 'state', label: 'State' },
      ],
    },
    {
      id: 'verifications',
      label: 'Verifications',
      columns: [
        { id: 'on', label: 'On' },
        { id: 'by', label: 'By' },
        { id: 'result', label: 'Result' },
        { id: 'state', label: 'State' },
      ],
    },
  ],
  overview: {
    staleField: 'last_verified',
    staleTitle: 'Longest unverified',
    bigField: 'value_usd',
    bigTitle: 'Highest value',
  },
  card: { metaField: 'custodian', valueField: 'value_usd' },
  activity: { recipe: 'Damage routing', restrictedLabel: 'Disposal justification' },
  workflow: {
    stateField: 'status',
    states: [
      { key: 'in_transit', label: 'In transit', role: 'draft' },
      { key: 'in_storage', label: 'In storage', role: 'active' },
      { key: 'issued', label: 'Issued', role: 'progress' },
      { key: 'under_repair', label: 'Under repair', role: 'warning' },
      { key: 'disposed', label: 'Disposed', role: 'closed', terminal: true },
    ],
    transitions: [
      { id: 'receive', from: 'in_transit', to: 'in_storage', label: 'Receive into storage' },
      { id: 'issue', from: 'in_storage', to: 'issued', label: 'Issue to custodian' },
      { id: 'repair', from: 'issued', to: 'under_repair', label: 'Send for repair' },
      { id: 'return', from: 'under_repair', to: 'issued', label: 'Return to custodian' },
      {
        id: 'dispose',
        from: 'in_storage',
        to: 'disposed',
        label: 'Dispose',
        gate: { approvers: 'Asset board', allowSelfApproval: false },
      },
    ],
  },
  // No Gantt map, deliberately: an asset has no start/end pair, and the
  // switcher's honest gate ("this app declares no date pair") is itself a
  // behaviour worth demonstrating.
  viewMaps: {
    board: { laneField: 'status' },
    calendar: { dateField: 'last_verified' },
  },
  forms: [
    {
      id: 'receive-assets',
      name: 'Receive assets',
      verb: 'Record the receipt',
      intro: 'A receipt lands each asset as a governed record with a tag, a state and a custodian trail.',
      sections: [
        {
          title: 'The asset',
          fields: [
            { fieldId: 'asset_tag', required: true, helpText: 'The physical tag, e.g. UN-AST-0117.' },
            { fieldId: 'description', required: true },
            { fieldId: 'value_usd' },
          ],
        },
        { title: 'Placement', fields: [{ fieldId: 'custodian' }, { fieldId: 'last_verified' }] },
      ],
      landing: { stateKey: 'in_storage', explains: 'Lands In storage, awaiting issue.' },
    },
  ],
  recipes: [
    {
      id: 'ast-verify',
      title: 'Annual verification',
      trigger: 'date-field reached',
      sentence: [
        'When ',
        { kind: 'field', value: 'Last verified' },
        ' is ',
        { kind: 'value', value: '12 months' },
        ' past, task ',
        { kind: 'principal', value: 'Custodian' },
        ' to verify.',
      ],
      enabled: true,
      runs30d: 23,
      lastRun: '2026-08-02T06:00:00Z',
    },
    {
      id: 'ast-damaged',
      title: 'Damage routing',
      trigger: 'row updated',
      sentence: [
        'When ',
        { kind: 'field', value: 'Condition' },
        ' becomes ',
        { kind: 'value', value: 'Damaged' },
        ', set ',
        { kind: 'field', value: 'Status' },
        ' to ',
        { kind: 'state', value: 'Under repair' },
        ' and open a repair job.',
      ],
      enabled: true,
      runs30d: 4,
      lastRun: '2026-07-30T09:15:00Z',
    },
    {
      id: 'ast-dispose',
      title: 'Disposal certificate',
      trigger: 'state changed',
      sentence: [
        'When ',
        { kind: 'field', value: 'Status' },
        ' becomes ',
        { kind: 'state', value: 'Disposed' },
        ', generate the disposal certificate and file it on the record.',
      ],
      enabled: false,
      runs30d: 0,
      lastRun: null,
    },
  ],
}

const HOLDERS = ['J. Mwangi', 'P. Silva', 'A. Rahman', 'C. Dubois', 'S. Petrov']

function assetChildren(
  tableId: string,
  rowId: string,
  values: Readonly<Record<string, unknown>>,
): ChildRow[] {
  const seed = seedOf(rowId)
  const custodian = str(values, 'custodian', HOLDERS[seed % HOLDERS.length]!)
  if (tableId === 'assignments') {
    return [
      {
        values: { holder: custodian, from: '2026-03-12', to: '' },
        ...chip('In progress'),
      },
      {
        values: { holder: HOLDERS[(seed + 1) % HOLDERS.length]!, from: '2025-06-01', to: '2026-03-12' },
        ...chip('Done'),
      },
    ]
  }
  const verified = dateLabel(values, 'last_verified')
  return [
    {
      values: { on: verified, by: custodian, result: str(values, 'condition', 'good') },
      ...chip('Done'),
    },
    {
      values: { on: '2025-07-15', by: HOLDERS[(seed + 2) % HOLDERS.length]!, result: 'good' },
      ...chip('Done'),
    },
  ]
}

/* --- project management (the flagship composition) ------------------------ */

export const PROJECT_SPINE: SpineDef = {
  blueprintId: 'projects',
  purpose:
    'The project header and figures come from the warehouse; the risks, issues, tasks and reporting that RUN the project live here, joined to it.',
  entityLabel: 'Projects',
  childTables: [
    {
      id: 'prisks',
      label: 'Risk register',
      columns: [
        { id: 'risk', label: 'Risk' },
        { id: 'severity', label: 'Severity' },
        { id: 'owner', label: 'Owner' },
        { id: 'state', label: 'State' },
      ],
    },
    {
      id: 'pissues',
      label: 'Issues',
      columns: [
        { id: 'issue', label: 'Issue' },
        { id: 'raised', label: 'Raised' },
        { id: 'owner', label: 'Owner' },
        { id: 'state', label: 'State' },
      ],
    },
    {
      id: 'ptasks',
      label: 'Tasks',
      columns: [
        { id: 'task', label: 'Task' },
        { id: 'due', label: 'Due' },
        { id: 'assignee', label: 'Assignee' },
        { id: 'state', label: 'State' },
      ],
    },
  ],
  overview: {
    staleField: 'end',
    staleTitle: 'Ending soonest',
    bigField: 'budget_usd',
    bigTitle: 'Largest budget',
  },
  card: { metaField: 'manager', valueField: 'budget_usd' },
  activity: { recipe: 'High-severity risk alert', restrictedLabel: 'Board commentary' },
  workflow: {
    stateField: 'status',
    states: [
      { key: 'inception', label: 'Inception', role: 'draft' },
      { key: 'delivery', label: 'Delivery', role: 'progress' },
      { key: 'closure', label: 'Closure', role: 'closed', terminal: true },
    ],
    transitions: [
      {
        id: 'approve-start',
        from: 'inception',
        to: 'delivery',
        label: 'Approve start',
        gate: { approvers: 'Portfolio board', allowSelfApproval: false },
      },
      { id: 'begin-closure', from: 'delivery', to: 'closure', label: 'Begin closure' },
    ],
  },
  viewMaps: {
    board: { laneField: 'status' },
    calendar: { dateField: 'end' },
    gantt: { startField: 'start', endField: 'end' },
  },
  forms: [
    {
      id: 'open-project',
      name: 'Open a project',
      verb: 'Open this project',
      intro:
        'A project opens as a governed room: its header knows the real project register, and its risks, issues and tasks live joined to it from day one.',
      sections: [
        {
          title: 'The project',
          fields: [
            { fieldId: 'title', required: true },
            { fieldId: 'manager', required: true },
            { fieldId: 'country' },
            { fieldId: 'budget_usd' },
          ],
        },
        { title: 'Timeline', fields: [{ fieldId: 'start' }, { fieldId: 'end' }] },
      ],
      childSection: {
        collectionId: 'prisks',
        title: 'Known risks at opening',
        hint: 'The risk register starts populated, not blank.',
        addLabel: 'Add another risk',
        columns: [
          { id: 'risk', label: 'Risk', type: 'text', required: true },
          { id: 'severity', label: 'Severity', type: 'text' },
          { id: 'owner', label: 'Owner', type: 'text' },
        ],
      },
      landing: { stateKey: 'inception', explains: 'Lands in Inception, awaiting board approval.' },
    },
  ],
  recipes: [
    {
      id: 'prj-highrisk',
      title: 'High-severity risk alert',
      trigger: 'row created',
      sentence: [
        'When a risk with severity ',
        { kind: 'value', value: 'High' },
        ' is added, notify ',
        { kind: 'principal', value: 'Project manager' },
        ' and require mitigation fields.',
      ],
      enabled: true,
      runs30d: 6,
      lastRun: '2026-07-29T11:41:00Z',
    },
    {
      id: 'prj-report',
      title: 'Monthly reporting pack',
      trigger: 'scheduled',
      sentence: [
        'Every month, create the reporting task and generate the meeting pack from the project record.',
      ],
      enabled: true,
      runs30d: 48,
      lastRun: '2026-08-01T05:00:00Z',
    },
    {
      id: 'prj-budget',
      title: 'Budget threshold alert',
      trigger: 'scheduled',
      sentence: [
        'When ',
        { kind: 'field', value: 'Spent (USD)' },
        ' exceeds ',
        { kind: 'expression', value: 'budget_usd * 0.9' },
        ', alert ',
        { kind: 'principal', value: 'Project manager' },
        '.',
      ],
      enabled: true,
      runs30d: 1,
      lastRun: '2026-07-18T06:00:00Z',
    },
  ],
}

const PRISK_TEXTS = [
  'Rainy season delays site access',
  'Fuel price escalation beyond contingency',
  'Community consultation slips the schedule',
  'Customs clearance exceeds 30 days',
  'Contractor capacity below committed level',
]
const PISSUE_TEXTS = [
  'Access road washed out at km 14',
  'Generator delivery held at port',
  'Survey data gap on northern parcel',
  'Local permit renewal pending',
]
const PTASK_TEXTS = [
  'Submit quarterly donor report',
  'Complete environmental screening',
  'Handover training for site team',
  'Update procurement plan',
  'Site safety audit',
]

function projectChildren(
  tableId: string,
  rowId: string,
  values: Readonly<Record<string, unknown>>,
): ChildRow[] {
  const seed = seedOf(rowId)
  const manager = str(values, 'manager', 'L. Fernández')
  const end = dateLabel(values, 'end')
  if (tableId === 'prisks') {
    return Array.from({ length: 2 + (seed % 2) }, (_, i) => ({
      values: {
        risk: PRISK_TEXTS[(seed + i) % PRISK_TEXTS.length]!,
        severity: (seed + i) % 3 === 0 ? 'High' : (seed + i) % 3 === 1 ? 'Medium' : 'Low',
        owner: manager,
      },
      ...chip(i === 0 ? 'In progress' : 'Planned'),
    }))
  }
  if (tableId === 'pissues') {
    return Array.from({ length: 1 + (seed % 2) }, (_, i) => ({
      values: {
        issue: PISSUE_TEXTS[(seed + i) % PISSUE_TEXTS.length]!,
        raised: '2026-07-0' + (1 + ((seed + i) % 9)),
        owner: manager,
      },
      ...chip(i === 0 ? 'In progress' : 'Done'),
    }))
  }
  return Array.from({ length: 3 }, (_, i) => ({
    values: {
      task: PTASK_TEXTS[(seed + i) % PTASK_TEXTS.length]!,
      due: end,
      assignee: manager,
    },
    ...chip(i === 0 ? 'In progress' : i === 1 ? 'Planned' : 'Done'),
  }))
}

/* --- fleet management ----------------------------------------------------- */

export const FLEET_SPINE: SpineDef = {
  blueprintId: 'fleet',
  purpose:
    'The asset app with vehicle fields and a maintenance log added beside the locked base — service by date or odometer, insurance on a clock.',
  entityLabel: 'Vehicles',
  childTables: [
    {
      id: 'maintenance',
      label: 'Maintenance log',
      columns: [
        { id: 'job', label: 'Job' },
        { id: 'on', label: 'On' },
        { id: 'cost', label: 'Cost (USD)' },
        { id: 'state', label: 'State' },
      ],
    },
    {
      id: 'fuel',
      label: 'Fuel log',
      columns: [
        { id: 'on', label: 'On' },
        { id: 'litres', label: 'Litres' },
        { id: 'odometer', label: 'Odometer' },
        { id: 'state', label: 'State' },
      ],
    },
  ],
  overview: {
    staleField: 'insurance_expiry',
    staleTitle: 'Insurance expiring',
    bigField: 'odometer',
    bigTitle: 'Highest odometer',
  },
  card: { metaField: 'model', valueField: 'odometer' },
  activity: { recipe: 'Service by odometer', restrictedLabel: null },
  workflow: {
    stateField: 'status',
    states: [
      { key: 'in_service', label: 'In service', role: 'active' },
      { key: 'maintenance', label: 'In maintenance', role: 'warning' },
      { key: 'retired', label: 'Retired', role: 'closed', terminal: true },
    ],
    transitions: [
      { id: 'to-shop', from: 'in_service', to: 'maintenance', label: 'Send to maintenance' },
      { id: 'back', from: 'maintenance', to: 'in_service', label: 'Return to service' },
      {
        id: 'retire',
        from: 'maintenance',
        to: 'retired',
        label: 'Retire vehicle',
        gate: { approvers: 'Fleet board', allowSelfApproval: false },
      },
    ],
  },
  viewMaps: {
    board: { laneField: 'status' },
    calendar: { dateField: 'insurance_expiry' },
  },
  forms: [
    {
      id: 'accident-report',
      name: 'Report an incident',
      verb: 'Report this incident',
      intro: 'An incident lands against the vehicle with a state and a clock — never as an email thread.',
      sections: [
        {
          title: 'The incident',
          fields: [
            { fieldId: 'plate', required: true, helpText: 'The vehicle involved.' },
            { fieldId: 'driver', required: true },
            { fieldId: 'odometer' },
          ],
        },
      ],
      landing: { stateKey: 'maintenance', explains: 'The vehicle moves to In maintenance pending inspection.' },
    },
  ],
  recipes: [
    {
      id: 'flt-service-km',
      title: 'Service by odometer',
      trigger: 'row updated',
      sentence: [
        'When ',
        { kind: 'field', value: 'Odometer' },
        ' passes ',
        { kind: 'field', value: 'Next service (km)' },
        ', open a maintenance job and notify ',
        { kind: 'principal', value: 'Fleet officer' },
        '.',
      ],
      enabled: true,
      runs30d: 7,
      lastRun: '2026-08-01T14:20:00Z',
    },
    {
      id: 'flt-next',
      title: 'Schedule the next service',
      trigger: 'state changed',
      sentence: [
        'When ',
        { kind: 'field', value: 'Status' },
        ' returns to ',
        { kind: 'state', value: 'In service' },
        ', set ',
        { kind: 'field', value: 'Next service (km)' },
        ' to ',
        { kind: 'expression', value: 'odometer + 10000' },
        '.',
      ],
      enabled: true,
      runs30d: 5,
      lastRun: '2026-07-28T16:05:00Z',
    },
    {
      id: 'flt-insurance',
      title: 'Insurance renewal',
      trigger: 'date-field approaching',
      sentence: [
        'When ',
        { kind: 'field', value: 'Insurance expiry' },
        ' is ',
        { kind: 'value', value: '30 days' },
        ' away, notify ',
        { kind: 'principal', value: 'Fleet officer' },
        '.',
      ],
      enabled: true,
      runs30d: 3,
      lastRun: '2026-07-31T06:00:00Z',
    },
  ],
}

const JOBS = ['10,000 km service', 'Brake pad replacement', 'Tyre rotation', 'Suspension check', 'AC compressor repair']

function fleetChildren(
  tableId: string,
  rowId: string,
  values: Readonly<Record<string, unknown>>,
): ChildRow[] {
  const seed = seedOf(rowId)
  const rawOdo = values['odometer']
  const odo = typeof rawOdo === 'number' ? rawOdo : 60000
  if (tableId === 'maintenance') {
    return Array.from({ length: 2 }, (_, i) => ({
      values: {
        job: JOBS[(seed + i) % JOBS.length]!,
        on: i === 0 ? '2026-07-1' + (seed % 9) : '2026-03-0' + (1 + (seed % 9)),
        cost: String(180 + ((seed * (i + 2)) % 900)),
      },
      ...chip(i === 0 && values['status'] === 'maintenance' ? 'In progress' : 'Done'),
    }))
  }
  return Array.from({ length: 3 }, (_, i) => ({
    values: {
      on: `2026-07-${String(3 + i * 9 + (seed % 3)).padStart(2, '0')}`,
      litres: String(35 + ((seed + i * 7) % 40)),
      odometer: String(odo - (2 - i) * 900),
    },
    ...chip('Done'),
  }))
}

/* --- registry -------------------------------------------------------------- */

export const PILOT_SPINES: readonly SpineDef[] = [
  CONTRACT_SPINE,
  ASSET_SPINE,
  PROJECT_SPINE,
  FLEET_SPINE,
]

/** Child rows for any pilot app's child table. The risk app keeps its own
 * derivation in `risk.ts`; the store routes there. */
export function pilotChildren(
  blueprintId: string,
  tableId: string,
  rowId: string,
  values: Readonly<Record<string, unknown>>,
): ChildRow[] {
  switch (blueprintId) {
    case 'contracts':
      return contractChildren(rowId, values)
    case 'assets':
      return assetChildren(tableId, rowId, values)
    case 'projects':
      return projectChildren(tableId, rowId, values)
    case 'fleet':
      return fleetChildren(tableId, rowId, values)
    default:
      return []
  }
}
