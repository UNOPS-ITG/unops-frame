/**
 * Wiring regression guard: every callable name passed to apiCall('...') in src/
 * must exist in CALLABLE_TO_REST_MAPPING, otherwise apiCall throws
 * "No REST mapping found" at runtime. Run via `npm run check:wiring`
 * (chained into `npm run build`).
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(fileURLToPath(new URL('.', import.meta.url)), '..');
const srcDir = join(root, 'src');
const mappingFile = join(srcDir, 'services', 'callable-to-rest.mapping.ts');

// --- Collect mapped callable names ---
const mappingSource = readFileSync(mappingFile, 'utf8');
const mappedNames = new Set(
  [...mappingSource.matchAll(/^\s*'([\w-]+)':\s*\{/gm)].map((m) => m[1]),
);
if (mappedNames.size === 0) {
  console.error(`check-callable-mappings: no entries parsed from ${mappingFile} — parser out of date?`);
  process.exit(1);
}

// --- Collect apiCall('name') usages across src ---
function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      yield* walk(full);
    } else if (/\.(ts|tsx)$/.test(entry)) {
      yield full;
    }
  }
}

// Matches apiCall('name'), apiCall<T>('name'), including multi-line generics.
const usageRe = /\bapiCall\s*(?:<[\s\S]*?>)?\s*\(\s*['"`]([\w-]+)['"`]/g;

const problems = [];
let usageCount = 0;
for (const file of walk(srcDir)) {
  const source = readFileSync(file, 'utf8');
  for (const match of source.matchAll(usageRe)) {
    usageCount += 1;
    const name = match[1];
    if (!mappedNames.has(name)) {
      const line = source.slice(0, match.index).split('\n').length;
      problems.push(`${relative(root, file)}:${line} — apiCall('${name}') has no CALLABLE_TO_REST_MAPPING entry`);
    }
  }
}

if (usageCount === 0) {
  console.error('check-callable-mappings: found no apiCall() usages — extractor out of date?');
  process.exit(1);
}

if (problems.length > 0) {
  console.error(`check-callable-mappings: ${problems.length} unmapped callable(s):\n`);
  for (const p of problems) console.error(`  ${p}`);
  console.error('\nAdd the mapping to src/services/callable-to-rest.mapping.ts or remove the dead call.');
  process.exit(1);
}

console.log(`check-callable-mappings: OK (${usageCount} apiCall usages, ${mappedNames.size} mapped callables)`);
