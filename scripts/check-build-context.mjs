#!/usr/bin/env node
/**
 * Guard the frontend Docker build context.
 *
 * `Dockerfile.frontend` copies a deliberately narrow context — package files,
 * the tsconfigs, `src/`, `public/`, and each build script named individually.
 * That keeps the image small and its layer cache sharp, but it means adding a
 * script to `npm run build` without also adding it to the `COPY` line produces
 * a build that passes locally and dies in Cloud Build with:
 *
 *   Error: Cannot find module '/app/scripts/<name>.mjs'
 *
 * Which is a whole build to discover a one-line omission. This compares the two
 * lists and fails immediately.
 *
 * The right response to a failure here is usually NOT to add the COPY. Ask
 * first whether the check belongs in the frontend image at all: anything
 * validating infra config (firestore.indexes.json, terraform, cloudbuild)
 * cannot see its own input from inside an image whose context excludes it, and
 * belongs in the pre-commit hook or the relevant Cloud Build step instead.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

const SCRIPT_RE = /scripts\/[A-Za-z0-9._-]+\.(mjs|js|cjs)/g;

const buildScript = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8')).scripts?.build ?? '';
const dockerfile = readFileSync(join(ROOT, 'Dockerfile.frontend'), 'utf8');

const invoked = [...new Set(buildScript.match(SCRIPT_RE) ?? [])];
const copied = new Set(
  dockerfile
    .split('\n')
    .filter((line) => line.trimStart().startsWith('COPY'))
    .flatMap((line) => line.match(SCRIPT_RE) ?? []),
);

const missing = invoked.filter((script) => !copied.has(script));

if (missing.length) {
  console.error('check-build-context: FAILED\n');
  for (const script of missing) {
    console.error(`  - "npm run build" invokes ${script}, but Dockerfile.frontend never COPYs it.`);
  }
  console.error(
    '\nThe Cloud Build frontend image would fail with "Cannot find module".\n' +
    'Either add it to the COPY line in Dockerfile.frontend, or — if it validates\n' +
    'something outside the image context (infra config, backend files) — move it\n' +
    'to .husky/pre-commit and the relevant cloudbuild.yaml step instead.',
  );
  process.exit(1);
}

console.log(
  `check-build-context: OK (${invoked.length} build script${invoked.length === 1 ? '' : 's'}, all present in the image)`,
);
