#!/usr/bin/env node
/**
 * Seed a demonstrable register into the Firestore emulator.
 *
 * Deliberately includes rows the signed-in developer cannot see and a field
 * they cannot read. A seed of uniformly visible data makes the governed grid
 * look exactly like an ungoverned one, so the behaviour that distinguishes
 * Frame is the behaviour nobody ever exercises locally.
 */

import { ports } from '../config/ports.mjs'

const HOST = `127.0.0.1:${ports.emulators.firestore}`
const PROJECT = process.env.FRAME_GCP_PROJECT ?? 'frame-local'
const DATABASE = process.env.FRAME_FIRESTORE_DATABASE ?? 'frame'
const WORKSPACE = 'ws-demo'
const BLUEPRINT = 'risk'

const BASE = `http://${HOST}/v1/projects/${PROJECT}/databases/${DATABASE}/documents`

/** Firestore's REST value encoding. */
function value(v) {
  if (v === null || v === undefined) return { nullValue: null }
  if (typeof v === 'boolean') return { booleanValue: v }
  if (typeof v === 'number') {
    return Number.isInteger(v) ? { integerValue: String(v) } : { doubleValue: v }
  }
  if (typeof v === 'string') return { stringValue: v }
  if (Array.isArray(v)) return { arrayValue: { values: v.map(value) } }
  return { mapValue: { fields: Object.fromEntries(Object.entries(v).map(([k, x]) => [k, value(x)])) } }
}

const doc = (fields) => ({
  fields: Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, value(v)])),
})

/**
 * `Bearer owner` is the Firestore emulator's admin credential.
 *
 * Needed because `firestore.rules` denies everything — deliberately and
 * permanently, since every read and write goes through the API and the rules
 * layer is not a permission surface. A seed is server-side setup, so it takes
 * the same path the backend's admin SDK does rather than being a reason to
 * weaken the rules.
 */
const ADMIN = { 'Content-Type': 'application/json', Authorization: 'Bearer owner' }

async function put(path, fields) {
  const response = await fetch(`${BASE}/${path}`, {
    method: 'PATCH',
    headers: ADMIN,
    body: JSON.stringify(doc(fields)),
  })
  if (!response.ok) {
    throw new Error(`${response.status} writing ${path}: ${await response.text()}`)
  }
}

const blueprint = {
  id: BLUEPRINT,
  name: 'Risk register',
  workspace_id: WORKSPACE,
  tier: 'team',
  version: 1,
  view_defaults: { title_field: 'title' },
  fields: [
    { id: 'title', label: 'Risk', type: 'text', variant: 'single', required: true, indexed: true },
    {
      id: 'status', label: 'Status', type: 'single_select', indexed: true,
      options: [
        { key: 'open', label: 'Open' },
        { key: 'mitigating', label: 'Mitigating' },
        { key: 'closed', label: 'Closed' },
      ],
    },
    { id: 'owner', label: 'Owner', type: 'text', variant: 'single', indexed: true },
    {
      id: 'exposure', label: 'Exposure (USD)', type: 'number', variant: 'decimal',
      indexed: true, validation: { min: 0, max: 100000000 },
    },
    { id: 'reviewed', label: 'Last reviewed', type: 'date', indexed: true },
    // The Gantt pair (BP-1a field maps): mitigation runs from start to due.
    // Not indexed — the views lay them out client-side from fetched values,
    // and an unindexed field honestly reports itself unsortable in the grid.
    { id: 'mitigation_start', label: 'Mitigation start', type: 'date' },
    { id: 'mitigation_due', label: 'Mitigation due', type: 'date' },
    // Band 2 is at or above the restricted threshold, so this renders as a
    // typed stub for anyone without a grant that reaches it.
    { id: 'rationale', label: 'Owner rationale', type: 'text', variant: 'long', sensitivity: 2 },
    // PRD 14. Present so the corporate cell renderer and the picker are
    // exercisable locally: without a corporate field seeded, the only way to
    // see either is to hand-write a Blueprint, which means neither gets looked
    // at until a real one exists.
    //
    // The dimension is a LOCAL demo relation seeded below, not a real one. It
    // has to be, and the reason is worth writing down: every relation in the
    // real swept catalogue classifies as `entitled`, because the probe cannot
    // confirm an all-staff audience without the floor principal that is still
    // waiting on GCP provisioning. An entitled dimension resolves live or
    // renders a restricted stub — correct, and it means the snapshot and
    // staleness treatments would never appear in development.
    {
      id: 'agency', label: 'Agency', type: 'corporate_reference',
      dimension: 'Demo_Api.Agency',
    },
  ],
  // Expressed with ALLOWS that union, never a deny.
  //
  // A deny beats every allow at every scope, which makes it the right tool for
  // an exclusion nobody may override and the wrong tool for "most people see
  // the small exposures" — a deny on `*` would also deny the risk team, since
  // being in a narrower group is not an escape from a deny that names you.
  permissions: [
    // Everyone: unrestricted fields, and only the small exposures.
    {
      principals: ['*'], actions: ['read', 'create', 'update'], effect: 'allow', max_band: 1,
      row_condition: {
        type: 'binary', op: 'lt',
        left: { type: 'field', id: 'exposure' },
        right: { type: 'literal', value: 5000000 },
      },
    },
    // The risk team: every field, every row.
    {
      principals: ['group:risk-team'],
      actions: ['read', 'create', 'update'],
      effect: 'allow',
    },
  ],
}

const OWNERS = ['A. Haddad', 'M. Osei', 'L. Fernández', 'R. Nakamura', 'T. Bergström']
const STATUSES = ['open', 'mitigating', 'closed']
const KINDS = ['delivery', 'supplier', 'compliance', 'currency', 'safety']

/**
 * One `open` corporate dimension, for development only.
 *
 * Everything in the real swept catalogue classifies as `entitled`, and
 * correctly so: the disclosure probe refuses to call anything open until a
 * floor principal confirms the all-staff audience, and that principal is
 * waiting on GCP provisioning. An entitled dimension resolves live or renders a
 * PM-5 stub, which is right — and means the snapshot, staleness and orphan
 * treatments never appear locally.
 *
 * Written only if the workspace has no catalogue root yet, so a real sweep is
 * never overwritten. `Demo_Api` is not a dataset in `unops-datahub`; because an
 * open dimension is never queried, that costs nothing.
 */
async function seedCorporateDemo() {
  const root = `workspaces/${WORKSPACE}/corporateCatalogue/current`
  const swept = await fetch(`${BASE}/${root}`, { headers: ADMIN }).catch(() => null)

  // The demo relation is written either way; the root only if there is no real
  // sweep to overwrite. A real sweep's summary counts are its own, and
  // replacing them with "1 dimension" would make the catalogue page report
  // something false about the warehouse.
  if (!swept?.ok) {
    await put(root, {
      source: {
        id: 'demo',
        project: 'frame-local-demo',
        excludedDatasets: [],
        location: 'EU',
        metadataDataset: 'Metadata_Api',
        maxBytesBilled: 2000000000,
        requirePartitionFilter: true,
        enabled: true,
      },
      sweptAt: new Date().toISOString(),
      dimensionCount: 1,
      factCount: 0,
      relationCount: 1,
      openDimensionCount: 1,
      quarantined: [],
      restored: [],
      errors: [],
    })
  }

  // snake_case, matching what the sweep writes. The Dimension model forbids
  // extra keys, so a camelCase copy validates as nothing and the relation reads
  // back as missing — which renders every reference to it as orphaned, a
  // symptom that points at the data rather than at the seed.
  await put(`${root}/relations/Demo_Api__Agency`, {
    kind: 'dimension',
    id: 'Demo_Api.Agency',
    dataset: 'Demo_Api',
    table: 'Agency',
    label: 'Agency',
    description:
      'A demonstration dimension Frame seeds for local development, so the corporate cell treatments render before a real open dimension exists.',
    business_domain: 'Demo',
    business_key: 'Agency_Code',
    effective_date_column: null,
    attributes: [
      {
        name: 'Agency_Code', label: 'Agency code', description: null, data_type: 'STRING',
        role: 'dimension', policy_tag: null, is_business_key: true,
      },
      {
        name: 'Agency_Name', label: 'Agency name', description: null, data_type: 'STRING',
        role: 'dimension', policy_tag: null, is_business_key: false,
      },
    ],
    disclosure: 'open',
    label_visibility: 'open',
    status: 'active',
    classification_reasons: [
      'Seeded for local development; not the result of a disclosure probe.',
    ],
  })
  console.log(
    swept?.ok
      ? '  corporate: added the open demo dimension beside the swept catalogue'
      : '  corporate: seeded one open demo dimension',
  )
}

async function main() {
  console.log(`seeding ${PROJECT}/${DATABASE} at ${HOST}`);

  await put(`workspaces/${WORKSPACE}`, { name: 'Demo workspace' })
  await put(`workspaces/${WORKSPACE}/blueprints/${BLUEPRINT}`, blueprint)
  await seedCorporateDemo()

  // Two personas, because the milestone's whole claim is that they see
  // different things. A seed with one identity makes the governed grid look
  // exactly like an ungoverned one.
  //
  // Membership is keyed on the SUBJECT, never the email: an address is mutable
  // and reassignable, so keying grants on one means a recycled address silently
  // inherits them. The dev bypass prefixes its subject so a bypassed identity
  // is distinguishable downstream from a real session (PM-7), which means a
  // local seed needs BOTH keys — seeding only the email is a silent no-op that
  // makes every group-scoped rule quietly stop matching.
  const people = [
    { email: 'risk@unops.org', groups: ['staff', 'risk-team'] },
    { email: 'dev@unops.org', groups: ['staff'] },
    ...(process.env.FRAME_DEV_EMAIL
      ? [{ email: process.env.FRAME_DEV_EMAIL, groups: ['staff'] }]
      : []),
  ]
  for (const person of people) {
    for (const subject of [person.email, `dev-bypass:${person.email}`]) {
      await put(`workspaces/${WORKSPACE}/members/${subject}`, {
        groups: person.groups,
        roles: ['editor'],
      })
    }
  }

  // Rows the seed did not write — e2e creates, manual experiments — are
  // cleared first. The seed OWNS the demo register: without this, every test
  // run leaves "E2E 1785…" litter at the top of the grid forever, because the
  // API deliberately has no delete yet (lifecycle archival is a real feature,
  // not a dev-seed workaround).
  const listed = await fetch(
    `${BASE}/workspaces/${WORKSPACE}/rows/${BLUEPRINT}/items?pageSize=1000&mask.fieldPaths=__name__`,
    { headers: ADMIN },
  ).then((r) => (r.ok ? r.json() : {}))
  let cleared = 0
  for (const doc of listed.documents ?? []) {
    const id = doc.name.split('/').pop()
    if (!/^r\d{5}$/.test(id)) {
      await fetch(`${BASE}/workspaces/${WORKSPACE}/rows/${BLUEPRINT}/items/${id}`, {
        method: 'DELETE',
        headers: ADMIN,
      })
      cleared += 1
    }
  }
  if (cleared > 0) console.log(`  cleared ${cleared} non-seed rows`)

  const total = Number(process.env.FRAME_SEED_ROWS ?? 500)
  for (let i = 0; i < total; i++) {
    // Every eleventh row is above the deny threshold, so roughly 9% of the
    // register is withheld — visible in the annotation without swamping it.
    const exposure = i % 11 === 0 ? 5_000_000 + i : ((i * 7919) % 900_000) + 1_000
    await put(`workspaces/${WORKSPACE}/rows/${BLUEPRINT}/items/r${String(i).padStart(5, '0')}`, {
      id: `r${String(i).padStart(5, '0')}`,
      blueprintId: BLUEPRINT,
      workspaceId: WORKSPACE,
      lifecycleStatus: 'active',
      values: {
        title: `Risk ${i + 1}: ${KINDS[i % KINDS.length]} exposure`,
        status: STATUSES[i % STATUSES.length],
        owner: OWNERS[i % OWNERS.length],
        exposure,
        reviewed: new Date(2026, 0, 1 + (i % 200)).toISOString(),
        // Mitigation windows stagger across Jul–Nov 2026 with varied spans,
        // so the Gantt has real overlapping bars rather than a staircase.
        mitigation_start: new Date(2026, 6, 1 + (i % 90)).toISOString(),
        mitigation_due: new Date(2026, 6, 15 + (i % 90) + ((i * 7) % 60)).toISOString(),
        rationale: `Reviewed with the owner in Q${(i % 4) + 1}.`,
        // Three of the four corporate states, so the renderer's treatments are
        // visible without waiting for a warehouse to go wrong: a fresh
        // snapshot, one old enough to be marked stale, and one whose relation
        // was withdrawn upstream. The fourth — a live resolve — needs a
        // connection and cannot be seeded.
        ...(i % 3 === 0
          ? {
              agency: {
                key: `AG${String((i % 40) + 1).padStart(3, '0')}`,
                label: `Agency ${(i % 40) + 1}`,
                snapshotAt:
                  i % 9 === 0
                    ? new Date(2024, 0, 1).toISOString() // older than 90 days
                    : new Date().toISOString(),
                catalogueVersion: 1,
              },
            }
          : {}),
      },
      fieldVersions: { title: 1, status: 1, owner: 1, exposure: 1 },
      // The generic index projection the reader queries against. Written here
      // by hand because this bypasses the writer on purpose — a seed that went
      // through the API would need the API running to seed the API.
      eq: [
        `fld_title=Risk ${i + 1}: ${KINDS[i % KINDS.length]} exposure`,
        `fld_status=${STATUSES[i % STATUSES.length]}`,
        `fld_owner=${OWNERS[i % OWNERS.length]}`,
        `fld_exposure=${exposure}`,
      ],
      num0: exposure,
      // The date slot the compiler assigns `reviewed`. Its absence was found
      // by the overview's "longest unreviewed" list coming back EMPTY:
      // Firestore's orderBy excludes documents missing the ordered field, so
      // an unstamped slot makes every row vanish under that sort — silently,
      // because the slot legitimately exists. (The platform-level version of
      // this sharp edge is PRD 02 open question 4.)
      date0: new Date(2026, 0, 1 + (i % 200)).toISOString(),
      txt0: `Risk ${i + 1}: ${KINDS[i % KINDS.length]} exposure`,
      txt1: STATUSES[i % STATUSES.length],
      txt2: OWNERS[i % OWNERS.length],
    })

    if ((i + 1) % 100 === 0) console.log(`  ${i + 1}/${total}`)
  }

  // One shared saved view, so the demonstration is "the same URL", not "two
  // similar URLs". A view carries a query and grants nothing.
  await put(`workspaces/${WORKSPACE}/blueprints/${BLUEPRINT}/views/open-risks`, {
    id: 'open-risks',
    name: 'Open risks by exposure',
    blueprint_id: BLUEPRINT,
    workspace_id: WORKSPACE,
    scope: 'shared',
    author: 'dev-bypass:risk@unops.org',
    filter: {
      type: 'binary', op: 'eq',
      left: { type: 'field', id: 'status' },
      right: { type: 'literal', value: 'open' },
    },
    sort: [{ field_id: 'exposure', direction: 'desc' }],
    columns: [],
    row_height: 'normal',
    blueprint_version: 1,
  })

  await seedPilotApps()

  const base = `http://localhost:${ports.frontend}`
  console.log('done.')
  console.log(`  register:  ${base}/#/w/${WORKSPACE}/b/${BLUEPRINT}`)
  console.log(`  saved view: ${base}/#/w/${WORKSPACE}/b/${BLUEPRINT}/v/open-risks`)
  console.log(`  pilots:    contracts · assets · projects · fleet (same workspace)`)
  console.log('  personas:  risk@unops.org (risk-team) · dev@unops.org (staff)')
}

/* ---------------------------------------------------------------------------
 * The pilot apps: contract, asset, project and fleet management — the four
 * registers of specs/pilots/paper-catalog.md, seeded as REAL Blueprints with
 * real rows so the workspace reads as a portfolio of working apps rather
 * than one demo and a wizard gallery.
 *
 * Slot projections follow the compiler's assignment order exactly as the
 * risk seed does: indexed text/select fields take txt0..N in declaration
 * order, numbers num0.., dates date0... Getting this wrong is silent (rows
 * vanish under sort — PRD 02 open question 4), which is why each app keeps
 * its indexed set small and stated.
 * ------------------------------------------------------------------------ */

const MANAGERS = ['A. Haddad', 'M. Osei', 'L. Fernández', 'R. Nakamura', 'T. Bergström']
const HOLDERS = ['J. Mwangi', 'P. Silva', 'A. Rahman', 'C. Dubois', 'S. Petrov']
const SUPPLIERS = [
  'Nordwind Logistics', 'Sahel Power Co', 'Meridian Prefab', 'AquaPure Systems',
  'HighPoint Engineering', 'Crescent Freight', 'Terra Survey Ltd', 'Baltic Gensets',
]
const day = (y, m, d) => new Date(y, m, d).toISOString()

const APPS = [
  {
    id: 'contracts',
    name: 'Contract management',
    titleField: 'title',
    count: 120,
    fields: [
      { id: 'title', label: 'Contract', type: 'text', variant: 'single', required: true, indexed: true },
      {
        id: 'status', label: 'Status', type: 'single_select', indexed: true,
        options: [
          { key: 'active', label: 'Active' },
          { key: 'review', label: 'Under review' },
          { key: 'closed', label: 'Closed' },
        ],
      },
      { id: 'manager', label: 'Contract manager', type: 'text', variant: 'single', indexed: true },
      { id: 'contract_value', label: 'Value (USD)', type: 'number', variant: 'decimal', indexed: true },
      { id: 'end', label: 'End', type: 'date', indexed: true },
      { id: 'start', label: 'Start', type: 'date' },
      { id: 'supplier', label: 'Supplier', type: 'text', variant: 'single' },
      {
        id: 'performance', label: 'Performance', type: 'single_select',
        options: [
          { key: 'good', label: 'Good' },
          { key: 'watch', label: 'Watch' },
          { key: 'poor', label: 'Poor' },
        ],
      },
      { id: 'negotiation_notes', label: 'Negotiation notes', type: 'text', variant: 'long', sensitivity: 2 },
    ],
    row(i) {
      const supplier = SUPPLIERS[i % SUPPLIERS.length]
      const item = ['Generator supply', 'Prefab offices', 'Road rehabilitation', 'Water systems', 'Freight services'][i % 5]
      const status = i % 20 < 12 ? 'active' : i % 20 < 17 ? 'review' : 'closed'
      const startD = new Date(2025, i % 12, 1 + (i % 27))
      const months = 6 + ((i * 5) % 19)
      const endD = new Date(startD.getFullYear(), startD.getMonth() + months, startD.getDate())
      const contract_value = 50_000 + ((i * 37561) % 4_500_000) + (i % 13 === 0 ? 5_500_000 : 0)
      return {
        values: {
          title: `CON-2026-${String(i + 1).padStart(3, '0')} · ${item} — ${supplier}`,
          status,
          manager: MANAGERS[i % MANAGERS.length],
          contract_value,
          end: endD.toISOString(),
          start: startD.toISOString(),
          supplier,
          performance: i % 9 === 0 ? 'poor' : i % 4 === 0 ? 'watch' : 'good',
          negotiation_notes: `Payment terms concessions agreed in round ${1 + (i % 3)}.`,
        },
        eq: [
          `fld_status=${status}`,
          `fld_manager=${MANAGERS[i % MANAGERS.length]}`,
          `fld_contract_value=${contract_value}`,
        ],
        slots: {
          txt0: `CON-2026-${String(i + 1).padStart(3, '0')} · ${item} — ${supplier}`,
          txt1: status,
          txt2: MANAGERS[i % MANAGERS.length],
          num0: contract_value,
          date0: endD.toISOString(),
        },
      }
    },
  },
  {
    id: 'assets',
    name: 'Asset management',
    titleField: 'description',
    count: 260,
    fields: [
      { id: 'description', label: 'Asset', type: 'text', variant: 'single', required: true, indexed: true },
      {
        id: 'status', label: 'Status', type: 'single_select', indexed: true,
        options: [
          { key: 'in_transit', label: 'In transit' },
          { key: 'in_storage', label: 'In storage' },
          { key: 'issued', label: 'Issued' },
          { key: 'under_repair', label: 'Under repair' },
          { key: 'disposed', label: 'Disposed' },
        ],
      },
      { id: 'custodian', label: 'Custodian', type: 'text', variant: 'single', indexed: true },
      { id: 'value_usd', label: 'Value (USD)', type: 'number', variant: 'decimal', indexed: true },
      { id: 'last_verified', label: 'Last verified', type: 'date', indexed: true },
      { id: 'asset_tag', label: 'Asset tag', type: 'text', variant: 'single' },
      {
        id: 'condition', label: 'Condition', type: 'single_select',
        options: [
          { key: 'good', label: 'Good' },
          { key: 'fair', label: 'Fair' },
          { key: 'damaged', label: 'Damaged' },
        ],
      },
      { id: 'warranty_until', label: 'Warranty until', type: 'date' },
      { id: 'disposal_notes', label: 'Disposal justification', type: 'text', variant: 'long', sensitivity: 2 },
    ],
    row(i) {
      const kind = ['Laptop — Dell Latitude 5440', 'Generator — 50kVA silent', 'Printer — HP M479',
        'Satellite phone — Iridium 9575', 'Field tent — 6-person', 'Water pump — submersible 3kW'][i % 6]
      const description = `${kind} #${String(1 + (i % 60)).padStart(2, '0')}`
      const status = ['in_storage', 'issued', 'issued', 'issued', 'in_transit', 'in_storage', 'under_repair',
        'issued', 'in_storage', 'issued'][i % 10] ?? 'issued'
      const finalStatus = i % 47 === 0 ? 'disposed' : status
      const custodian = HOLDERS[i % HOLDERS.length]
      const value_usd = 300 + ((i * 977) % 24_000)
      const verified = day(2025, i % 12, 1 + (i % 27))
      return {
        values: {
          description,
          status: finalStatus,
          custodian,
          value_usd,
          last_verified: verified,
          asset_tag: `UN-AST-${1000 + i}`,
          condition: i % 17 === 0 ? 'damaged' : i % 5 === 0 ? 'fair' : 'good',
          warranty_until: day(2026 + (i % 3), i % 12, 15),
          disposal_notes: 'Board case reference pending.',
        },
        eq: [`fld_status=${finalStatus}`, `fld_custodian=${custodian}`, `fld_value_usd=${value_usd}`],
        slots: { txt0: description, txt1: finalStatus, txt2: custodian, num0: value_usd, date0: verified },
      }
    },
  },
  {
    id: 'projects',
    name: 'Project management',
    titleField: 'title',
    count: 48,
    fields: [
      { id: 'title', label: 'Project', type: 'text', variant: 'single', required: true, indexed: true },
      {
        id: 'status', label: 'Phase', type: 'single_select', indexed: true,
        options: [
          { key: 'inception', label: 'Inception' },
          { key: 'delivery', label: 'Delivery' },
          { key: 'closure', label: 'Closure' },
        ],
      },
      { id: 'manager', label: 'Project manager', type: 'text', variant: 'single', indexed: true },
      { id: 'budget_usd', label: 'Budget (USD)', type: 'number', variant: 'decimal', indexed: true },
      { id: 'end', label: 'End', type: 'date', indexed: true },
      { id: 'start', label: 'Start', type: 'date' },
      { id: 'spent_usd', label: 'Spent (USD)', type: 'number', variant: 'decimal' },
      { id: 'country', label: 'Country', type: 'text', variant: 'single' },
      { id: 'commentary', label: 'Board commentary', type: 'text', variant: 'long', sensitivity: 2 },
    ],
    row(i) {
      const sector = ['Solar electrification', 'Feeder roads rehabilitation', 'Health post construction',
        'Flood protection works', 'School WASH upgrade', 'Cold-chain expansion'][i % 6]
      const place = ['Kakuma', 'Karamoja', 'Bay Region', 'Sittwe', 'Nord-Kivu', 'Chocó', 'Sindh', 'Timbuktu'][i % 8]
      const title = `${sector} — ${place}`
      const status = i % 10 < 2 ? 'inception' : i % 10 < 8 ? 'delivery' : 'closure'
      const startD = new Date(2024 + (i % 2), i % 12, 1)
      const endD = new Date(2026 + (i % 3), (i * 5) % 12, 28)
      const budget_usd = 800_000 + ((i * 613_777) % 29_000_000)
      const country = ['Kenya', 'Uganda', 'Somalia', 'Myanmar', 'DR Congo', 'Colombia', 'Pakistan', 'Mali'][i % 8]
      return {
        values: {
          title,
          status,
          manager: MANAGERS[i % MANAGERS.length],
          budget_usd,
          end: endD.toISOString(),
          start: startD.toISOString(),
          spent_usd: Math.round(budget_usd * (status === 'closure' ? 0.96 : status === 'delivery' ? 0.55 : 0.08)),
          country,
          commentary: 'Sensitivities discussed at the last portfolio board.',
        },
        eq: [`fld_status=${status}`, `fld_manager=${MANAGERS[i % MANAGERS.length]}`, `fld_country=${country}`],
        slots: {
          txt0: title,
          txt1: status,
          txt2: MANAGERS[i % MANAGERS.length],
          num0: budget_usd,
          date0: endD.toISOString(),
        },
      }
    },
  },
  {
    id: 'fleet',
    name: 'Fleet management',
    titleField: 'plate',
    count: 45,
    fields: [
      { id: 'plate', label: 'Plate', type: 'text', variant: 'single', required: true, indexed: true },
      { id: 'model', label: 'Model', type: 'text', variant: 'single', indexed: true },
      {
        id: 'status', label: 'Status', type: 'single_select', indexed: true,
        options: [
          { key: 'in_service', label: 'In service' },
          { key: 'maintenance', label: 'In maintenance' },
          { key: 'retired', label: 'Retired' },
        ],
      },
      { id: 'odometer', label: 'Odometer (km)', type: 'number', variant: 'decimal', indexed: true },
      { id: 'insurance_expiry', label: 'Insurance expiry', type: 'date', indexed: true },
      { id: 'driver', label: 'Driver', type: 'text', variant: 'single' },
      { id: 'next_service_km', label: 'Next service (km)', type: 'number', variant: 'decimal' },
      { id: 'acquisition', label: 'Acquired', type: 'date' },
    ],
    row(i) {
      const model = ['Toyota Land Cruiser 79', 'Toyota Hilux', 'Nissan Patrol', 'Ford Ranger'][i % 4]
      const plate = `UN-${4200 + i}`
      const status = i % 10 < 7 ? 'in_service' : i % 10 < 9 ? 'maintenance' : 'retired'
      const odometer = 15_000 + ((i * 6553) % 205_000)
      const insurance = day(2026, 7 + (i % 12), 1 + (i % 27))
      return {
        values: {
          plate,
          model,
          status,
          odometer,
          insurance_expiry: insurance,
          driver: HOLDERS[i % HOLDERS.length],
          next_service_km: odometer + (10_000 - (odometer % 10_000)),
          acquisition: day(2019 + (i % 6), i % 12, 10),
        },
        eq: [`fld_status=${status}`, `fld_model=${model}`, `fld_plate=${plate}`],
        slots: { txt0: plate, txt1: model, txt2: status, num0: odometer, date0: insurance },
      }
    },
  },
]

async function seedPilotApps() {
  for (const app of APPS) {
    await put(`workspaces/${WORKSPACE}/blueprints/${app.id}`, {
      id: app.id,
      name: app.name,
      workspace_id: WORKSPACE,
      tier: 'team',
      version: 1,
      view_defaults: { title_field: app.titleField },
      fields: app.fields,
      // Everyone reads and writes the working fields; the one band-2 field
      // per app renders as a stub for both local personas, so governance is
      // visible in every app, and the risk-team persona keeps its full view.
      permissions: [
        { principals: ['*'], actions: ['read', 'create', 'update'], effect: 'allow', max_band: 1 },
        { principals: ['group:risk-team'], actions: ['read', 'create', 'update'], effect: 'allow' },
      ],
    })

    // The seed owns each app's rows: clear anything it did not write.
    const listed = await fetch(
      `${BASE}/workspaces/${WORKSPACE}/rows/${app.id}/items?pageSize=1000&mask.fieldPaths=__name__`,
      { headers: ADMIN },
    ).then((r) => (r.ok ? r.json() : {}))
    for (const d of listed.documents ?? []) {
      const id = d.name.split('/').pop()
      if (!/^r\d{5}$/.test(id)) {
        await fetch(`${BASE}/workspaces/${WORKSPACE}/rows/${app.id}/items/${id}`, {
          method: 'DELETE',
          headers: ADMIN,
        })
      }
    }

    for (let i = 0; i < app.count; i++) {
      const { values, eq, slots } = app.row(i)
      await put(`workspaces/${WORKSPACE}/rows/${app.id}/items/r${String(i).padStart(5, '0')}`, {
        id: `r${String(i).padStart(5, '0')}`,
        blueprintId: app.id,
        workspaceId: WORKSPACE,
        lifecycleStatus: 'active',
        values,
        fieldVersions: Object.fromEntries(Object.keys(values).map((k) => [k, 1])),
        eq,
        ...slots,
      })
    }
    console.log(`  ${app.id}: ${app.count} rows`)
  }
}

main().catch((error) => {
  console.error(error.message)
  process.exitCode = 1
})
