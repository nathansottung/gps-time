// Legacy dashboard (gps_time_pi/static/dashboard.js): the Sun & daylight widget
// must say why there is no almanac. The helper is pulled out of the file and
// evaluated on its own, as in legacy-dashboard.test.ts.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(fileURLToPath(new URL('../../../gps_time_pi/static/dashboard.js', import.meta.url)), 'utf8');
const m = src.match(/^function almanacUnavailableText\(.*$/m);
if (!m) throw new Error('almanacUnavailableText not found in dashboard.js');
const text = new Function(`${m[0]}; return almanacUnavailableText;`)() as (alm: unknown, failed?: boolean) => string;

describe('legacy Sun & daylight: why the almanac is unavailable', () => {
  it("shows the station's reason", () => {
    expect(text({ available: false, reason: 'de440s.bsp is not readable by the service user' }))
      .toBe('Astronomy data unavailable: de440s.bsp is not readable by the service user');
  });

  it('shows a server error instead of hiding it', () => {
    expect(text({ error: 'boom' })).toBe('Astronomy data unavailable: boom');
  });

  it('says so when the station did not answer', () => {
    expect(text(null, true)).toContain('did not answer /api/almanac');
  });

  it('says loading, not a failure, before the first answer', () => {
    expect(text(null, false)).toBe('Astronomy data: loading\u2026');
    expect(text(null)).not.toContain('did not answer');
  });

  it('an almanac failure does not stop the dashboard from rendering', () => {
    expect(src).toMatch(/ALM_FAILED=false;\}catch\(e\)\{ALM=null;ALM_FAILED=true;\}render\(\);/);
    expect(src).toContain('${esc(almanacUnavailableText(ALM,ALM_FAILED))}');
  });

  it('never a bare "unavailable."', () => {
    expect(text({ available: false })).toBe('Astronomy data unavailable (no reason given).');
    expect(src).not.toContain('Astronomy data unavailable.</div>');
  });

  it('the widget escapes the reason', () => {
    expect(src).toContain('${esc(almanacUnavailableText(ALM,ALM_FAILED))}');
  });
});
