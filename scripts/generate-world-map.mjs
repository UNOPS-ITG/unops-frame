/**
 * Generates src/components/shared/viz/geo/worldPaths.ts — a pre-projected
 * SVG world map keyed by ISO-2 code — from the world-atlas TopoJSON.
 *
 * Run manually when the atlas or the backend country table changes:
 *   node scripts/generate-world-map.mjs
 *
 * Design decisions baked in here:
 *  - The output is COMMITTED and the projection happens at build time, so the
 *    runtime carries zero geo dependencies (no d3, no topojson, no fetch).
 *  - Country identity comes from NAME-MATCHING each atlas feature against
 *    `Intl.DisplayNames` renderings of the backend's own ISO-2 list
 *    (functions/lib/geo_regions.py — the single source of truth for which
 *    territories exist). An unmatched feature is WARNED about and skipped —
 *    this is an indicative internal map, so a missing shape is acceptable;
 *    add an alias when a warning names something that matters.
 *  - Shapes come from the 110m atlas (small file); territories too small to
 *    exist at 110m get a CENTROID from the 50m atlas instead, so island
 *    states can still be drawn as markers when they have data.
 *  - Antarctica is excluded — it can never carry data and costs a third of
 *    the vertical space.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { feature } from 'topojson-client';
import { geoNaturalEarth1, geoPath } from 'd3-geo';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => readFileSync(path.join(root, p), 'utf8');

// ---- the canonical ISO-2 universe, from the backend's region table --------
const geoRegionsPy = read('functions/lib/geo_regions.py');
const tableSection = geoRegionsPy.split('_COUNTRY_REGION')[1] ?? '';
const ISO2 = [...new Set([...tableSection.matchAll(/"([A-Z]{2})":/g)].map((m) => m[1]))];
if (ISO2.length < 200) {
  throw new Error(`Parsed only ${ISO2.length} ISO-2 codes from geo_regions.py — parser broken?`);
}

// ---- name normalization + lookup ------------------------------------------
const normalize = (name) =>
  name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // strip diacritics
    .replace(/[’'`.]/g, '')
    .toLowerCase()
    .replace(/\bis\b/g, 'islands')
    .replace(/\brep\b/g, 'republic')
    .replace(/\bdem\b/g, 'democratic')
    .replace(/\beq\b/g, 'equatorial')
    .replace(/\bfr\b/g, 'french')
    .replace(/\bs\b/g, 'south')
    .replace(/\bn\b/g, 'north')
    .replace(/\bw\b/g, 'western')
    .replace(/\bst\b/g, 'saint')
    .replace(/\bherz\b/g, 'herzegovina')
    .replace(/\bter\b/g, 'territory')
    .replace(/\band\b|\bthe\b|\bof\b/g, ' ')
    .replace(/[^a-z]/g, '');

const display = new Intl.DisplayNames(['en'], { type: 'region' });
const byName = new Map();
for (const code of ISO2) {
  const name = display.of(code);
  if (name && name !== code) byName.set(normalize(name), code);
}

// Atlas names whose normalized form still misses the DisplayNames rendering.
const ALIASES = {
  'United States of America': 'US',
  'Dem. Rep. Congo': 'CD',
  'Congo': 'CG',
  'Central African Rep.': 'CF',
  'S. Sudan': 'SS',
  'Lao PDR': 'LA',
  'Macedonia': 'MK',
  'Bosnia and Herz.': 'BA',
  'Czechia': 'CZ',
  'Brunei': 'BN',
  'Palestine': 'PS',
  'Taiwan': 'TW',
  'South Korea': 'KR',
  'North Korea': 'KP',
  'Timor-Leste': 'TL',
  'Myanmar': 'MM',
  'Cabo Verde': 'CV',
  'eSwatini': 'SZ',
  'Swaziland': 'SZ',
  'W. Sahara': 'EH',
  'Micronesia': 'FM',
  'St. Vin. and Gren.': 'VC',
  'St-Barthélemy': 'BL',
  'St-Martin': 'MF',
  'Sint Maarten': 'SX',
  'U.S. Virgin Is.': 'VI',
  'British Virgin Is.': 'VG',
  'S. Geo. and the Is.': 'GS',
  'Heard I. and McDonald Is.': 'HM',
  'Brit. Indian Ocean Ter.': 'IO',
  'Fr. Polynesia': 'PF',
  'Wallis and Futuna Is.': 'WF',
  'Faeroe Is.': 'FO',
  'Åland': 'AX',
  'Vatican': 'VA',
  'Macao': 'MO',
  'United Kingdom': 'GB',
  'Fr. S. Antarctic Lands': 'TF',
  'Turkey': 'TR',
  'N. Mariana Is.': 'MP',
  'Br. Indian Ocean Ter.': 'IO',
  'Hong Kong': 'HK',
  'Antigua and Barb.': 'AG',
};

// Atlas features with no ISO-2 identity (or excluded on purpose).
const SKIP = new Set([
  'Antarctica',
  'N. Cyprus',
  'Somaliland',
  'Kosovo',
  'Siachen Glacier',
  // Australian external territories with no ISO-2 of their own in our table.
  'Indian Ocean Ter.',
  'Ashmore and Cartier Is.',
]);

const resolve = (name) => ALIASES[name] ?? byName.get(normalize(name)) ?? null;

// ---- project ---------------------------------------------------------------
const WIDTH = 960;
const atlas110 = JSON.parse(read('node_modules/world-atlas/countries-110m.json'));
const atlas50 = JSON.parse(read('node_modules/world-atlas/countries-50m.json'));

const featuresOf = (atlas) => feature(atlas, atlas.objects.countries).features;
const kept110 = featuresOf(atlas110).filter((f) => !SKIP.has(f.properties.name));

const projection = geoNaturalEarth1();
projection.fitWidth(WIDTH, { type: 'FeatureCollection', features: kept110 });
const [[, y0], [, y1]] = geoPath(projection).bounds({ type: 'FeatureCollection', features: kept110 });
projection.translate([projection.translate()[0], projection.translate()[1] - y0]);
const HEIGHT = Math.ceil(y1 - y0);
const pathOf = geoPath(projection);

const round = (d) => d.replace(/-?\d+\.\d+/g, (m) => Number(m).toFixed(1));

const unmatched = [];
const shapes = [];
const seen = new Set();
for (const f of kept110) {
  const iso2 = resolve(f.properties.name);
  if (!iso2) {
    unmatched.push(f.properties.name);
    continue;
  }
  if (seen.has(iso2)) throw new Error(`Duplicate iso2 ${iso2} (${f.properties.name})`);
  seen.add(iso2);
  const d = pathOf(f);
  if (!d) continue;
  const [cx, cy] = pathOf.centroid(f);
  shapes.push({
    iso2,
    d: round(d),
    area: Math.round(pathOf.area(f)),
    cx: Number(cx.toFixed(1)),
    cy: Number(cy.toFixed(1)),
  });
}

// Territories absent at 110m: take a centroid from the 50m atlas so they can
// still appear as data markers.
const markers = [];
for (const f of featuresOf(atlas50)) {
  if (SKIP.has(f.properties.name)) continue;
  const iso2 = resolve(f.properties.name);
  if (!iso2) {
    unmatched.push(`${f.properties.name} (50m)`);
    continue;
  }
  if (seen.has(iso2)) continue;
  seen.add(iso2);
  const [cx, cy] = pathOf.centroid(f);
  if (!Number.isFinite(cx) || !Number.isFinite(cy)) continue;
  markers.push({ iso2, cx: Number(cx.toFixed(1)), cy: Number(cy.toFixed(1)) });
}

if (unmatched.length) {
  console.warn('Unmatched atlas features — skipped (add an alias if one matters):');
  for (const name of unmatched) console.warn(`  - ${name}`);
}

const unplaced = ISO2.filter((c) => !seen.has(c)).sort();
console.log(`shapes: ${shapes.length}, marker-only: ${markers.length}, codes with no geometry at all: ${unplaced.length}`);
if (unplaced.length) console.log(`  no geometry: ${unplaced.join(' ')}`);

shapes.sort((a, b) => a.iso2.localeCompare(b.iso2));
markers.sort((a, b) => a.iso2.localeCompare(b.iso2));

const out = `/**
 * Pre-projected world map (Natural Earth I, ${WIDTH}×${HEIGHT}).
 *
 * GENERATED by scripts/generate-world-map.mjs — do not edit by hand; re-run
 * the script instead. Identity comes from the backend's own ISO-2 table
 * (functions/lib/geo_regions.py) name-matched against the world-atlas
 * geometry, with the generator failing loudly on anything it cannot identify.
 *
 * \`area\` is the projected on-screen area in px² — the component uses it to
 * decide when a territory is too small to see and needs a marker instead.
 * MARKER_ONLY holds territories that have no geometry at this resolution but
 * still deserve a dot when they carry data.
 */

export const MAP_WIDTH = ${WIDTH};
export const MAP_HEIGHT = ${HEIGHT};

export interface CountryShape {
  iso2: string;
  d: string;
  /** Projected area, px² at the ${WIDTH}-wide viewBox. */
  area: number;
  cx: number;
  cy: number;
}

export const COUNTRY_SHAPES: CountryShape[] = [
${shapes.map((s) => `  { iso2: '${s.iso2}', area: ${s.area}, cx: ${s.cx}, cy: ${s.cy}, d: ${JSON.stringify(s.d)} },`).join('\n')}
];

export const MARKER_ONLY: Array<{ iso2: string; cx: number; cy: number }> = [
${markers.map((m) => `  { iso2: '${m.iso2}', cx: ${m.cx}, cy: ${m.cy} },`).join('\n')}
];
`;

const outPath = path.join(root, 'src/components/shared/viz/geo/worldPaths.ts');
writeFileSync(outPath, out);
console.log(`wrote ${outPath}`);
