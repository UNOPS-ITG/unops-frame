#!/usr/bin/env node
/**
 * Validate firestore.indexes.json before it reaches Cloud Build.
 *
 * `firebase deploy --only firestore` validates server-side, one index at a
 * time, and aborts on the first rejection — so a malformed file costs a whole
 * deploy cycle to discover, and then another to discover the next problem.
 * Everything checked here is a rule the API enforces anyway; the only thing
 * this adds is finding out in a second rather than in ten minutes.
 *
 * The rule that actually bit us:
 *
 *   HTTP 400 — "this index is not necessary, configure using single field
 *               index controls"
 *
 * The composite-index API only accepts indexes of TWO OR MORE fields.
 * Single-field indexes are managed separately, under `fieldOverrides`. That
 * includes single-field COLLECTION_GROUP indexes, which collection-group
 * queries genuinely do need — they just aren't declared in `indexes`.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const FILE = join(ROOT, 'firestore.indexes.json');

const SCOPES = new Set(['COLLECTION', 'COLLECTION_GROUP']);
const ORDERS = new Set(['ASCENDING', 'DESCENDING']);

const problems = [];
const warnings = [];

function fail(message) {
  problems.push(message);
}

let config;
try {
  config = JSON.parse(readFileSync(FILE, 'utf8'));
} catch (error) {
  console.error(`check-firestore-indexes: cannot parse firestore.indexes.json — ${error.message}`);
  process.exit(1);
}

const indexes = config.indexes ?? [];
const overrides = config.fieldOverrides ?? [];

// --- composite indexes ------------------------------------------------------

const seenIndexes = new Map();

for (const index of indexes) {
  const label = `${index.collectionGroup} [${(index.fields ?? []).map((f) => f.fieldPath).join(', ')}]`;

  if (!index.collectionGroup) fail(`index with no collectionGroup: ${JSON.stringify(index)}`);
  if (!SCOPES.has(index.queryScope)) {
    fail(`${label}: queryScope must be COLLECTION or COLLECTION_GROUP, got ${index.queryScope ?? '(missing)'}`);
  }

  const fields = index.fields ?? [];
  if (fields.length < 2) {
    // THE one that fails the deploy.
    fail(
      `${label}: single-field indexes are rejected by the composite-index API ` +
      `("this index is not necessary, configure using single field index controls"). ` +
      `Move it to fieldOverrides — including single-field COLLECTION_GROUP indexes, ` +
      `which belong there too.`,
    );
  }

  for (const field of fields) {
    const kinds = Object.keys(field).filter((k) => k !== 'fieldPath');
    if (kinds.length !== 1) {
      fail(`${label}: field ${field.fieldPath} needs exactly one of order/arrayConfig/vectorConfig, got [${kinds}]`);
    }
    if (field.order && !ORDERS.has(field.order)) {
      fail(`${label}: field ${field.fieldPath} has invalid order ${field.order}`);
    }
  }

  // An array-contains field must come before any range field, and there can be
  // at most one. Firestore rejects the rest server-side.
  const arrayFields = fields.filter((f) => f.arrayConfig);
  if (arrayFields.length > 1) {
    fail(`${label}: at most one arrayConfig field per index, found ${arrayFields.length}`);
  }

  const key = JSON.stringify([
    index.collectionGroup,
    index.queryScope,
    fields.map((f) => [f.fieldPath, f.order ?? f.arrayConfig ?? f.vectorConfig]),
  ]);
  if (seenIndexes.has(key)) fail(`${label}: duplicate index declaration`);
  seenIndexes.set(key, true);
}

// --- field overrides --------------------------------------------------------

const seenOverrides = new Map();

for (const override of overrides) {
  const label = `${override.collectionGroup}.${override.fieldPath}`;

  if (!override.collectionGroup || !override.fieldPath) {
    fail(`fieldOverride needs collectionGroup and fieldPath: ${JSON.stringify(override)}`);
    continue;
  }
  if (seenOverrides.has(label)) fail(`duplicate fieldOverride for ${label}`);
  seenOverrides.set(label, true);

  if (!Array.isArray(override.indexes)) {
    fail(`${label}: fieldOverride needs an indexes array (use [] to exempt the field entirely)`);
    continue;
  }

  for (const entry of override.indexes) {
    if (!SCOPES.has(entry.queryScope)) {
      fail(`${label}: override entry needs a valid queryScope, got ${entry.queryScope ?? '(missing)'}`);
    }
    const kinds = Object.keys(entry).filter((k) => k !== 'queryScope');
    if (kinds.length !== 1) {
      fail(`${label}: override entry needs exactly one of order/arrayConfig, got [${kinds}]`);
    }
  }

  // Declaring an override REPLACES Firestore's automatic single-field indexes
  // for that field. An override that adds a COLLECTION_GROUP scope but forgets
  // to re-declare the COLLECTION ones silently removes ordinary per-collection
  // ordering — and the deploy succeeds, so nothing tells you until a query
  // starts failing in production.
  const hasGroupScope = override.indexes.some((e) => e.queryScope === 'COLLECTION_GROUP');
  const collectionOrders = new Set(
    override.indexes.filter((e) => e.queryScope === 'COLLECTION' && e.order).map((e) => e.order),
  );
  if (hasGroupScope && (!collectionOrders.has('ASCENDING') || !collectionOrders.has('DESCENDING'))) {
    warnings.push(
      `${label}: declares a COLLECTION_GROUP index but not both COLLECTION orders. ` +
      `An override replaces the automatic single-field indexes, so per-collection ` +
      `ordering on this field will stop working. Re-declare COLLECTION ASCENDING ` +
      `and DESCENDING unless you are certain nothing orders by it.`,
    );
  }
}

// --- report -----------------------------------------------------------------

for (const warning of warnings) console.warn(`check-firestore-indexes: WARNING ${warning}`);

if (problems.length) {
  console.error('check-firestore-indexes: FAILED\n');
  for (const problem of problems) console.error(`  - ${problem}`);
  console.error(`\n${problems.length} problem(s). These would be rejected by the Firestore API at deploy time.`);
  process.exit(1);
}

console.log(
  `check-firestore-indexes: OK (${indexes.length} composite indexes, ${overrides.length} field overrides` +
  `${warnings.length ? `, ${warnings.length} warning(s)` : ''})`,
);
