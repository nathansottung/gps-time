import { expect, test } from '@playwright/test'
import { auditDesign, TYPE_SCALE, type DesignFinding } from './design-audit'

// Guidelines.md, checked in the browser: contrast (WCAG AA), the type scale, weights,
// tabular figures for numbers, visible keyboard focus, and loading shown as loading.

const PAGES = ['overview', 'timing', 'pps', 'gnss', 'sun', 'network', 'radio', 'aviation',
  'distributed', 'data', 'configure', 'admin']

test.describe('design audit at 1280 px', () => {
  test.use({ viewport: { width: 1280, height: 900 } })
  for (const page of PAGES) {
    test(page, async ({ page: p }) => {
      await p.goto(`./?source=demo#${page}`)
      await p.waitForSelector('main .page-enter')
      await p.waitForTimeout(600)
      const found: DesignFinding[] = [...await p.evaluate(auditDesign, TYPE_SCALE)]
      const tabs = p.locator('main [role="tab"]')
      for (let i = 1; i < await tabs.count(); i++) {
        await tabs.nth(i).click()
        await p.waitForTimeout(350)
        found.push(...await p.evaluate(auditDesign, TYPE_SCALE))
      }
      expect(found, found.map(f => `${f.kind}: ${f.where} — ${f.detail}`).join('\n')).toEqual([])
    })
  }
})

test.describe('keyboard focus is visible', () => {
  test.use({ viewport: { width: 1280, height: 900 } })
  for (const page of PAGES) {
    test(page, async ({ page: p }) => {
      await p.goto(`./?source=demo#${page}`)
      await p.waitForSelector('main .page-enter')
      await p.waitForTimeout(400)
      const missing: string[] = []
      for (let i = 0; i < 60; i++) {
        await p.keyboard.press('Tab')
        const r = await p.evaluate(() => {
          const e = document.activeElement as HTMLElement | null
          if (!e || e === document.body) return null
          const s = getComputedStyle(e)
          const ring = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 1
          return { ring: ring || s.boxShadow !== 'none', what: `${e.tagName.toLowerCase()} "${(e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 30)}"` }
        })
        if (r && !r.ring) missing.push(r.what)
      }
      expect([...new Set(missing)]).toEqual([])
    })
  }
})

test.describe('loading is not UNKNOWN', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('values show as loading until the station answers', async ({ page: p }) => {
    await p.route('**/api**', () => { /* never answered */ })
    await p.goto('./?source=live#admin')
    await p.waitForSelector('main .page-enter')
    await p.waitForTimeout(500)
    await expect(p.locator('main [aria-label="loading"]').first()).toBeVisible()
    await expect(p.locator('main').getByText('UNKNOWN', { exact: true })).toHaveCount(0)
  })

  test('a failed request ends loading', async ({ page: p }) => {
    await p.route('**/api**', r => r.abort())
    await p.goto('./?source=live#admin')
    await p.waitForSelector('main .page-enter')
    await p.waitForTimeout(800)
    await expect(p.locator('main [aria-label="loading"]')).toHaveCount(0)
  })
})
