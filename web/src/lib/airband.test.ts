import { describe, expect, it } from 'vitest';
import { cycleLine, mhz, refreshLine, rows } from './airband';
import type { AirbandStatus } from '../api/types';

const st = (nasr: AirbandStatus['nasr'], last: AirbandStatus['last_refresh'] = null): AirbandStatus => ({
  built_in: [{ name: 'Guard (emergency)', frequency_hz: 121_500_000, use: 'emergency', source: 'built-in' }],
  nasr, current_cycle: '2026-11-26', refresh_allowed: true, refresh_note: '', last_refresh: last,
});
const set = (age: number, stale: boolean): AirbandStatus['nasr'] => ({
  cycle: '2026-10-29', fetched_utc: null, radius_km: 80, site_precision: 'exact', count: 2,
  age_days: { value: age, unit: 'days', provenance: 'calculated' }, stale,
  bookmarks: [{ name: 'X TWR', frequency_hz: 119_100_000, use: 'LCL/P', source: 'nasr' }],
});

describe('airband', () => {
  it('shows the cycle date and flags it past 28 days', () => {
    expect(cycleLine(st(set(6, false)))).toEqual({ variant: 'good', text: 'FAA NASR cycle 2026-10-29 (6 days old), 2 channels within 80 km.' });
    const old = cycleLine(st(set(29, true)));
    expect(old.variant).toBe('warn');
    expect(old.text).toContain('past 28 days');
    expect(old.text).toContain('current cycle is 2026-11-26');
  });
  it('says when there is no FAA set yet', () => {
    expect(cycleLine(st(null)).text).toContain('only the 1 built-in');
  });
  it('reports the last refresh, failures included', () => {
    expect(refreshLine(st(null))).toBeNull();
    expect(refreshLine(st(null, { ok: false, at_utc: '2026-11-04T18:00:00+00:00', error: 'download failed' }))!.variant).toBe('error');
  });
  it('lists built-ins first and formats MHz', () => {
    expect(rows(st(set(1, false))).map(r => r.source)).toEqual(['built-in', 'nasr']);
    expect(mhz(121_500_000)).toBe('121.500');
  });
});
