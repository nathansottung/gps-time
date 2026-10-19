import { describe, expect, it } from 'vitest';
import type { OscillatorBin } from '../api/types';
import { fitLine, fmtBytes, fmtSlope, oscPoints, scatterPoints, spanDays } from './oscillator';
import { demoApi } from '../api/demo';

const bin = (t: string, temp: number | null, freq: number | null, pps = 10): OscillatorBin => ({
  t, samples: 10, pps_samples: pps, temp_mean_c: temp, temp_min_c: temp, temp_max_c: temp,
  freq_mean_ppm: freq, freq_min_ppm: freq, freq_max_ppm: freq, skew_mean_ppm: 0.008, residual_mean_ppm: 0,
});

describe('oscillator helpers', () => {
  const bins = [bin('2026-10-19T10:00:00+00:00', 50, 10.3), bin('2026-10-19T10:10:00+00:00', 52, 9.8, 4),
                bin('2026-10-19T10:20:00+00:00', null, 10.0)];

  it('points keep missing values as null and mark partial-PPS bins', () => {
    const p = oscPoints(bins);
    expect(p.map(x => x.pps)).toEqual([true, false, true]);
    expect(p[2].temp).toBeNull();
    expect(oscPoints(undefined)).toEqual([]);
  });

  it('scatter uses complete points, optionally PPS-only', () => {
    const p = oscPoints(bins);
    expect(scatterPoints(p, false)).toEqual([{ x: 50, y: 10.3 }, { x: 52, y: 9.8 }]);
    expect(scatterPoints(p, true)).toEqual([{ x: 50, y: 10.3 }]);
  });

  it('fit line only with a fit', () => {
    const fit = { bins_used: 40, slope_ppm_per_c: -0.25, intercept_ppm: 22.8, r: -0.99, temp_span_c: 6, reason: null, provenance: 'calculated' as const };
    expect(fitLine(fit, [{ x: 50 }, { x: 54 }])).toEqual([{ x: 50, y: 10.3 }, { x: 54, y: 9.3 }]);
    expect(fitLine({ ...fit, slope_ppm_per_c: null }, [{ x: 50 }, { x: 54 }])).toEqual([]);
    expect(fitLine(fit, [{ x: 50 }])).toEqual([]);
  });

  it('labels', () => {
    expect(fmtSlope(-0.25)).toBe('−0.250 ppm/°C');
    expect(fmtSlope(0.0123)).toBe('+0.012 ppm/°C');
    expect(fmtSlope(null)).toBeNull();
    expect([500, 24727, 4194304].map(fmtBytes)).toEqual(['500 B', '24 kB', '4.0 MB']);
    expect(spanDays(oscPoints(bins))).toBeCloseTo(20 / 1440, 6);
    expect(spanDays([])).toBeNull();
  });

  it('demo adapter: observed bins and a calculated slope', async () => {
    const r = await demoApi().oscillator();
    expect(r.available).toBe(true);
    expect(r.provenance).toBe('observed');
    expect(r.fit.provenance).toBe('calculated');
    expect(r.fit.slope_ppm_per_c).toBeCloseTo(-0.3, 1);
    expect(r.bins.length).toBeGreaterThan(100);
  });
});
