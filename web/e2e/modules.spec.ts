import { expect, test } from '@playwright/test'
import { auditDesign, TYPE_SCALE } from './design-audit'
import { auditLayout } from './layout-audit'

// Administration → Experimental modules with a module turned on: its latest output (the demo's
// canned sample of the module's synthetic demo) is shown as labeled values, and the card still
// fits every width and passes the design audit.

for (const width of [360, 768, 1280]) {
  test.describe(`${width} px`, () => {
    test.use({ viewport: { width, height: 900 } })
    test('module output on Administration', async ({ page: p }) => {
      await p.goto('./?source=demo#admin')
      await p.waitForSelector('main .page-enter')
      await p.getByRole('switch', { name: 'Experimental modules' }).click()
      await p.getByRole('button', { name: /Confirm: turn on/ }).click()
      await p.getByRole('switch', { name: 'Module sdr-pps-marker' }).click()
      const out = p.getByLabel('Latest output of sdr-pps-marker')
      await expect(out).toBeVisible()
      await expect(out).toContainText('markers')
      await expect(out).toContainText('µs')                          // sample_time_uncertainty_s, scaled
      await expect(out.locator('.tag-observed').first()).toBeVisible()  // labels come with the values
      await expect(p.getByText(/Latest observation .* kept in RAM/)).toBeVisible()
      await expect(p.getByText(/canned sample/)).toBeVisible()        // the demo says what it is
      await p.waitForTimeout(300)
      const layout = await p.evaluate(auditLayout)
      expect(layout, layout.map(f => `${f.kind}: ${f.where} — ${f.detail}`).join('\n')).toEqual([])
      if (width === 1280) {
        const design = await p.evaluate(auditDesign, TYPE_SCALE)
        expect(design, design.map(f => `${f.kind}: ${f.where} — ${f.detail}`).join('\n')).toEqual([])
      }
      // turning the switch off removes the output again
      await p.getByRole('switch', { name: 'Experimental modules' }).click()
      await p.getByRole('button', { name: /Confirm: turn off/ }).click()
      await expect(out).toHaveCount(0)
    })
  })
}

// The SDR modules: readiness, settings (checked before sending) and the SDR receivers card.
for (const width of [360, 1280]) {
  test.describe(`${width} px, SDR`, () => {
    test.use({ viewport: { width, height: 900 } })
    test('readiness, settings and receivers', async ({ page: p }) => {
      await p.goto('./?source=demo#admin')
      await p.waitForSelector('main .page-enter')
      const ready = p.getByLabel('Readiness of sdr-pps-marker')
      await expect(ready).toContainText('rtl_tcp running')
      await expect(ready).toContainText('MISSING')                   // no live plan yet
      await expect(ready).toContainText('UNKNOWN')                   // the injected PPS can't be observed
      await expect(p.getByLabel('Readiness of reference-adsb')).toContainText('1090 MHz feed')

      await p.getByRole('button', { name: /^Settings/ }).first().click()
      const box = p.getByLabel('Settings of sdr-pps-marker (JSON)')
      await box.fill('{"rtl_tcp": {"plan": [{"lat": 38.9}]}}')
      await p.getByRole('button', { name: 'Save settings' }).first().click()
      await expect(p.getByRole('alert')).toContainText('positions are not set here')
      await box.fill('{"fs_nominal": 2400000, "rtl_tcp": {"plan": [{"center_hz": 88800000, "dwell_s": 10}]}}')
      await p.getByRole('button', { name: 'Save settings' }).first().click()
      await expect(p.getByText(/sdr-pps-marker settings: saved/)).toBeVisible()
      await expect(ready).not.toContainText('MISSING')

      const units = p.getByLabel('SDR units')
      await expect(units).toContainText('gps-time-readsb.service')
      await expect(units).toContainText('RUNNING')
      await expect(p.getByLabel('RTL-SDR dongles')).toContainText('00001090')
      await expect(p.getByLabel('Decoder feeds')).toContainText('FRESH')
      await p.waitForTimeout(300)
      const layout = await p.evaluate(auditLayout)
      expect(layout, layout.map(f => `${f.kind}: ${f.where} — ${f.detail}`).join('\n')).toEqual([])
      if (width === 1280) {
        const design = await p.evaluate(auditDesign, TYPE_SCALE)
        expect(design, design.map(f => `${f.kind}: ${f.where} — ${f.detail}`).join('\n')).toEqual([])
      }
    })
  })
}
