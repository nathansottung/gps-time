import { expect, test, type Page } from '@playwright/test'
import { auditLayout } from '../e2e/layout-audit'
import { auditDesign, TYPE_SCALE } from '../e2e/design-audit'

// Every page and tab of the UI as a station serves it (playwright.station.config.ts):
// - layout at 360, 768, 1280 and 1920 px and design (contrast, type scale…) at 1280 px, with no
//   console errors;
// - screenshot mode: the US Naval Observatory demo position never appears on screen;
// - the red night theme's layout.
// Screenshots at 360 and 1280 px go to test-results/station-shots (or STATION_SHOTS), for a look by eye:
// a layout audit can't see a chart whose text is drawn stretched.

const OUT = process.env.STATION_SHOTS || 'test-results/station-shots'
const PAGES = ['overview', 'timing', 'pps', 'gnss', 'sun', 'network', 'radio', 'aviation', 'distributed', 'data', 'configure', 'admin']

/** The whole page: the app scrolls inside its own container, so the viewport is grown to the content first. */
async function shoot(p: Page, name: string) {
  const vp = p.viewportSize()!
  const h = await p.evaluate(() => Math.max(...[...document.querySelectorAll('*')].map(e => e.scrollHeight)))
  await p.setViewportSize({ width: vp.width, height: Math.min(Math.max(h, vp.height), 9000) })
  await p.waitForTimeout(300)
  await p.screenshot({ path: `${OUT}/${name.replace(/[^a-z0-9-]+/gi, '_')}.png` })
  await p.setViewportSize(vp)
}

async function eachTab(p: Page, fn: (tab: string) => Promise<void>) {
  await fn('main')
  const tabs = p.locator('main [role="tab"]')
  const n = await tabs.count()
  for (let i = 1; i < n; i++) {
    await tabs.nth(i).click(); await p.waitForTimeout(500)
    await fn((await tabs.nth(i).innerText()).trim())
  }
}

for (const width of [360, 768, 1280, 1920]) {
  test.describe(`${width}`, () => {
    test.use({ viewport: { width, height: 900 } })
    for (const page of PAGES) {
      test(page, async ({ page: p }) => {
        const errors: string[] = []
        p.on('pageerror', e => errors.push(String(e)))
        p.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
        await p.goto(`./?source=live#${page}`)
        await p.waitForSelector('main .page-enter'); await p.waitForTimeout(1500)
        const found: string[] = []
        await eachTab(p, async (tab) => {
          for (const f of await p.evaluate(auditLayout)) found.push(`layout [${tab}] ${f.kind}: ${f.where} — ${f.detail}`)
          if (width === 1280) for (const f of await p.evaluate(auditDesign, TYPE_SCALE)) found.push(`design [${tab}] ${f.kind}: ${f.where} — ${f.detail}`)
          if (width === 1280 || width === 360) await shoot(p, `${width}-${page}-${tab}`)
        })
        expect([...found, ...errors.map(e => `console: ${e}`)]).toEqual([])
      })
    }
  })
}

test.describe('screenshot mode and night theme at 1280', () => {
  test.use({ viewport: { width: 1280, height: 900 } })
  for (const page of PAGES) {
    test(`screenshot mode hides the position: ${page}`, async ({ page: p }) => {
      await p.goto(`./?source=live#${page}`)
      await p.waitForSelector('main .page-enter'); await p.waitForTimeout(1200)
      await p.keyboard.press('Alt+Shift+S'); await p.waitForTimeout(400)
      const leaks: string[] = []
      await eachTab(p, async (tab) => {
        const text = await p.evaluate(() => document.body.innerText)
        for (const pat of [/38\.92/, /77\.06/, /38°\s*55/, /77°\s*0?4/]) if (pat.test(text)) leaks.push(`[${tab}] ${pat}`)
      })
      expect(leaks).toEqual([])
    })
    test(`night theme layout: ${page}`, async ({ page: p }) => {
      await p.goto(`./?source=live&theme=night#${page}`)
      await p.waitForSelector('main .page-enter'); await p.waitForTimeout(1200)
      const found: string[] = []
      await eachTab(p, async (tab) => { for (const f of await p.evaluate(auditLayout)) found.push(`[${tab}] ${f.kind}: ${f.where}`) })
      if (page === 'overview' || page === 'timing') await shoot(p, `night-${page}`)
      expect(found).toEqual([])
    })
  }
})
