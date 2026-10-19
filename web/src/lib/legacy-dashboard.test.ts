// The legacy dashboard (gps_time_pi/static/dashboard.js) isn't a module, so the
// helper is pulled out of the file and evaluated on its own.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(fileURLToPath(new URL('../../../gps_time_pi/static/dashboard.js', import.meta.url)), 'utf8');

function helper(name: string): (x: unknown) => string {
  const m = src.match(new RegExp(`^function ${name}\\(.*$`, 'm'));
  if (!m) throw new Error(`${name} not found in dashboard.js`);
  return new Function(`${m[0]}; return ${name};`)() as (x: unknown) => string;
}

describe('legacy Sun & daylight: change vs yesterday', () => {
  const signedSeconds = helper('signedSeconds');

  it('keeps the sign (a shrinking day is negative, with U+2212)', () => {
    expect(signedSeconds(-182.8)).toBe('−182.8 s');
    expect(signedSeconds(56.74)).toBe('+56.7 s');
    expect(signedSeconds(0.02)).toBe('0.0 s');
  });

  it('shows unknown, not 0, when there is no value', () => {
    expect(signedSeconds(null)).toBe('–');
    expect(signedSeconds(undefined)).toBe('–');
  });

  it('the widget uses it for both changes and no longer drops the sign', () => {
    expect(src).not.toMatch(/Math\.abs\(ALM\.delta_yesterday/);
    expect(src).toContain('${signedSeconds(ALM.delta_yesterday)} change vs yesterday');
    expect(src).toContain('${signedSeconds(ALM.delta_tomorrow)}');
  });
});

describe('legacy Sun & daylight: sunset as prominent as sunrise', () => {
  const m = ['fmtLocal', 'sunDay'].map(n => src.match(new RegExp(`^function ${n}\\(.*$`, 'm'))?.[0]);
  const sunDay = new Function(`${m.join('\n')}; return sunDay;`)() as (l: string, r: unknown, s: unknown) => string;

  it('both times are in <strong>, each with its own label', () => {
    const html = sunDay('Today', '2026-10-19T11:15:00Z', '2026-10-19T22:20:00Z');
    expect(html.match(/<strong>/g)).toHaveLength(2);
    expect(html).toMatch(/<strong>[^<]+<\/strong><small class="muted">Sunrise<\/small><strong>[^<]+<\/strong><small class="muted">Sunset<\/small>/);
  });

  it('a missing time is a dash, not a blank', () => {
    expect(sunDay('Tomorrow', null, undefined).match(/<strong>—<\/strong>/g)).toHaveLength(2);
  });

  it('all three days use it; sunset is no longer small print', () => {
    for (const d of ['Yesterday', 'Today', 'Tomorrow']) expect(src).toContain(`\${sunDay("${d}",`);
    expect(src).not.toContain('sunset</small>');
  });
});
