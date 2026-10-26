// Layout checks run inside the page (page.evaluate). Pure DOM; no dependencies.
// Each finding names a short CSS path and the text involved, so a failure can be found.

export interface Finding { kind: 'page-overflow' | 'offscreen' | 'clipped' | 'overlap'; where: string; detail: string }

export function auditLayout(): Finding[] {
  const out: Finding[] = [];
  const vw = document.documentElement.clientWidth;
  const tol = 1;

  const path = (el: Element): string => {
    const parts: string[] = [];
    let e: Element | null = el;
    while (e && e !== document.body && parts.length < 5) {
      const cls = (e.getAttribute('class') || '').split(/\s+/).filter(c => c && !c.includes('[') && !c.includes(':')).slice(0, 2).join('.');
      parts.push(e.tagName.toLowerCase() + (cls ? '.' + cls : ''));
      e = e.parentElement;
    }
    return parts.reverse().join(' > ');
  };
  const text = (el: Element) => (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60);
  const visible = (el: Element) => {
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || Number(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  // Inside a deliberate horizontal scroller (overflow-x auto/scroll), content may extend past it.
  const inScroller = (el: Element) => {
    for (let e = el.parentElement; e; e = e.parentElement) {
      const ox = getComputedStyle(e).overflowX;
      if (ox === 'auto' || ox === 'scroll') return e.tagName !== 'MAIN' && e.tagName !== 'HTML' && e.tagName !== 'BODY';
    }
    return false;
  };
  // data-layout-ok="plot": a plot draws labels where its data falls (sky plots, polar maps), so its
  // text may overlap by design; it is still checked for overflow and clipping.
  const plotText = (el: Element) => !!el.closest('[data-layout-ok="plot"]');

  // 1. The page and the main area never scroll sideways.
  if (document.documentElement.scrollWidth > vw + tol) {
    out.push({ kind: 'page-overflow', where: 'document', detail: `scrollWidth ${document.documentElement.scrollWidth} > ${vw}` });
  }
  const main = document.querySelector('main');
  if (main && main.scrollWidth > main.clientWidth + tol) {
    out.push({ kind: 'page-overflow', where: 'main', detail: `scrollWidth ${main.scrollWidth} > ${main.clientWidth}` });
  }

  const all = Array.from(document.querySelectorAll('body *')).filter(el => visible(el));

  // 2. Nothing visible sticks out past the right edge (except inside a horizontal scroller).
  for (const el of all) {
    const r = el.getBoundingClientRect();
    if (r.right > vw + tol && !inScroller(el)) {
      // report the outermost offender only
      const parent = el.parentElement;
      if (parent && parent.getBoundingClientRect().right > vw + tol && !inScroller(parent)) continue;
      out.push({ kind: 'offscreen', where: path(el), detail: `right ${Math.round(r.right)} > ${vw}: "${text(el)}"` });
    }
  }

  // 3. Text clipped by its own box (overflow hidden or an ellipsis).
  for (const el of all) {
    if (el instanceof SVGElement) continue;
    const s = getComputedStyle(el);
    const clips = s.overflowX === 'hidden' || s.overflowX === 'clip' || s.textOverflow === 'ellipsis';
    if (!clips || !text(el)) continue;
    const he = el as HTMLElement;
    if (he.scrollWidth > he.clientWidth + tol && !inScroller(el)) {
      out.push({ kind: 'clipped', where: path(el), detail: `${he.scrollWidth} > ${he.clientWidth}: "${text(el)}"` });
    }
  }

  // The part of a rectangle that ancestors with clipping overflow leave visible; null if none.
  const clipToAncestors = (r: DOMRect, el: Element): DOMRect | null => {
    let { left, top, right, bottom } = r;
    for (let e = el.parentElement; e && e !== document.documentElement; e = e.parentElement) {
      const st = getComputedStyle(e);
      if (st.overflowX === 'visible' && st.overflowY === 'visible') continue;
      const c = e.getBoundingClientRect();
      if (st.overflowX !== 'visible') { left = Math.max(left, c.left); right = Math.min(right, c.right); }
      if (st.overflowY !== 'visible') { top = Math.max(top, c.top); bottom = Math.min(bottom, c.bottom); }
      if (right <= left || bottom <= top) return null;
    }
    return new DOMRect(left, top, right - left, bottom - top);
  };

  // 4. Text runs drawn over other text. One rectangle per text line of every text node.
  type Run = { r: DOMRect; node: Text };
  const runs: Run[] = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const t = n as Text;
    if (!t.data.trim() || !t.parentElement || !visible(t.parentElement) || plotText(t.parentElement)) continue;
    const range = document.createRange();
    range.selectNodeContents(t);
    for (const raw of Array.from(range.getClientRects())) {
      const r = clipToAncestors(raw, t.parentElement);   // what a scroller or overflow-hidden box hides isn't drawn
      if (r && r.width > 1 && r.height > 1) runs.push({ r, node: t });
    }
  }
  runs.sort((a, b) => a.r.left - b.r.left);
  const seen = new Set<string>();
  for (let i = 0; i < runs.length; i++) {
    const a = runs[i];
    for (let j = i + 1; j < runs.length && runs[j].r.left < a.r.right; j++) {
      const b = runs[j];
      if (a.node === b.node) continue;
      const w = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
      const h = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
      // a real overlap: both directions clearly, not touching line boxes
      if (w > 2 && h > Math.min(a.r.height, b.r.height) * 0.4) {
        const key = `${a.node.data.trim()}|${b.node.data.trim()}`;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push({ kind: 'overlap', where: path(a.node.parentElement!),
                   detail: `"${a.node.data.trim().slice(0, 30)}" overlaps "${b.node.data.trim().slice(0, 30)}"` });
      }
    }
  }
  return out;
}
