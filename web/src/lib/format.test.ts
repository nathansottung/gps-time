// Sign and unit conventions that are easy to get backwards.
import { describe, expect, it } from 'vitest';
import { chronyFreqToFrac, fmtDelta, fmtDuration, fmtOffset, fmtSeconds } from './format';
import { fmtSci } from './units';

describe('chronyFreqToFrac', () => {
  it('maps chrony "slow" to a negative and "fast" to a positive Δf/f', () => {
    expect(chronyFreqToFrac('1.240 ppm slow')).toBeCloseTo(-1.24e-6, 12);
    expect(chronyFreqToFrac('2.117 ppm fast')).toBeCloseTo(2.117e-6, 12);
  });
  it('returns null for missing or unparsable text', () => {
    expect(chronyFreqToFrac(null)).toBeNull();
    expect(chronyFreqToFrac('n/a')).toBeNull();
  });
});

describe('fmtOffset', () => {
  it('picks the unit and uses a Unicode minus', () => {
    expect(fmtOffset(12.3e-9)).toEqual({ value: '+12.3', unit: 'ns' });
    expect(fmtOffset(-4.5e-6)).toEqual({ value: '−4.5', unit: 'µs' });
    expect(fmtOffset(0.0021)).toEqual({ value: '+2.1', unit: 'ms' });
  });
  it('is null (UNKNOWN) for missing values, never 0', () => {
    expect(fmtOffset(null)).toBeNull();
    expect(fmtOffset(undefined)).toBeNull();
    expect(fmtOffset(Number.NaN)).toBeNull();
  });
});

describe('durations and magnitudes', () => {
  it('formats durations', () => {
    expect(fmtDuration(34)).toBe('34s');
    expect(fmtDuration(161)).toBe('2m 41s');
    expect(fmtDuration(2 * 86400 + 7 * 3600 + 14 * 60)).toBe('2d 7h 14m');
    expect(fmtDuration(null)).toBeNull();
  });
  it('formats signed daylight changes', () => {
    expect(fmtDelta(-131.3)).toBe('−2m 11.3s');
    expect(fmtDelta(182.8)).toBe('+3m 02.8s');
  });
  it('formats unsigned magnitudes', () => {
    expect(fmtSeconds(-4.1e-9)).toBe('4.1 ns');
  });
});

describe('fmtSci (Δf/f as ×10⁻ⁿ)', () => {
  it('uses superscripts and a Unicode minus', () => {
    expect(fmtSci(-1.24e-9)).toBe('−1.24 × 10⁻⁹');
    expect(fmtSci(9.996e-7)).toBe('1 × 10⁻⁶');
  });
});
