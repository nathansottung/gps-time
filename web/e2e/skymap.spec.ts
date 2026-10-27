import { expect, test } from '@playwright/test'
import { auditDesign, TYPE_SCALE } from './design-audit'
import { auditLayout } from './layout-audit'

// GNSS & Site → Sky Obstruction: the learned map from the station (demo data), shaded by class or
// C/N₀, the sectors and the satellite losses; gone in hidden mode. Administration → Capability record:
// the sky-quality opt-in.

const clean = async (p: import('@playwright/test').Page, design: boolean) => {
  await p.waitForTimeout(300)
  const layout = await p.evaluate(auditLayout)
  expect(layout, layout.map(f => `${f.kind}: ${f.where} — ${f.detail}`).join('\n')).toEqual([])
  if (design) {
    const d = await p.evaluate(auditDesign, TYPE_SCALE)
    expect(d, d.map(f => `${f.kind}: ${f.where} — ${f.detail}`).join('\n')).toEqual([])
  }
}

for (const width of [360, 768, 1280]) {
  test.describe(`${width} px`, () => {
    test.use({ viewport: { width, height: 900 } })

    test('the learned sky-obstruction map', async ({ page: p }) => {
      await p.goto('./?source=demo#gnss')
      await p.getByRole('tab', { name: 'Sky Obstruction' }).click()
      const map = p.getByRole('img', { name: /Learned sky-obstruction map/ })
      await expect(map).toBeVisible()
      expect(await map.locator('path').count()).toBeGreaterThan(400)
      await expect(p.getByText('Expected obstruction below ~30°')).toBeVisible()
      await expect(p.getByText(/^Learned over 12 days/)).toBeVisible()
      await expect(p.getByText(/3 expected, 1 not explained/)).toBeVisible()
      await expect(p.getByRole('cell', { name: 'NOT EXPLAINED' })).toBeVisible()
      await p.getByRole('button', { name: 'C/N₀' }).click()
      await expect(p.getByText('mean C/N₀ per cell')).toBeVisible()
      await clean(p, width === 1280)
    })

    test('the sky-quality opt-in and hidden mode', async ({ page: p }) => {
      await p.goto('./?source=demo#admin')
      await p.waitForSelector('main .page-enter')
      const row = p.getByText('Sky quality in the record').locator('..')
      await expect(row).toContainText('not included')
      await p.getByRole('switch', { name: 'Include the sky-quality summary' }).click()
      await expect(row).toContainText('learned, 12 days')
      await clean(p, width === 1280)
      await p.getByRole('button', { name: 'hidden' }).click()
      await expect(row).toContainText('location privacy is hidden')
      await expect(p.getByText(/Opted in, but location privacy is hidden/)).toBeVisible()
    })
  })
}

test('hidden mode shows no map', async ({ page: p }) => {
  await p.goto('./?source=demo#admin')
  await p.getByRole('button', { name: 'hidden' }).click()
  await p.evaluate(() => { location.hash = '#gnss' })          // same page: the demo adapter keeps the mode
  await p.getByRole('tab', { name: 'Sky Obstruction' }).click()
  await expect(p.getByText(/sky-obstruction map is neither collected nor shown/)).toBeVisible()
  await expect(p.getByRole('img', { name: /Learned sky-obstruction map/ })).toHaveCount(0)
})
