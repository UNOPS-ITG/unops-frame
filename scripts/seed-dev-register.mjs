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
    // Band 2 is at or above the restricted threshold, so this renders as a
    // typed stub for anyone without a grant that reaches it.
    { id: 'rationale', label: 'Owner rationale', type: 'text', variant: 'long', sensitivity: 2 },
  ],
  permissions: [
    { principals: ['*'], actions: ['read', 'create', 'update'], effect: 'allow', max_band: 1 },
    // A row-scoped deny, so the withheld count is non-zero and the annotation
    // has something true to say.
    {
      principals: ['*'], actions: ['read'], effect: 'deny',
      row_condition: {
        type: 'binary', op: 'gte',
        left: { type: 'field', id: 'exposure' },
        right: { type: 'literal', value: 5000000 },
      },
    },
  ],
}

const OWNERS = ['A. Haddad', 'M. Osei', 'L. Fernández', 'R. Nakamura', 'T. Bergström']
const STATUSES = ['open', 'mitigating', 'closed']
const KINDS = ['delivery', 'supplier', 'compliance', 'currency', 'safety']

async function main() {
  console.log(`seeding ${PROJECT}/${DATABASE} at ${HOST}`);

  await put(`workspaces/${WORKSPACE}`, { name: 'Demo workspace' })
  await put(`workspaces/${WORKSPACE}/blueprints/${BLUEPRINT}`, blueprint)

  for (const email of ['dev@unops.org', process.env.FRAME_DEV_EMAIL].filter(Boolean)) {
    await put(`workspaces/${WORKSPACE}/members/${email}`, {
      groups: ['staff'],
      roles: ['editor'],
    })
  }

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
        rationale: `Reviewed with the owner in Q${(i % 4) + 1}.`,
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
      txt0: `Risk ${i + 1}: ${KINDS[i % KINDS.length]} exposure`,
      txt1: STATUSES[i % STATUSES.length],
      txt2: OWNERS[i % OWNERS.length],
    })

    if ((i + 1) % 100 === 0) console.log(`  ${i + 1}/${total}`)
  }

  console.log(`done. open http://localhost:${ports.frontend}/#register/${WORKSPACE}/${BLUEPRINT}`)
}

main().catch((error) => {
  console.error(error.message)
  process.exitCode = 1
})
