import { expect, test } from '@playwright/test'
import { auditLayout, type Finding } from './layout-audit'

// Every /app/ page at phone, tablet, laptop and desktop widths, and at half-screen
// widths (a window snapped to half of a 1280, 1366 or 1920 px screen): no sideways
// scroll, nothing past the right edge, no clipped text, no text drawn over text.
// The demo adapter supplies the data (?source=demo); values change, layout must not break.

const WIDTHS = [360, 768, 1024, 1280, 1920]
const HALF_SCREEN = [640, 683, 960]
const PAGES = ['overview', 'timing', 'pps', 'gnss', 'sun', 'network', 'radio', 'aviation',
  'distributed', 'data', 'configure', 'admin']

for (const width of [...WIDTHS, ...HALF_SCREEN]) {
  test.describe(`${width} px`, () => {
    test.use({ viewport: { width, height: 900 } })
    for (const page of PAGES) {
      test(page, async ({ page: p }) => {
        await p.goto(`./?source=demo#${page}`)
        await p.waitForSelector('main .page-enter')
        await p.waitForTimeout(700)               // demo data arrives after ~60 ms; charts lay out after
        const findings: Finding[] = []
        findings.push(...await p.evaluate(auditLayout))
        // Tabs inside pages hold more layouts; each is opened and audited too.
        const tabs = p.locator('main [role="tab"]')
        const n = await tabs.count()
        for (let i = 1; i < n; i++) {
          await tabs.nth(i).click()
          await p.waitForTimeout(400)
          const label = (await tabs.nth(i).innerText()).trim()
          findings.push(...(await p.evaluate(auditLayout)).map(f => ({ ...f, where: `[tab ${label}] ${f.where}` })))
        }
        const unique = [...new Map(findings.map(f => [`${f.kind}|${f.where}|${f.detail}`, f])).values()]
        expect(unique, unique.map(f => `${f.kind}: ${f.where} — ${f.detail}`).join('\n')).toEqual([])
      })
    }
  })
}
