import { describe, expect, it } from 'vitest';
import type { SatelliteNow, ShadowMap } from '../api/types';
import {
  compass, elementAge, fmtDeg, fmtDurationShort, fmtKm, mapSegments, nowLine, parseShell, segmentPath, skyXY,
  stateLabel, stateVariant, xyToSky,
} from './shadow';
import { demoApi } from '../api/demo';

const map = (rows: string[], alts: number[]): ShadowMap => ({
  shell_km: 550, alt_step_deg: 2, az_step_deg: 90, alts_deg: alts, azs_deg: [0, 90, 180, 270], rows,
});

describe('states', () => {
  it('shadow is the good state for a clean frame; sunlight is the warning', () => {
    expect(['UMBRA', 'PENUMBRA', 'SUNLIT', undefined].map(s => stateVariant(s as never))).toEqual(['good', 'info', 'warn', 'muted']);
    expect(stateLabel('UMBRA')).toBe('IN SHADOW (UMBRA)');
    expect(stateLabel(null)).toBe('UNKNOWN');
  });
});

describe('sky map', () => {
  it('merges equal neighbours along a ring', () => {
    const segs = mapSegments(map(['SSUU', 'UUUU'], [10, 12]));
    expect(segs.map(s => [s.code, s.az0, s.az1, s.alt0, s.alt1])).toEqual([
      ['S', -45, 135, 9, 11], ['U', 135, 315, 9, 11], ['U', -45, 315, 11, 13],
    ]);
  });

  it('clamps the horizon and zenith rings', () => {
    const segs = mapSegments(map(['UUUU', 'UUUU'], [0, 90]));
    expect([segs[0].alt0, segs[0].alt1, segs[1].alt0, segs[1].alt1]).toEqual([0, 1, 89, 90]);
    expect(mapSegments(undefined)).toEqual([]);
  });

  it('keeps a thin penumbra run', () => {
    expect(mapSegments(map(['SPUU'], [20])).map(s => s.code)).toEqual(['S', 'P', 'U']);
  });

  it('plot coordinates: north up, east right, zenith centre', () => {
    const r = 100;
    expect(skyXY(0, 0, 0, 0, r).y).toBeCloseTo(-100, 6);
    expect(skyXY(90, 0, 0, 0, r).x).toBeCloseTo(100, 6);
    expect(skyXY(123, 90, 0, 0, r)).toEqual({ x: 0, y: 0 });
    const p = skyXY(300, 20, 50, 50, r);
    expect(xyToSky(p.x, p.y, 50, 50, r)).toEqual({ az: 300, alt: 20 });
    expect(xyToSky(200, 50, 50, 50, r)).toBeNull();
  });

  it('paths: one sector, and a full ring as two halves', () => {
    const one = segmentPath({ code: 'S', alt0: 0, alt1: 10, az0: 0, az1: 90 }, 100, 100, 90);
    expect(one.startsWith('M100.00,10.00 A90.00,90.00 0 0 1 190.00,100.00')).toBe(true);
    expect(one.endsWith('Z')).toBe(true);
    const ring = segmentPath({ code: 'U', alt0: 80, alt1: 90, az0: -2.5, az1: 357.5 }, 100, 100, 90);
    expect(ring.match(/M/g)!.length).toBe(2);
    expect(ring).not.toContain('NaN');
  });
});

describe('formatting', () => {
  it('distances, angles, compass', () => {
    expect(fmtKm(762.8)).toBe('763 km');
    expect(fmtKm(1721.7)).toBe('1,722 km');
    expect(fmtKm(13.4)).toBe('13.4 km');
    expect(fmtKm(null)).toBeNull();
    expect(fmtDeg(-18.7)).toBe('−18.7°');
    expect(fmtDeg(48.31, 0)).toBe('48°');
    expect([0, 44, 290, 359, -90].map(compass)).toEqual(['N', 'NE', 'WNW', 'N', 'W']);
    expect(fmtDurationShort(277)).toBe('4m 37s');
  });

  it('custom shell input', () => {
    expect(['780', ' 1200 ', '99', '60000', 'abc', ''].map(parseShell)).toEqual([780, 1200, null, null, null, null]);
  });

  it('element age is loud when old', () => {
    expect(elementAge(1.29)).toEqual({ text: 'ELEMENTS 31 h OLD', variant: 'good' });
    expect(elementAge(9.2)).toEqual({ text: 'ELEMENTS 9.2 days OLD', variant: 'warn' });
    expect(elementAge(40)).toEqual({ text: 'ELEMENTS 40 days OLD · UNRELIABLE', variant: 'error' });
    expect(elementAge(-3).text).toBe('ELEMENTS DATED 3.0 days AHEAD');
    expect(elementAge(null)).toEqual({ text: 'AGE UNKNOWN', variant: 'muted' });
  });

  it('where a satellite is now', () => {
    const base = { available: true, reason: null, azimuth_deg: 41.7, altitude_deg: 48.3, range_km: 548.9, above_horizon: true } as SatelliteNow;
    expect(nowLine(base)).toBe('48.3° up, NE (42°) · 549 km away');
    expect(nowLine({ ...base, above_horizon: false, altitude_deg: -31.6, range_km: 7480.2 })).toBe('below the horizon (−31.6°) · 7,480 km away');
    expect(nowLine({ ...base, available: false, reason: 'SGP4 could not propagate these elements' })).toBe('SGP4 could not propagate these elements');
  });
});

describe('demo adapter', () => {
  it('shadow: station shape, modeled, with a grid', async () => {
    const s = await demoApi().shadow({ shell: 550 });
    expect(s.available).toBe(true);
    if (!s.available) return;
    expect(s.provenance).toBe('modeled');
    expect(s.map.rows.length).toBe(s.map.alts_deg.length);
    expect(s.map.rows.every(r => r.length === s.map.azs_deg.length && /^[SPU]+$/.test(r))).toBe(true);
    expect(s.messages.join(' ')).toMatch(/not sightings/);
    const q = await demoApi().shadow({ shell: 1200, az: 300, alt: 20 });
    expect(q.available && q.query?.shell_km).toBe(1200);
  });

  it('satellites: external elements, predicted passes, age shown', async () => {
    const s = await demoApi().satellites();
    expect(s.available).toBe(true);
    if (!s.available) return;
    expect(s.provenance).toBe('external');
    expect(s.passes.every(p => p.provenance === 'predicted')).toBe(true);
    expect(s.satellite?.age_days).toBeGreaterThan(0);
    expect(s.cache?.newest_age_days).toBeGreaterThan(0);
  });

  it('hidden location: neither is computed', async () => {
    const api = demoApi();
    await api.setLocationDisplay('hidden');
    const [sh, sat] = [await api.shadow(), await api.satellites()];
    expect(sh.available).toBe(false);
    expect(sat.available).toBe(false);
    expect(!sh.available && sh.reason).toMatch(/privacy/);
  });
});
