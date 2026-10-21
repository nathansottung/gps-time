// Review GPS-007: chronyc "System time" is the correction still being slewed out, and the
// figure next to it is chrony's conditional error bound, never "± root dispersion". Checked in
// the source, since the labels are what a reader takes away. (The legacy pages that also carried
// these labels were removed after v1.4.0; GPS-003's band is tested in offset.test.ts.)
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const overview = readFileSync(fileURLToPath(new URL('../pages/Overview.tsx', import.meta.url)), 'utf8');

describe('GPS-007: remaining correction and its bound', () => {
  it('/app/ labels System time as the remaining correction and shows the bound, not ± root dispersion', () => {
    expect(overview).toContain('Remaining correction (chrony)');
    expect(overview).toContain('bound ≤ {t.bound}');
    expect(overview).toContain('max_error_bound_s');
    expect(overview).not.toMatch(/±\s*\{t\.err\}/);
    expect(overview).not.toContain('lightDistance(q?.system_time_s)');
  });
});
