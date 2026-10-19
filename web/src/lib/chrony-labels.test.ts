// Review GPS-007: chronyc "System time" is the correction still being slewed out, and the
// figure next to it is chrony's conditional error bound, never "± root dispersion". Checked in
// the sources of both UIs, since the labels are what a reader takes away.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
const overview = read('../pages/Overview.tsx');
const legacyJs = read('../../../gps_time_pi/static/dashboard.js');
const legacyHtml = read('../../../gps_time_pi/templates/legacy.html');
const history = read('../../../gps_time_pi/templates/history.html');

describe('GPS-007: remaining correction and its bound', () => {
  it('/app/ labels System time as the remaining correction and shows the bound, not ± root dispersion', () => {
    expect(overview).toContain('Remaining correction (chrony)');
    expect(overview).toContain('bound ≤ {t.bound}');
    expect(overview).toContain('max_error_bound_s');
    expect(overview).not.toMatch(/±\s*\{t\.err\}/);
    expect(overview).not.toContain('lightDistance(q?.system_time_s)');
  });
  it('the legacy pages say the same', () => {
    expect(legacyJs).toContain('metric("Remaining correction"');
    expect(legacyJs).toContain('metric("chrony error bound",fmtSec(q.max_error_bound_s)');
    expect(legacyJs).not.toContain('lightDistance(q.system_time_s)');
    expect(legacyHtml).toContain('id="q_bound"');
  });
});

describe('GPS-003: the history band is chrony\'s offset SD, never invented', () => {
  it('no err_s and no ±|offset| fallback', () => {
    expect(history).not.toContain('err_s');
    expect(history).not.toMatch(/\?\?\s*Math\.abs\(p\.offset_s\)/);
    expect(history).toContain('offset_sd_s');
  });
});
