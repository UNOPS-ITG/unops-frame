import { expect, test } from '@playwright/test'

/**
 * The application around the grid.
 *
 * The register suite covers what the grid does; this covers whether a person
 * can get to it, move between the surfaces, and read what each one is telling
 * them. Those are the parts that fail silently — a route that resolves to the
 * wrong page still renders *something*, and nothing else notices.
 *
 * Needs `npm run seed` and both services up, like the register suite.
 */

const WORKSPACE = '/#/w/ws-demo'
const REGISTER = '/#/w/ws-demo/b/risk/table'

async function as(page: import('@playwright/test').Page, email: string, hash: string) {
  await page.addInitScript((who) => {
    sessionStorage.setItem('frame-dev-persona', who)
  }, email)
  await page.goto(hash)
}

test.describe('the shell', () => {
  test('lists the workspace registers and opens one', async ({ page }) => {
    await as(page, 'dev@unops.org', WORKSPACE)

    const sidebar = page.getByRole('navigation', { name: 'Workspace' })
    await expect(sidebar.getByText('Risk register')).toBeVisible()

    await page.getByRole('link', { name: /Risk register/ }).first().click()

    // A register LANDS as an app — the Overview, not the grid. The grid is
    // the Table tab, one click away. (Owner decision at the first vision
    // checkpoint: "user clicks risk register, sees a giant grid" was the
    // failure this ordering exists to prevent.)
    await page.waitForSelector('.overview', { timeout: 20_000 })

    // The header carries the Blueprint's own name rather than the route's noun.
    // It comes from the register list the shell already loaded, so it must not
    // wait for the page.
    await expect(page.getByRole('heading', { name: 'Risk register' })).toBeVisible()

    await page.getByRole('link', { name: 'Risks', exact: true }).click()
    await page.waitForSelector('canvas', { timeout: 20_000 })
  })

  test('a stale link still lands somewhere useful', async ({ page }) => {
    // The pre-shell URL shapes are printed by the seed script and pasted into
    // chat by people. A link that used to work and now silently lands somewhere
    // else is worse than one that 404s.
    await as(page, 'dev@unops.org', '/#register/ws-demo/risk')
    await page.waitForSelector('canvas', { timeout: 20_000 })
    await expect(page.getByRole('heading', { name: 'Risk register' })).toBeVisible()
  })

  test('collapses to an icon rail and remembers it', async ({ page }) => {
    // Bob's pattern, deliberately: the same panel glyph, a 56px rail that
    // keeps every destination one click away, and a persisted preference.
    await as(page, 'dev@unops.org', WORKSPACE)
    const sidebar = page.getByRole('navigation', { name: 'Workspace' })
    await expect(sidebar.getByText('Apps')).toBeVisible()

    await page.getByRole('button', { name: 'Collapse sidebar' }).click()
    await expect(sidebar.getByText('Apps')).toBeHidden()
    // Destinations survive as labelled icons, not disappear.
    await expect(sidebar.getByRole('link', { name: 'Corporate data' })).toBeVisible()

    await page.reload()
    await expect(page.getByRole('button', { name: 'Expand sidebar' })).toBeVisible()

    await page.getByRole('button', { name: 'Expand sidebar' }).click()
    await expect(sidebar.getByText('Apps')).toBeVisible()
  })

  test('the brand and the Home item both lead home', async ({ page }) => {
    await as(page, 'dev@unops.org', REGISTER)
    await page.waitForSelector('canvas', { timeout: 20_000 })

    // Two ways home, both labelled "Home": the nav item and the brand.
    await page.locator('.sidebar__scroll').getByRole('link', { name: 'Home', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Your apps' })).toBeVisible()

    await page.goto(REGISTER)
    await page.waitForSelector('canvas', { timeout: 20_000 })
    await page.locator('.sidebar__brand').click()
    await expect(page.getByRole('heading', { name: 'Your apps' })).toBeVisible()
  })

  test('an unrecognised route lands one level up rather than on an error', async ({ page }) => {
    await as(page, 'dev@unops.org', '/#/nonsense/here')
    await expect(page.getByRole('heading', { name: 'Workspace' })).toBeVisible()
  })
})

test.describe('the fields page', () => {
  test('explains the register from its compiled metadata', async ({ page }) => {
    await as(page, 'dev@unops.org', REGISTER)
    await page.waitForSelector('canvas', { timeout: 20_000 })
    await page.getByRole('link', { name: 'Fields' }).click()

    const table = page.getByRole('table')
    await expect(table).toContainText('Owner rationale')
    // The stable field id, which is what an API caller and a CSV header must
    // match exactly — and which is never case-transformed on the wire.
    await expect(table).toContainText('rationale')
    // Sensitivity is shown rather than implied by the value being missing.
    await expect(table).toContainText('sensitivity 2')
  })
})

test.describe('the row detail panel', () => {
  test('opens on request and says the word "withheld"', async ({ page }) => {
    await as(page, 'dev@unops.org', REGISTER)
    await page.waitForSelector('canvas', { timeout: 20_000 })
    await page.waitForTimeout(800)

    await page.getByRole('button', { name: 'Details' }).click()
    const panel = page.getByRole('complementary', { name: 'Row detail' })
    await expect(panel).toBeVisible()

    // Nothing selected yet: it says so rather than rendering an empty form.
    await expect(panel).toContainText('Select a row')

    const box = await page.locator('canvas').first().boundingBox()
    await page.mouse.click(box!.x + 120, box!.y + 120)
    await page.waitForTimeout(400)

    // The grid can only afford an em-dash. Here there is room for the word, and
    // that is the difference between a reader knowing a value exists and
    // assuming none was recorded.
    await expect(panel).toContainText('Withheld')
    // An unrecorded value is not the same fact, and is not styled the same.
    await expect(panel).toContainText('Not recorded')
  })
})

test.describe('the corporate catalogue', () => {
  test('states the connection and searches on the server', async ({ page }) => {
    await as(page, 'dev@unops.org', '/#/w/ws-demo/corporate')

    await expect(page.getByText(/BigQuery (not )?connected/)).toBeVisible()

    // The section count specifically — the domain group headers also end in
    // "dimensions" now, so a bare text match resolves to ten elements.
    const count = page.locator('.corporate__count').first()
    await expect(count).toHaveText(/^(\d+) of \1 dimensions$/, { timeout: 20_000 })

    await page.getByLabel('Search the catalogue').fill('agency')

    // A retrying assertion rather than a fixed wait. The narrowing is a
    // debounce plus a round trip over a real catalogue, and a sleep long enough
    // to be safe on a loaded machine is a sleep paid on every green run.
    await expect(count).toHaveText(/^(?!(\d+) of \1 )\d+ of \d+ dimensions$/, {
      timeout: 15_000,
    })
  })

  test('says why a relation cannot be bound rather than hiding it', async ({ page }) => {
    // "Why can I not pick from this?" is otherwise unanswerable without
    // re-running a probe with credentials the asker does not have.
    await as(page, 'dev@unops.org', '/#/w/ws-demo/corporate')
    await expect(page.locator('.corporate__count').first()).toBeVisible({ timeout: 20_000 })

    // Searching opens the matched domain sections; cards live inside them now.
    // Wait for the NARROWED count before clicking: until the search fetch
    // lands, the open sections still show the previous full list, and a click
    // on a card from that render targets a component the refetch is about to
    // unmount — the detail opens and then vanishes under the test.
    await page.getByLabel('Search the catalogue').fill('absence balance')
    await expect(page.locator('.corporate__count').first()).toHaveText(/^1 of /, {
      timeout: 15_000,
    })
    const card = page.locator('.relation__trigger').first()
    await card.click()

    const detail = page.locator('.relation__detail').first()
    await expect(detail).toBeVisible()
    // The greeting is a human sentence; the probe transcript is one click away.
    await expect(detail).toContainText(/resolve live|snapshot/)
    await detail.getByText('Why this classification?').click()
    await expect(detail).toContainText(/floor principal|probe|policy/)
  })
})

test.describe('adding a row', () => {
  test('creates through the one write path and offers only writable fields', async ({ page }) => {
    await as(page, 'dev@unops.org', REGISTER)
    await page.waitForSelector('canvas', { timeout: 20_000 })
    await page.waitForTimeout(800)

    await page.getByRole('button', { name: 'New row' }).click()
    const dialog = page.getByRole('form', { name: /Add a row/ })
    await expect(dialog).toBeVisible()

    // Band 2, and this persona's grant caps at band 1. Absent rather than
    // disabled: a disabled input for a field nobody will ever be allowed to
    // fill is a permanent, unexplained dead end.
    await expect(dialog.getByLabel('Owner rationale')).toHaveCount(0)

    // Offered even though the row does not require it. A permission grant may
    // be conditioned on ANY field — this register's create grant is conditioned
    // on exposure, so a dialog that omitted it made creation impossible for a
    // reason the user could not see.
    await expect(dialog.getByLabel('Exposure (USD)')).toBeVisible()

    const title = `E2E ${Date.now()}`
    await dialog.getByLabel('Risk').fill(title)
    await dialog.getByLabel('Status').selectOption({ label: 'Open' })
    await dialog.getByLabel('Exposure (USD)').fill('4200')
    await page.getByRole('button', { name: 'Add row' }).click()

    await expect(dialog).toBeHidden({ timeout: 15_000 })
  })

  test('reports a refusal against the field rather than as a dead end', async ({ page }) => {
    await as(page, 'dev@unops.org', REGISTER)
    await page.waitForSelector('canvas', { timeout: 20_000 })
    await page.waitForTimeout(800)

    await page.getByRole('button', { name: 'New row' }).click()
    const dialog = page.getByRole('form', { name: /Add a row/ })

    // Above the register's declared maximum. The server refuses it and the
    // dialog stays open carrying the message — a create that vanished with an
    // error elsewhere would lose everything typed.
    await dialog.getByLabel('Risk').fill('Refused on purpose')
    await dialog.getByLabel('Exposure (USD)').fill('999999999')
    await page.getByRole('button', { name: 'Add row' }).click()

    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('alert').first()).toBeVisible({ timeout: 15_000 })
  })
})
