#!/usr/bin/env node
/**
 * Help translation status.
 *
 * English is the source of truth for the help corpus; the five translations
 * live under `public/assets/help/<locale>/` and mirror its paths exactly. This
 * script hashes every English article and compares it with the hash recorded in
 * `translations.manifest.json` at the time each translation was written, so a
 * translation can be in one of three states:
 *
 *   current  — the manifest hash matches the English file as it stands now
 *   stale    — the English article changed after the translation was written
 *   missing  — no translated file (or no manifest entry) at all
 *
 * Deliberately NOT wired into `npm run build`. Unlike a UI string, a lagging
 * help translation degrades cleanly — the viewer falls back to the English
 * article and says so — and that must never be able to block a deploy. The
 * build guard for the UI catalogs is `scripts/check-locales.mjs`.
 *
 * Run directly, or via `npm run help:status`. Exits 0 always; pass `--strict`
 * to exit 1 when anything is stale or missing (useful inside the /help-docs
 * skill, which wants a hard signal).
 */
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const HELP_DIR = join(ROOT, 'public', 'assets', 'help');
const MANIFEST_PATH = join(HELP_DIR, 'translations.manifest.json');
const TARGETS = ['es', 'fr', 'ru', 'ar', 'zh'];

const strict = process.argv.includes('--strict');
const verbose = process.argv.includes('--verbose');

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function loadIndex() {
  const path = join(HELP_DIR, 'index.json');
  if (!existsSync(path)) {
    console.error(`help-translation-status: missing ${path}`);
    process.exit(1);
  }
  return JSON.parse(readFileSync(path, 'utf8'));
}

function loadManifest() {
  if (!existsSync(MANIFEST_PATH)) return { articles: {} };
  try {
    const parsed = JSON.parse(readFileSync(MANIFEST_PATH, 'utf8'));
    return { articles: parsed.articles ?? {} };
  } catch (err) {
    console.error(`help-translation-status: could not parse the manifest — ${err.message}`);
    process.exit(1);
  }
}

const index = loadIndex();
const manifest = loadManifest();

const rows = [];
const totals = Object.fromEntries(TARGETS.map((l) => [l, { current: 0, stale: 0, missing: 0 }]));
let missingEnglish = 0;

for (const section of index.sections ?? []) {
  for (const article of section.articles ?? []) {
    const enPath = join(HELP_DIR, article.file);
    if (!existsSync(enPath)) {
      missingEnglish += 1;
      rows.push({ id: article.id, file: article.file, states: Object.fromEntries(TARGETS.map((l) => [l, 'no-source'])) });
      continue;
    }

    const enHash = sha256(enPath);
    const record = manifest.articles?.[article.id] ?? {};
    const states = {};

    for (const locale of TARGETS) {
      const translatedPath = join(HELP_DIR, locale, article.file);
      const recordedHash = record.translated?.[locale];
      let state;
      if (!existsSync(translatedPath) || !recordedHash) state = 'missing';
      else if (recordedHash !== enHash) state = 'stale';
      else state = 'current';
      states[locale] = state;
      totals[locale][state] += 1;
    }

    rows.push({ id: article.id, file: article.file, states });
  }
}

const SYMBOL = { current: '·', stale: 'S', missing: 'M', 'no-source': '?' };

const needsWork = rows.filter((row) => Object.values(row.states).some((s) => s !== 'current'));

if (verbose || needsWork.length > 0) {
  const width = Math.max(...rows.map((r) => r.id.length), 8);
  console.log(`${'article'.padEnd(width)}  ${TARGETS.join(' ')}`);
  for (const row of verbose ? rows : needsWork) {
    console.log(`${row.id.padEnd(width)}  ${TARGETS.map((l) => SYMBOL[row.states[l]] + ' ').join('').trim()}`);
  }
  console.log('');
  console.log('· current   S stale (English changed since translation)   M missing   ? no English source');
  console.log('');
}

for (const locale of TARGETS) {
  const { current, stale, missing } = totals[locale];
  const total = current + stale + missing;
  console.log(`${locale}: ${current}/${total} current` + (stale ? ` · ${stale} stale` : '') + (missing ? ` · ${missing} missing` : ''));
}

if (missingEnglish > 0) {
  console.log(`\n${missingEnglish} indexed article(s) have no English file — fix index.json first.`);
}

const problems = missingEnglish + TARGETS.reduce((n, l) => n + totals[l].stale + totals[l].missing, 0);
if (problems === 0) console.log('\nAll translations are current.');
else console.log(`\n${problems} translation(s) need attention — run the /help-docs skill to sync them.`);

process.exit(strict && problems > 0 ? 1 : 0);
