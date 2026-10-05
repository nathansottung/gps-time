import { describe, expect, it } from 'vitest';
import type { StabilityPoint } from '../api/types';
import { chartRows, decadeTicks, fmtDeviation, fmtInterval, fmtTau, valueExtent } from './stability';
import { demoApi } from '../api/demo';

const pt = (over: Partial<StabilityPoint>): StabilityPoint => ({
  tau_s: 1, series: 'seconds', adev: 4e-7, adev_terms: 100, adev_low: 3.9e-7, adev_high: 4.1e-7, edf: 50,
  noise: 'white PM', noise_assumed: false, mdev: 4e-7, mdev_terms: 99, tdev_s: 2.3e-7, ...over,
});

describe('chartRows', () => {
  it('gives ADEV its confidence bar as distances below and above', () => {
    const [r] = chartRows([pt({})], 'adev');
    expect(r.v).toBe(4e-7);
    expect(r.err![0]).toBeCloseTo(1e-8, 12);
    expect(r.err![1]).toBeCloseTo(1e-8, 12);
  });

  it('draws no bar where no interval was calculated', () => {
    expect(chartRows([pt({ adev_low: null, adev_high: null })], 'adev')[0].err).toBeUndefined();
    expect(chartRows([pt({})], 'mdev')[0].err).toBeUndefined();
    expect(chartRows([pt({})], 'tdev')[0].err).toBeUndefined();
  });

  it('leaves out a point with no value instead of drawing zero', () => {
    const rows = chartRows([pt({ tau_s: 1 }), pt({ tau_s: 2000, mdev: null, tdev_s: null })], 'mdev');
    expect(rows.map(r => r.tau)).toEqual([1]);
  });

  it('sorts by averaging time and handles no data', () => {
    expect(chartRows([pt({ tau_s: 3600 }), pt({ tau_s: 10 })], 'adev').map(r => r.tau)).toEqual([10, 3600]);
    expect(chartRows(undefined, 'adev')).toEqual([]);
  });
});

describe('axes', () => {
  it('covers the data with whole decades', () => {
    expect(decadeTicks(3e-10, 4e-7).map(t => Math.round(Math.log10(t)))).toEqual([-10, -9, -8, -7, -6]);
    expect(decadeTicks(1, 2000)).toEqual([1, 10, 100, 1000, 10000]);
    expect(decadeTicks(5e-9, 6e-9).length).toBe(2);
    expect(decadeTicks(0, 1)).toEqual([]);
  });

  it('extent includes the confidence bars', () => {
    const rows = chartRows([pt({}), pt({ tau_s: 10, adev: 4e-8, adev_low: 3e-8, adev_high: 6e-8 })], 'adev');
    const [lo, hi] = valueExtent(rows)!;
    expect(lo).toBeCloseTo(3e-8, 12);
    expect(hi).toBeCloseTo(4.1e-7, 12);
    expect(valueExtent([])).toBeNull();
  });
});

describe('labels', () => {
  it('averaging times', () => {
    expect([1, 100, 2000, 3600, 36000, 86400, 172800].map(fmtTau))
      .toEqual(['1 s', '100 s', '2000 s', '1 h', '10 h', '1 day', '2 days']);
  });

  it('ADEV and MDEV as ×10⁻ⁿ, TDEV as a time', () => {
    expect(fmtDeviation(4.354e-9, 'adev')).toBe('4.35 × 10⁻⁹');
    expect(fmtDeviation(1.333e-8, 'mdev')).toBe('1.33 × 10⁻⁸');
    expect(fmtDeviation(2.53e-7, 'tdev')).toBe('253 ns');
    expect(fmtDeviation(9.02e-5, 'tdev')).toBe('90.2 µs');
    expect(fmtDeviation(null, 'adev')).toBeNull();
  });

  it('interval text, or null when none', () => {
    expect(fmtInterval(pt({}))).toBe('3.9 × 10⁻⁷ to 4.1 × 10⁻⁷');
    expect(fmtInterval(pt({ adev_low: null, adev_high: null }))).toBeNull();
  });
});

describe('demo adapter', () => {
  it('serves the same shape as the station, with all five key points', async () => {
    const s = await demoApi().stability();
    expect(s.available).toBe(true);
    expect(s.provenance).toBe('calculated');
    expect(s.key_points.map(k => k.label)).toEqual(['1 s', '10 s', '100 s', '1000 s', '1 day']);
    expect(s.key_points.every(k => k.point !== null)).toBe(true);
    expect(s.notes.join(' ')).toMatch(/sample data/);
    for (const p of s.points) {
      expect(p.adev).toBeGreaterThan(0);
      expect(p.adev_low!).toBeLessThan(p.adev);
      expect(p.adev_high!).toBeGreaterThan(p.adev);
    }
  });
});
