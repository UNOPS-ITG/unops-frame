#!/usr/bin/env node
/**
 * Locale catalog parity check.
 *
 * Verifies that every non-English catalog (es/fr/ru/ar/zh) has exactly the keys
 * of the English source — accounting for language-specific plural forms:
 * a plural key group in en (`foo_one`/`foo_other`) must appear in each locale
 * with THAT language's CLDR plural categories (ru: one/few/many/other;
 * ar: zero/one/two/few/many/other; zh: other only; es/fr: one/many?/other — we
 * require the categories Intl.PluralRules reports for the locale, except
 * optional ones that i18next falls back for; missing REQUIRED categories fail
 * the build).
 *
 * Run via `npm run build` (fails the build on mismatch) or directly:
 *   node scripts/check-locales.mjs
 */
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const LOCALES_DIR = join(ROOT, 'src', 'locales');
const SOURCE = 'en';
const TARGETS = ['es', 'fr', 'ru', 'ar', 'zh'];
const NAMESPACES = ['common', 'case', 'admin', 'apps'];

const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/;

function flatten(obj, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object') flatten(v, key, out);
    else out[key] = v;
  }
  return out;
}

/** `{{var}}` interpolation names used by a string. A translated placeholder
 *  name silently renders as literal text at runtime, so names must survive
 *  translation verbatim. */
function placeholders(value) {
  if (typeof value !== 'string') return new Set();
  return new Set([...value.matchAll(/\{\{\s*([^}\s,]+)/g)].map((m) => m[1]));
}

/** `<1>…</1>` markup tags consumed by <Trans>. Losing or renumbering one
 *  drops the inline element (a link, a <strong>) from the rendered sentence. */
function transTags(value) {
  if (typeof value !== 'string') return new Set();
  return new Set([...value.matchAll(/<\/?(\d+)>/g)].map((m) => m[1]));
}

const setsEqual = (a, b) => a.size === b.size && [...a].every((x) => b.has(x));

/** Group flat keys into { singular: Set, pluralBases: Map<base, Set<category>> }. */
function classify(flat) {
  const singular = new Set();
  const pluralBases = new Map();
  for (const key of Object.keys(flat)) {
    const m = key.match(PLURAL_SUFFIX);
    if (m) {
      const base = key.slice(0, -m[0].length);
      if (!pluralBases.has(base)) pluralBases.set(base, new Set());
      pluralBases.get(base).add(m[1]);
    } else {
      singular.add(key);
    }
  }
  return { singular, pluralBases };
}

function requiredCategories(locale) {
  return new Set(new Intl.PluralRules(locale).resolvedOptions().pluralCategories);
}

let failed = false;
const problems = [];

for (const ns of NAMESPACES) {
  const enPath = join(LOCALES_DIR, SOURCE, `${ns}.json`);
  if (!existsSync(enPath)) {
    problems.push(`missing source catalog: ${SOURCE}/${ns}.json`);
    failed = true;
    continue;
  }
  const enFlat = flatten(JSON.parse(readFileSync(enPath, 'utf8')));
  const en = classify(enFlat);

  for (const locale of TARGETS) {
    const path = join(LOCALES_DIR, locale, `${ns}.json`);
    if (!existsSync(path)) {
      problems.push(`missing catalog: ${locale}/${ns}.json`);
      failed = true;
      continue;
    }
    const locFlat = flatten(JSON.parse(readFileSync(path, 'utf8')));
    const loc = classify(locFlat);

    // --- interpolation + markup integrity -----------------------------------
    // Non-plural keys must carry exactly en's placeholders and Trans tags.
    for (const key of en.singular) {
      if (!loc.singular.has(key)) continue; // already reported as missing
      const want = placeholders(enFlat[key]);
      const got = placeholders(locFlat[key]);
      if (!setsEqual(want, got)) {
        problems.push(
          `${locale}/${ns}: "${key}" placeholder drift — en {${[...want]}} vs {${[...got]}}`,
        );
        failed = true;
      }
      const wantTags = transTags(enFlat[key]);
      const gotTags = transTags(locFlat[key]);
      if (!setsEqual(wantTags, gotTags)) {
        problems.push(
          `${locale}/${ns}: "${key}" Trans tag drift — en <${[...wantTags]}> vs <${[...gotTags]}>`,
        );
        failed = true;
      }
    }
    // Plural forms are compared against the union over en's forms, ignoring
    // `count`: Arabic (and others) may legitimately encode small counts in the
    // noun rather than a numeral, so a form may omit {{count}} by design.
    for (const [base, cats] of en.pluralBases) {
      const want = new Set();
      const wantTags = new Set();
      for (const c of cats) {
        for (const p of placeholders(enFlat[`${base}_${c}`])) want.add(p);
        for (const t of transTags(enFlat[`${base}_${c}`])) wantTags.add(t);
      }
      want.delete('count');
      for (const c of loc.pluralBases.get(base) ?? []) {
        const form = `${base}_${c}`;
        const got = placeholders(locFlat[form]);
        got.delete('count');
        if (!setsEqual(want, got)) {
          problems.push(
            `${locale}/${ns}: "${form}" placeholder drift — en {${[...want]}} vs {${[...got]}}`,
          );
          failed = true;
        }
        if (!setsEqual(wantTags, transTags(locFlat[form]))) {
          problems.push(`${locale}/${ns}: "${form}" Trans tag drift`);
          failed = true;
        }
      }
    }

    for (const key of en.singular) {
      if (!loc.singular.has(key)) {
        problems.push(`${locale}/${ns}: missing key "${key}"`);
        failed = true;
      }
    }
    for (const key of loc.singular) {
      if (!en.singular.has(key) && !en.pluralBases.has(key)) {
        problems.push(`${locale}/${ns}: extra key "${key}" not in en`);
        failed = true;
      }
    }

    const required = requiredCategories(locale);
    for (const [base, enCats] of en.pluralBases) {
      const locCats = loc.pluralBases.get(base);
      if (!locCats) {
        problems.push(`${locale}/${ns}: missing plural group "${base}_*"`);
        failed = true;
        continue;
      }
      for (const cat of required) {
        // "zero"/"two" are only required where the locale's rules define them.
        if (!locCats.has(cat)) {
          problems.push(`${locale}/${ns}: plural "${base}" missing _${cat}`);
          failed = true;
        }
      }
      void enCats;
    }
    for (const base of loc.pluralBases.keys()) {
      if (!en.pluralBases.has(base) && !en.singular.has(base)) {
        problems.push(`${locale}/${ns}: extra plural group "${base}_*" not in en`);
        failed = true;
      }
    }
  }
}

if (failed) {
  console.error(`check-locales: ${problems.length} problem(s):`);
  for (const p of problems) console.error(`  - ${p}`);
  process.exit(1);
}
console.log('check-locales: all locale catalogs are in parity with en.');
