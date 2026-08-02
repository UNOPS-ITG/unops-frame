import { expect, test } from '@playwright/test'

/**
 * GR-9: the grid performance harness, and the only proof the canvas actually
 * paints.
 *
 * Unit tests cover the cell mapping, but a canvas grid can pass every one of
 * them and render a blank rectangle — `fillStyle` assignment fails silently on
 * an unparseable colour, and jsdom has no canvas at all. So this suite reads
 * real pixels out of a real browser.
 *
 * The budgets below are deliberately generous relative to the target. They
 * exist to catch a regression of the "we accidentally re-render every row on
 * scroll" kind, not to police a few milliseconds — a tight budget on shared CI
 * hardware produces flakes, and a flaky perf test gets muted, at which point it
 * protects nothing.
 */

const APP = 'http://localhost:6300/'

test.describe('the grid renders', () => {
  test('paints a non-blank canvas in brand colours', async ({ page }) => {
    await page.goto(APP)
    const canvas = page.locator('canvas').first()
    await expect(canvas).toBeVisible()

    // Read the pixels back. A grid that threw during paint, or assigned an
    // unparseable fillStyle, leaves a uniform rectangle — which every
    // DOM-level assertion would still call "rendered".
    const distinctColours = await page.evaluate(() => {
      const el = document.querySelector('canvas') as HTMLCanvasElement | null
      if (!el) return 0
      const ctx = el.getContext('2d')
      if (!ctx) return 0
      const { data } = ctx.getImageData(0, 0, Math.min(el.width, 800), Math.min(el.height, 400))
      const seen = new Set<string>()
      for (let i = 0; i < data.length; i += 4) {
        seen.add(`${data[i]},${data[i + 1]},${data[i + 2]}`)
      }
      return seen.size
    })

    // Text antialiasing alone produces dozens of shades; a blank canvas gives 1.
    expect(distinctColours).toBeGreaterThan(10)
  })

  test('states the withheld count where a screen reader will read it', async ({ page }) => {
    // PM-5 requires the count to be STATED, not merely available: a reader who
    // cannot see that rows were withheld reports the visible total as truth.
    await page.goto(APP)
    const status = page.getByRole('status')
    await expect(status).toContainText('withheld')
    await expect(status).toContainText('Risk register')
  })

  test('follows a theme change rather than staying on stale colours', async ({ page }) => {
    await page.goto(APP)
    // Driven through the theme store, the way the app does it. Setting
    // `data-theme` directly would repaint the DOM and leave the canvas
    // untouched — proving nothing except that CSS works.
    const sample = async () =>
      page.evaluate(() => {
        const el = document.querySelector('canvas') as HTMLCanvasElement
        const ctx = el.getContext('2d')!
        return Array.from(ctx.getImageData(2, 2, 1, 1).data).join(',')
      })

    await page.getByRole('button', { name: 'light', exact: true }).click()
    await page.waitForTimeout(400)
    const light = await sample()

    await page.getByRole('button', { name: 'dark', exact: true }).click()
    await page.waitForTimeout(400)
    const dark = await sample()

    // The canvas reads tokens once per theme change against a detached probe.
    // If that read never happens, these are identical.
    expect(dark, 'the canvas kept its light-theme colours').not.toBe(light)
  })
})

test.describe('GR-9 budgets', () => {
  for (const rows of [1_000, 10_000, 50_000]) {
    test(`stays responsive at ${rows.toLocaleString()} rows`, async ({ page }) => {
      await page.goto(APP)
      await page.getByRole('button', { name: `${rows.toLocaleString()} rows` }).click()
      await page.waitForTimeout(200)

      const canvas = page.locator('canvas').first()
      const box = await canvas.boundingBox()
      expect(box).not.toBeNull()

      const centre = { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2 }
      await page.mouse.move(centre.x, centre.y)

      // Warm the scroll path so the first frame's compile cost is not counted
      // as a rendering cost.
      await page.mouse.wheel(0, 400)
      await page.waitForTimeout(120)

      const started = Date.now()
      for (let i = 0; i < 20; i++) {
        await page.mouse.wheel(0, 600)
      }
      await page.waitForTimeout(120)
      const elapsed = Date.now() - started

      // 20 wheel events. Row count must not change this: the grid draws a
      // window, so a budget that scaled with the register would mean it does
      // not.
      expect(elapsed, `${rows} rows took ${elapsed}ms`).toBeLessThan(3_000)

      // And it is still painting afterwards, rather than having thrown.
      const painted = await page.evaluate(() => {
        const el = document.querySelector('canvas') as HTMLCanvasElement
        const ctx = el.getContext('2d')!
        const { data } = ctx.getImageData(0, 0, 400, 200)
        const seen = new Set<string>()
        for (let i = 0; i < data.length; i += 4) seen.add(`${data[i]},${data[i + 1]},${data[i + 2]}`)
        return seen.size
      })
      expect(painted).toBeGreaterThan(10)
    })
  }

  test('reports no console errors while scrolling', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (m) => {
      if (m.type() === 'error') errors.push(m.text())
    })
    page.on('pageerror', (e) => errors.push(e.message))

    await page.goto(APP)
    await page.getByRole('button', { name: '10,000 rows' }).click()
    const box = await page.locator('canvas').first().boundingBox()
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2)
    for (let i = 0; i < 10; i++) await page.mouse.wheel(0, 800)
    await page.waitForTimeout(300)

    expect(errors).toEqual([])
  })
})
