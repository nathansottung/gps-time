// Design checks run inside the page (page.evaluate), against web/guidelines/Guidelines.md.
// Pure DOM; no dependencies. Returns findings; the spec decides which fail.

export interface DesignFinding { kind: 'contrast' | 'type-scale' | 'numbers' | 'weight'; where: string; detail: string }

/** Font sizes in the guideline type scale (px). */
export const TYPE_SCALE = [8, 9, 10, 11, 12, 13, 14, 16, 20, 36, 44, 72]

export function auditDesign(scale: number[]): DesignFinding[] {
  const out: DesignFinding[] = []

  const parse = (c: string): [number, number, number, number] | null => {
    const m = c.match(/rgba?\(([^)]+)\)/)
    if (!m) return null
    const p = m[1].split(/[,\s/]+/).filter(Boolean).map(Number)
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]
  }
  const lum = ([r, g, b]: number[]) => {
    const f = (v: number) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 }
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
  }
  const over = (top: number[], below: number[]) => {
    const a = top[3]
    return [top[0] * a + below[0] * (1 - a), top[1] * a + below[1] * (1 - a), top[2] * a + below[2] * (1 - a), 1]
  }
  // The colour behind an element: its own and its ancestors' backgrounds, composited over the page.
  const backdrop = (el: Element): number[] => {
    const layers: number[][] = []
    for (let e: Element | null = el; e; e = e.parentElement) {
      const c = parse(getComputedStyle(e).backgroundColor)
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break }
    }
    let base = [8, 8, 9, 1]              // --bg
    for (const l of layers.reverse()) base = over(l, base)
    return base
  }
  const ratio = (a: number[], b: number[]) => {
    const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p)
    return (x + 0.05) / (y + 0.05)
  }
  const path = (el: Element) => {
    const parts: string[] = []
    for (let e: Element | null = el; e && e !== document.body && parts.length < 4; e = e.parentElement) {
      const cls = (e.getAttribute('class') || '').split(/\s+/).filter(c => c && !c.includes('[') && !c.includes(':') && !c.includes('@')).slice(0, 2).join('.')
      parts.push(e.tagName.toLowerCase() + (cls ? '.' + cls : ''))
    }
    return parts.reverse().join(' > ')
  }

  const seen = new Set<string>()
  const add = (f: DesignFinding) => {
    const k = `${f.kind}|${f.detail}`
    if (!seen.has(k)) { seen.add(k); out.push(f) }
  }
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const t = (n as Text).data.trim()
    const el = (n as Text).parentElement
    if (!t || !el) continue
    const s = getComputedStyle(el)
    const r = el.getBoundingClientRect()
    if (s.visibility === 'hidden' || s.display === 'none' || r.width === 0 || r.height === 0) continue
    if (el.closest('[aria-hidden="true"], .night-overlay, .sensitive')) continue
    const disabled = !!el.closest('button:disabled, input:disabled, select:disabled, [aria-disabled="true"]')
    const svg = el instanceof SVGElement
    const size = parseFloat(s.fontSize)
    const weight = Number(s.fontWeight)
    const sample = t.slice(0, 40)

    // Contrast (WCAG 2.2 AA): 4.5:1, or 3:1 for large text. Disabled controls are exempt.
    const fg = parse(svg ? (s.fill && s.fill !== 'none' ? s.fill : s.color) : s.color)
    if (fg && !disabled) {
      const bg = backdrop(el)
      const opacity = [...(function* () { for (let e: Element | null = el; e; e = e.parentElement) yield Number(getComputedStyle(e).opacity) })()].reduce((a, b) => a * b, 1)
      const c = over([fg[0], fg[1], fg[2], fg[3] * opacity], bg)
      const need = size >= 24 || (size >= 18.66 && weight >= 600) ? 3 : 4.5
      const k = ratio(c, bg)
      if (k < need - 0.01) add({ kind: 'contrast', where: path(el), detail: `${k.toFixed(2)}:1 < ${need} — ${s.color} on rgb(${bg.slice(0, 3).map(Math.round).join(',')}) ${size}px "${sample}"` })
    }
    // Type scale.
    if (!svg && !scale.includes(Math.round(size * 2) / 2)) add({ kind: 'type-scale', where: path(el), detail: `${size}px "${sample}"` })
    // Weights 300-600 only.
    if (weight > 600) add({ kind: 'weight', where: path(el), detail: `${weight} "${sample}"` })
    // Numbers that line up in columns use tabular figures.
    // A number standing alone in its element (a cell, a value), not one inside a sentence.
    const whole = (el.textContent || '').trim()
    if (!svg && /^[−+-]?\d[\d.,:'’ ]*\d?\s*(ns|µs|ms|s|%|dB-Hz|m|km|°|ppm|ppb|Hz|MHz|W|V|°C|MB|KB|GB)?$/.test(whole) && whole.length >= 2
        && !s.fontVariantNumeric.includes('tabular-nums')) {
      add({ kind: 'numbers', where: path(el), detail: `"${sample}" (${s.fontFamily.split(',')[0]}, ${s.fontVariantNumeric})` })
    }
  }
  return out
}
