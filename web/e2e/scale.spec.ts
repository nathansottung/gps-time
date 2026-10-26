import { expect, test, type Locator, type Page } from '@playwright/test'

// Linear/log toggle on every time-offset and stability chart: the axis follows it, time axes
// label each tick with ns/µs/ms/s, and the choice is remembered in this browser (localStorage).

const TIME_LABEL = /^(0|−?\d+(\.\d+)? (ns|µs|ms|s))$/

async function open(p: Page, page: string, tab?: string) {
  await p.goto(`./?source=demo#${page}`)
  await p.waitForSelector('main .page-enter')
  if (tab) await p.getByRole('tab', { name: tab }).click()
  await p.waitForTimeout(600)
}

/** The card holding the n-th scale toggle on the page, and that toggle. */
function chartCard(p: Page, n = 0): { card: Locator; toggle: Locator } {
  const toggle = p.locator('main [role="group"][aria-label="Value axis scale"]').nth(n)
  return { toggle, card: toggle.locator('xpath=ancestor::div[contains(@class,"card-surface")][1]') }
}

/** The value-axis tick labels (SVG text: textContent, not innerText). At least two, or it throws. */
async function yLabels(card: Locator): Promise<string[]> {
  const out = (await card.locator('.recharts-yAxis-tick-labels text.recharts-cartesian-axis-tick-value, .recharts-yAxis text.recharts-cartesian-axis-tick-value')
    .evaluateAll(els => els.map(e => (e.textContent || '').trim()))).filter(Boolean)
  expect(out.length, 'value-axis tick labels').toBeGreaterThan(1)
  return out
}

async function choose(toggle: Locator, scale: 'Lin' | 'Log') {
  await toggle.getByRole('button', { name: scale }).click()
  await expect(toggle.getByRole('button', { name: scale })).toHaveAttribute('aria-pressed', 'true')
}

const TIME_CHARTS: { name: string; page: string; tab?: string; n?: number }[] = [
  { name: 'Overview Δt', page: 'overview' },
  { name: 'offset history', page: 'timing' },
  { name: 'holdover', page: 'timing', n: 1 },
  { name: 'reference offset', page: 'timing', tab: 'References' },
  { name: 'reference delay', page: 'timing', tab: 'References', n: 1 },
]

test.use({ viewport: { width: 1280, height: 900 } })

for (const c of TIME_CHARTS) {
  test(`${c.name}: both scales, time labels, remembered`, async ({ page: p }) => {
    await open(p, c.page, c.tab)
    let { toggle, card } = chartCard(p, c.n)
    for (const scale of ['Log', 'Lin'] as const) {
      await choose(toggle, scale)
      await p.waitForTimeout(250)
      const labels = await yLabels(card)
      for (const l of labels) expect(l, `${scale} tick "${l}"`).toMatch(TIME_LABEL)
    }
    await choose(toggle, 'Log')
    await open(p, c.page, c.tab)                  // reload: the choice is remembered
    ;({ toggle, card } = chartCard(p, c.n))
    await expect(toggle.getByRole('button', { name: 'Log' })).toHaveAttribute('aria-pressed', 'true')
  })
}

test('stability: value axis linear or log; TDEV in time units', async ({ page: p }) => {
  await open(p, 'timing', 'Stability')
  const { toggle, card } = chartCard(p)
  await choose(toggle, 'Log')
  expect((await yLabels(card)).every(l => /^10[⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+$/.test(l))).toBe(true)
  await choose(toggle, 'Lin')
  await p.waitForTimeout(250)
  expect((await yLabels(card)).every(l => l === '0' || /× 10[⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+$/.test(l))).toBe(true)
  await card.getByRole('button', { name: 'TDEV' }).click()
  await p.waitForTimeout(250)
  for (const l of await yLabels(card)) expect(l).toMatch(TIME_LABEL)
  await open(p, 'timing', 'Stability')
  await expect(chartCard(p).toggle.getByRole('button', { name: 'Lin' })).toHaveAttribute('aria-pressed', 'true')
})

test('the three Overview views share one choice', async ({ page: p }) => {
  await open(p, 'overview')
  await choose(chartCard(p).toggle, 'Log')
  await p.getByRole('button', { name: 'B', exact: true }).click()
  await p.waitForTimeout(400)
  await expect(chartCard(p).toggle.getByRole('button', { name: 'Log' })).toHaveAttribute('aria-pressed', 'true')
})
