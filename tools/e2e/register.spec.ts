import { expect, test } from '@playwright/test'

/**
 * The governed register, end to end.
 *
 * These run against a real backend, a real permission library and the Firestore
 * emulator, so they need `npm run seed` and both services up. They are the tests
 * that catch the class of bug the unit suites structurally cannot: a wire
 * contract that changed on one side, a route that moved, a permission rule that
 * is correct in isolation and wrong when a real principal is resolved.
 *
 * Two of the bugs already found this way — an import refused for a
 * row-conditioned grant, and an export whose blob URL was revoked before the
 * browser read it — passed every unit test that existed.
 */

const REGISTER = '/#/w/ws-demo/b/risk/table'
const VIEW = '/#/w/ws-demo/b/risk/v/open-risks'

/** The persona is set before the app loads, because the client reads it when
 * building the request. */
async function as(page: import('@playwright/test').Page, email: string, hash: string) {
  await page.addInitScript((who) => {
    sessionStorage.setItem('frame-dev-persona', who)
  }, email)
  await page.goto(hash)
  await page.waitForSelector('canvas', { timeout: 20_000 })
  await page.waitForTimeout(800)
}

test.describe('the governed register', () => {
  test('states what it is not showing', async ({ page }) => {
    await as(page, 'dev@unops.org', REGISTER)
    const status = page.getByRole('status', { name: 'Register summary' })
    await expect(status).toContainText('withheld')
    await expect(status).toContainText('Owner rationale')
  })

  test('the same saved view shows two people different things', async ({ browser }) => {
    const read = async (email: string) => {
      const context = await browser.newContext()
      const page = await context.newPage()
      await as(page, email, VIEW)
      const text = (await page.getByRole('status', { name: 'Register summary' }).textContent()) ?? ''
      await context.close()
      return text
    }

    const privileged = await read('risk@unops.org')
    const ordinary = await read('dev@unops.org')

    expect(privileged).not.toBe(ordinary)
    expect(ordinary).toContain('withheld')
    expect(privileged).not.toContain('withheld')
  })
})

test.describe('the filter builder', () => {
  test('narrows the register and states the new withheld count', async ({ page }) => {
    await as(page, 'dev@unops.org', REGISTER)
    const status = page.getByRole('status', { name: 'Register summary' })
    const before = await status.textContent()

    await page.getByRole('button', { name: 'Filter' }).click()
    await page.getByRole('button', { name: 'Add condition' }).click()
    await page.getByLabel('Field').selectOption({ label: 'Status' })
    await page.getByLabel('Value').selectOption({ label: 'Open' })
    await page.getByRole('button', { name: 'Apply' }).click()
    await page.waitForTimeout(1_500)

    const after = await status.textContent()
    expect(after).not.toBe(before)
    // The count moves with the filter. A withheld count that did not would be a
    // wrong number the reader trusts.
    expect(after).toContain('withheld')
  })

  test('survives applying, so a half-typed view name is not lost', async ({ page }) => {
    // The page used to blank while refetching, which unmounted the toolbar and
    // took the filter panel with it every time the user pressed Apply.
    await as(page, 'dev@unops.org', REGISTER)
    await page.getByRole('button', { name: 'Filter' }).click()
    await page.getByRole('button', { name: 'Add condition' }).click()
    await page.getByLabel('Value').fill('anything')
    await page.getByRole('button', { name: 'Apply' }).click()
    await page.waitForTimeout(1_500)

    await expect(page.getByLabel('View name')).toBeVisible()
  })

  test('saves a filter as a view that then appears in the list', async ({ page }) => {
    await as(page, 'dev@unops.org', REGISTER)
    await page.getByRole('button', { name: 'Filter' }).click()
    await page.getByRole('button', { name: 'Add condition' }).click()
    await page.getByLabel('Field').selectOption({ label: 'Status' })
    await page.getByLabel('Value').selectOption({ label: 'Open' })

    const name = `E2E ${Date.now()}`
    await page.getByLabel('View name').fill(name)
    await page.getByRole('button', { name: 'Save view' }).click()
    await page.waitForTimeout(1_500)

    await expect(page.getByLabel('View', { exact: true })).toContainText(name)
  })
})

test.describe('import', () => {
  test('previews before it writes, and refuses to write a file with a bad row', async ({ page }) => {
    await as(page, 'dev@unops.org', REGISTER)

    await page.setInputFiles('input[type=file]', {
      name: 'risks.csv',
      mimeType: 'text/csv',
      // One valid row, one missing the required title.
      buffer: Buffer.from('Risk,Status,Exposure (USD)\nGood row,open,1234\n,open,50\n'),
    })

    const preview = page.getByRole('region', { name: 'Import preview' })
    await expect(preview).toContainText('2 rows read')
    await expect(preview).toContainText('1 valid')
    // 1-based including the header, so it matches what the user sees in Excel.
    await expect(preview).toContainText('Line 3')
    // Nothing is written while any row is invalid. Singular, because it is one
    // row — the button used to say "Import 1 rows" and this test asserted it.
    await expect(page.getByRole('button', { name: /^Import 1 row$/ })).toBeDisabled()
  })

  test('names the columns it could not match', async ({ page }) => {
    await as(page, 'dev@unops.org', REGISTER)
    await page.setInputFiles('input[type=file]', {
      name: 'odd.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('Risk,Nonsense\nx,y\n'),
    })
    await expect(page.getByRole('region', { name: 'Import preview' })).toContainText('Nonsense')
  })
})

test.describe('export', () => {
  test('downloads a CSV that says what it does not contain', async ({ page }, testInfo) => {
    await as(page, 'dev@unops.org', REGISTER)

    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 25_000 }),
      page.getByRole('button', { name: 'Export CSV' }).click(),
    ])

    const target = testInfo.outputPath('exported.csv')
    // saveAs rather than path(): headless Chromium reports a blob download as
    // cancelled when a downloadsPath is configured, and path() then throws on a
    // download that in fact completed.
    await download.saveAs(target)
    const text = await import('node:fs').then((fs) => fs.readFileSync(target, 'utf8'))

    // A BOM, or Excel on Windows renders every non-ASCII name as mojibake and
    // the user concludes the export is broken.
    expect(text.charCodeAt(0)).toBe(0xfeff)
    // The withheld count travels with the file, because a CSV has nowhere else
    // to put it and the person who exports is the person who forwards.
    expect(text).toMatch(/further row\(s\)/)
    // A withheld field exports as withheld, never as blank.
    expect(text).toContain('(withheld)')
  })
})
