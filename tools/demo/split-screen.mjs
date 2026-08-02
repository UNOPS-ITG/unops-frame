#!/usr/bin/env node
/**
 * The Milestone 1 demonstration, captured.
 *
 * Two people open the SAME saved view at the SAME URL and legitimately see
 * different rows and different columns. This script drives both browsers, reads
 * the annotations back, and asserts the difference is real — so the screenshot
 * is evidence rather than an illustration.
 *
 * It fails loudly if the two views agree. A demo that silently degrades to
 * "both users see the same thing" is worse than no demo, because it is the
 * exact failure the milestone exists to rule out and it looks like success.
 */

import { chromium } from '@playwright/test'
import { ports } from '../../config/ports.mjs'

const BASE = `http://localhost:${ports.frontend}`
const URL = `${BASE}/#view/ws-demo/risk/open-risks`
const OUT = process.argv[2] ?? '.artifacts'

const PEOPLE = [
  { email: 'risk@unops.org', label: 'Risk team' },
  { email: 'dev@unops.org', label: 'Programme staff' },
]

async function capture(browser, person) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 760 } })
  const page = await context.newPage()

  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text())
  })

  // Set before the app loads: the client reads it when building the request.
  await page.addInitScript((email) => {
    sessionStorage.setItem('frame-dev-persona', email)
  }, person.email)

  await page.goto(URL)
  await page.waitForSelector('canvas', { timeout: 15_000 })
  await page.waitForTimeout(1_500)

  const announcement = await page.getByRole('status').textContent()
  await page.screenshot({ path: `${OUT}/m1-${person.email.split('@')[0]}.png` })
  await context.close()

  return { ...person, announcement, errors }
}

function parse(announcement) {
  const shown = /(\d[\d,]*) rows shown/.exec(announcement ?? '')
  const withheld = /(\d[\d,]*) withheld/.exec(announcement ?? '')
  const columns = /Withheld columns: (.+)$/.exec(announcement ?? '')
  const toNumber = (m) => (m ? Number(m[1].replace(/,/g, '')) : 0)
  return {
    shown: toNumber(shown),
    withheld: toNumber(withheld),
    withheldColumns: columns ? columns[1] : '',
  }
}

const browser = await chromium.launch()
const results = []
for (const person of PEOPLE) results.push(await capture(browser, person))
await browser.close()

let failed = false
console.log(`\nOne URL: ${URL}\n`)
for (const r of results) {
  const p = parse(r.announcement)
  console.log(`  ${r.label.padEnd(18)} ${r.email}`)
  console.log(`      rows shown:       ${p.shown}`)
  console.log(`      rows withheld:    ${p.withheld}`)
  console.log(`      withheld columns: ${p.withheldColumns || '(none)'}`)
  if (r.errors.length > 0) {
    failed = true
    console.log(`      CONSOLE ERRORS:   ${r.errors.join(' | ')}`)
  }
  console.log()
}

const [privileged, ordinary] = results.map((r) => parse(r.announcement))

const checks = [
  ['the two people see a different number of rows', privileged.shown !== ordinary.shown],
  ['the less-privileged reader is told rows were withheld', ordinary.withheld > 0],
  ['the privileged reader has nothing withheld', privileged.withheld === 0],
  ['a whole column is withheld from one and not the other',
    ordinary.withheldColumns !== '' && privileged.withheldColumns === ''],
]

for (const [claim, held] of checks) {
  console.log(`  ${held ? 'OK  ' : 'FAIL'}  ${claim}`)
  if (!held) failed = true
}

console.log(`\nScreenshots in ${OUT}/`)
if (failed) {
  console.error('\nThe demonstration did not hold. This is the failure the milestone rules out.')
  process.exitCode = 1
}
