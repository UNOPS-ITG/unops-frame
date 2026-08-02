/* Screenshots the token gallery in every theme.
 *
 * A theme regression is a visual fact and cannot be reviewed as a diff of hex
 * values, so this exists to produce the four images a human (or an agent) can
 * actually look at. It also fails loudly on any console error, which is how a
 * broken var() reference or a missing font surfaces.
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { urls } from '../config/ports.mjs'

const BASE = process.env.GALLERY_URL ?? `${urls.frontend}/`
const OUT = process.env.GALLERY_OUT ?? '.artifacts/gallery'
const THEMES = ['light', 'grey', 'dark', 'system']

mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
const problems = []

for (const theme of THEMES) {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 1400 },
    deviceScaleFactor: 2,
    // Exercises the auto branch: with preference "system" and this set to dark,
    // the page must follow the OS rather than silently pinning light.
    colorScheme: theme === 'system' ? 'dark' : 'light',
  })
  const page = await context.newPage()

  page.on('console', (m) => {
    if (m.type() === 'error') problems.push(`[${theme}] console: ${m.text()}`)
  })
  page.on('pageerror', (e) => problems.push(`[${theme}] pageerror: ${e.message}`))

  await page.addInitScript((t) => {
    window.localStorage.setItem('frame-theme', t)
  }, theme)

  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForTimeout(400)

  const applied = await page.evaluate(() => ({
    attr: document.documentElement.getAttribute('data-theme'),
    bg: getComputedStyle(document.body).backgroundColor,
  }))

  // The trap this whole exercise exists to catch: "system" must REMOVE the
  // attribute, not set it to a value that matches no theme block.
  if (theme === 'system' && applied.attr !== null) {
    problems.push(`[system] data-theme should be absent, found "${applied.attr}"`)
  }
  if (theme !== 'system' && applied.attr !== theme) {
    problems.push(`[${theme}] data-theme should be "${theme}", found "${applied.attr}"`)
  }

  await page.screenshot({ path: `${OUT}/${theme}.png`, fullPage: true })
  console.log(`${theme.padEnd(7)} data-theme=${String(applied.attr).padEnd(6)} body-bg=${applied.bg}`)
  await context.close()
}

await browser.close()

if (problems.length) {
  console.error('\nProblems:')
  for (const p of problems) console.error('  ' + p)
  process.exit(1)
}
console.log(`\nOK — four themes rendered clean into ${OUT}/`)
