/**
 * The demo risk register's spine, hard-coded.
 *
 * This is the fixture the vision-verification checkpoint runs on
 * (`specs/pilots/vision-walkthrough.md`). The *shapes* are the draft API
 * contract (`contracts.ts`); the *content* is chosen to exercise every
 * treatment the paper catalog said the pilots need: a gated transition with
 * no self-approval, a recipe with an AU-16 expression parameter, a withheld
 * delta, an automation-attributed change, and a BP-28 extension.
 *
 * Everything binds to the seeded `risk` Blueprint's real fields (title,
 * status, owner, exposure, reviewed, rationale) so the surfaces read as one
 * product, not a demo bolted beside one.
 */

import type { ActivityEntry, PendingTask, SpineDef } from './contracts'

export const RISK_SPINE: SpineDef = {
  blueprintId: 'risk',

  purpose:
    'Track, mitigate and close operational risks — with intake, review gates and an audit trail built in, not bolted on.',

  entityLabel: 'Risks',

  childTables: [
    {
      id: 'mitigations',
      label: 'Mitigation actions',
      columns: [
        { id: 'action', label: 'Action' },
        { id: 'due', label: 'Due' },
        { id: 'assignee', label: 'Assignee' },
        { id: 'state', label: 'State' },
      ],
    },
  ],

  workflow: {
    stateField: 'status',
    states: [
      { key: 'open', label: 'Open', role: 'danger' },
      { key: 'mitigating', label: 'Mitigating', role: 'progress' },
      { key: 'closed', label: 'Closed', role: 'closed', terminal: true },
    ],
    transitions: [
      {
        id: 'start-mitigation',
        from: 'open',
        to: 'mitigating',
        label: 'Start mitigation',
      },
      {
        id: 'reopen',
        from: 'mitigating',
        to: 'open',
        label: 'Reopen',
      },
      {
        id: 'close',
        from: 'mitigating',
        to: 'closed',
        label: 'Close risk',
        gate: { approvers: 'Risk team', allowSelfApproval: false },
      },
      {
        id: 'close-direct',
        from: 'open',
        to: 'closed',
        label: 'Close without mitigation',
        gate: { approvers: 'Risk team', allowSelfApproval: false },
        condition: {
          expression: 'exposure < 1000000',
          explains: 'Only risks under $1M exposure may close without a mitigation phase.',
        },
      },
    ],
  },

  viewMaps: {
    board: { laneField: 'status' },
    calendar: { dateField: 'reviewed' },
    gantt: { startField: 'mitigation_start', endField: 'mitigation_due' },
  },

  forms: [
    {
      id: 'report-a-risk',
      name: 'Report a risk',
      verb: 'Report this risk',
      intro:
        'What you report lands in the app as a governed row — with a state, an owner and a clock — not as an email.',
      sections: [
        {
          title: 'The risk',
          fields: [
            {
              fieldId: 'title',
              required: true,
              helpText: 'One sentence, the way you would say it to a colleague.',
            },
            { fieldId: 'owner', required: true },
            {
              fieldId: 'exposure',
              helpText: 'Best estimate in USD. Above $5M the register gates who sees it.',
            },
          ],
        },
        {
          title: 'Context',
          hint: 'Optional, but the review lands faster with it.',
          fields: [{ fieldId: 'reviewed' }, { fieldId: 'agency' }],
        },
      ],
      childSection: {
        collectionId: 'mitigations',
        title: 'Mitigation actions',
        hint: 'Line items travel with the risk — added, approved and audited together (one transaction, not attachments).',
        addLabel: 'Add another action',
        columns: [
          { id: 'action', label: 'Action', type: 'text', required: true },
          { id: 'due', label: 'Due', type: 'date' },
          { id: 'assignee', label: 'Assignee', type: 'text' },
        ],
      },
      landing: {
        stateKey: 'open',
        explains: 'Lands as Open, assigned for triage. You get the reference number on submit.',
      },
    },
  ],

  recipes: [
    {
      id: 'stale-review',
      title: 'Stale review reminder',
      trigger: 'date-field reached',
      sentence: [
        'When ',
        { kind: 'field', value: 'Last reviewed' },
        ' is ',
        { kind: 'value', value: '90 days' },
        ' past, notify ',
        { kind: 'principal', value: 'Owner' },
        ' and flag the row for review.',
      ],
      enabled: true,
      runs30d: 41,
      lastRun: '2026-08-01T06:00:00Z',
    },
    {
      id: 'high-exposure',
      title: 'High exposure approval',
      trigger: 'row updated',
      sentence: [
        'When ',
        { kind: 'field', value: 'Exposure (USD)' },
        ' exceeds ',
        { kind: 'value', value: '$5,000,000' },
        ', request approval from ',
        { kind: 'principal', value: 'Risk team' },
        ' and set ',
        { kind: 'field', value: 'Status' },
        ' to ',
        { kind: 'state', value: 'Mitigating' },
        '.',
      ],
      enabled: true,
      runs30d: 3,
      lastRun: '2026-07-28T14:12:00Z',
    },
    {
      id: 'intake-routing',
      title: 'Intake routing',
      trigger: 'form submitted',
      sentence: [
        'When a row arrives from ',
        { kind: 'form', value: 'Report a risk' },
        ', assign ',
        { kind: 'principal', value: 'Owner' },
        ' and notify ',
        { kind: 'principal', value: 'Risk team' },
        ' in Chat.',
      ],
      enabled: true,
      runs30d: 12,
      lastRun: '2026-08-02T09:41:00Z',
    },
    {
      id: 'next-review',
      title: 'Schedule the next review',
      trigger: 'state changed',
      sentence: [
        'When ',
        { kind: 'field', value: 'Status' },
        ' becomes ',
        { kind: 'state', value: 'Mitigating' },
        ', set ',
        { kind: 'field', value: 'Last reviewed' },
        ' to ',
        { kind: 'expression', value: 'today()' },
        ' and the next review to ',
        { kind: 'expression', value: 'today() + 180d' },
        '.',
      ],
      enabled: false,
      runs30d: 0,
      lastRun: null,
    },
    {
      id: 'tpl-escalate',
      title: 'Escalate the unactioned',
      trigger: 'date-field reached',
      sentence: [
        'When a row sits in ',
        { kind: 'state', value: 'Open' },
        ' for ',
        { kind: 'value', value: '14 days' },
        ', notify ',
        { kind: 'principal', value: 'Head of unit' },
        '.',
      ],
      enabled: false,
      runs30d: 0,
      lastRun: null,
      template: true,
    },
    {
      id: 'tpl-closure-note',
      title: 'Closure letter',
      trigger: 'state changed',
      sentence: [
        'When ',
        { kind: 'field', value: 'Status' },
        ' becomes ',
        { kind: 'state', value: 'Closed' },
        ', generate the ',
        { kind: 'form', value: 'Risk closure note' },
        ' and file it on the row.',
      ],
      enabled: false,
      runs30d: 0,
      lastRun: null,
      template: true,
    },
  ],

  extension: {
    owner: 'PMO workspace',
    fields: [
      {
        id: 'x_board_attention',
        label: 'Board attention',
        type: 'select',
        options: [
          { key: 'none', label: 'Not raised' },
          { key: 'watch', label: 'Watchlist' },
          { key: 'raised', label: 'Raised to board' },
        ],
      },
      { id: 'x_review_cadence', label: 'Review cadence', type: 'text' },
    ],
    collections: [
      {
        id: 'x_decisions',
        title: 'Decision log',
        columns: [
          { id: 'decision', label: 'Decision' },
          { id: 'by', label: 'By' },
          { id: 'on', label: 'On' },
        ],
        rows: [
          { decision: 'Accepted with quarterly review', by: 'Steering committee', on: '2026-06-12' },
          { decision: 'Mitigation budget approved', by: 'K. Mensah', on: '2026-07-03' },
        ],
      },
    ],
  },
}

/** The inbox's opening state: one approval raised by the OTHER persona, so
 * whichever identity is active can exercise a real decision — and one update
 * request, so both classes of the single pending-task record render. */
export const SEED_TASKS: readonly PendingTask[] = [
  {
    id: 'task-close-approval',
    kind: 'approval',
    title: 'Close risk',
    detail:
      'Mitigation complete; residual exposure assessed as tolerable. Closing ends the review cycle.',
    requestedBy: 'dev@unops.org',
    requestedAt: '2026-08-02T08:05:00Z',
    waitingOn: 'Risk team',
    allowSelfApproval: false,
    status: 'waiting',
  },
  {
    id: 'task-complete-fields',
    kind: 'update',
    title: 'Complete the exposure estimate',
    detail: 'Requested so the high-exposure gate can evaluate this row.',
    requestedBy: 'risk@unops.org',
    requestedAt: '2026-08-01T15:30:00Z',
    waitingOn: 'dev@unops.org',
    allowSelfApproval: true,
    asksFor: ['Exposure (USD)', 'Last reviewed'],
    status: 'waiting',
  },
]

/**
 * The mitigation actions "under" a real risk row, derived deterministically
 * from the row's own values — owner, status, mitigation window — so all 500
 * seeded parents read believably and the same parent always shows the same
 * children. Dies when FM-3/BP-5 children are served for real.
 */
export interface FixtureChildRow {
  readonly action: string
  readonly due: string
  readonly assignee: string
  readonly state: 'Planned' | 'In progress' | 'Done'
}

const ACTION_VERBS = [
  'Renegotiate the coverage clause with',
  'Run the contingency drill owned by',
  'Split the exposure across suppliers with',
  'Update the escalation protocol with',
  'Commission the independent review via',
]

export function mitigationsFor(
  rowId: string,
  rowValues: Readonly<Record<string, unknown>>,
): FixtureChildRow[] {
  const rawOwner = rowValues['owner']
  const owner = typeof rawOwner === 'string' ? rawOwner : 'M. Okafor'
  const status = rowValues['status']
  const rawDue = rowValues['mitigation_due']
  const due = typeof rawDue === 'string' ? rawDue : ''
  const dueLabel = due === '' ? '' : new Date(due).toLocaleDateString()
  // A stable per-row seed from the id, so the list never reshuffles.
  const seed = [...rowId].reduce((n, ch) => (n * 31 + ch.charCodeAt(0)) % 997, 7)
  const count = status === 'closed' ? 2 : 1 + (seed % 2)
  return Array.from({ length: count }, (_, i) => {
    const verb = ACTION_VERBS[(seed + i) % ACTION_VERBS.length]!
    return {
      action: `${verb} ${owner}`,
      due: dueLabel,
      assignee: owner,
      state: status === 'closed' ? 'Done' : i === 0 ? 'In progress' : 'Planned',
    }
  })
}

/**
 * Scripted history behind whichever row the drawer opens on.
 *
 * Templated from the row's real values so all 500 seeded rows read
 * believably; the withheld delta and the automation attribution are fixed,
 * because those two treatments are what the drawer exists to show.
 */
export function activityFor(rowValues: Readonly<Record<string, unknown>>): ActivityEntry[] {
  const raw = rowValues['owner']
  const owner = typeof raw === 'string' ? raw : 'M. Okafor'
  return [
    {
      id: 'act-1',
      cls: 'change',
      at: '2026-08-02T09:41:00Z',
      actor: owner,
      channel: 'grid',
      summary: 'edited the row',
      deltas: [
        { fieldLabel: 'Status', before: 'Open', after: 'Mitigating' },
        { fieldLabel: 'Last reviewed', before: '2026-05-04', after: '2026-08-02' },
      ],
    },
    {
      id: 'act-2',
      cls: 'change',
      at: '2026-07-28T14:12:00Z',
      actor: 'recipe: High exposure approval',
      channel: 'automation',
      summary: 'requested approval and set the state',
      deltas: [{ fieldLabel: 'Status', before: 'Open', after: 'Mitigating' }],
    },
    {
      id: 'act-3',
      cls: 'change',
      at: '2026-07-25T11:02:00Z',
      actor: owner,
      channel: 'grid',
      summary: 'edited a restricted field',
      deltas: [{ fieldLabel: 'Owner rationale', withheld: true }],
    },
    {
      id: 'act-4',
      cls: 'governance',
      at: '2026-07-20T10:15:00Z',
      actor: 'risk@unops.org',
      channel: 'system',
      summary: 'tightened the read rule on Owner rationale (band 2)',
    },
    {
      id: 'act-5',
      cls: 'change',
      at: '2026-07-14T08:30:00Z',
      actor: 'import started by ' + owner,
      channel: 'import',
      summary: 'row created by CSV import',
    },
  ]
}
