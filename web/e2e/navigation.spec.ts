import { expect, test } from '@playwright/test'

// The navigation: a drawer below 1024 px, a fixed sidebar from 1024 px; the page in the URL hash.

test.describe('narrow (360 px): drawer', () => {
  test.use({ viewport: { width: 360, height: 800 } })

  test('opens from the menu button, navigates, and closes', async ({ page }) => {
    await page.goto('./?source=demo')
    const nav = page.getByRole('navigation', { name: 'Pages' })
    await expect(nav).toBeHidden()
    await page.getByRole('button', { name: 'Open navigation' }).click()
    await expect(nav).toBeVisible()
    await nav.getByRole('button', { name: 'Administration' }).click()
    await expect(page).toHaveURL(/#admin$/)
    await expect(page.getByRole('heading', { name: /Administration/ })).toBeVisible()
    await expect(nav).toBeHidden()
  })

  test('closes with Escape and the backdrop', async ({ page }) => {
    await page.goto('./?source=demo')
    const nav = page.getByRole('navigation', { name: 'Pages' })
    await page.getByRole('button', { name: 'Open navigation' }).click()
    await page.keyboard.press('Escape')
    await expect(nav).toBeHidden()
    await page.getByRole('button', { name: 'Open navigation' }).click()
    await page.mouse.click(340, 400)            // the backdrop, right of the 188 px drawer
    await expect(nav).toBeHidden()
  })
})

test.describe('wide (1280 px): sidebar', () => {
  test.use({ viewport: { width: 1280, height: 800 } })

  test('is always shown, with no menu button', async ({ page }) => {
    await page.goto('./?source=demo')
    await expect(page.getByRole('navigation', { name: 'Pages' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Open navigation' })).toBeHidden()
  })

  test('the hash opens a page, and Back returns', async ({ page }) => {
    await page.goto('./?source=demo#gnss')
    await expect(page.getByRole('heading', { name: 'GNSS & Site' })).toBeVisible()
    await page.getByRole('navigation', { name: 'Pages' }).getByRole('button', { name: 'Timing & Reliability' }).click()
    await expect(page).toHaveURL(/#timing$/)
    await page.goBack()
    await expect(page.getByRole('heading', { name: 'GNSS & Site' })).toBeVisible()
  })
})
