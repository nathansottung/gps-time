import { describe, expect, it } from 'vitest';
import { fmtDurationTick, fmtTime, linearTicks, logTicks, positiveOnly, symAxis, symThreshold, symTimeLabel, UNIT_S } from './timeaxis';
import { symlog } from './offset';

describe('fmtTime', () => {
  it('picks ns, µs, ms or s', () => {
    expect(fmtTime(0)).toBe('0');
    expect(fmtTime(850e-9)).toBe('850 ns');
    expect(fmtTime(1.5e-6)).toBe('1.5 µs');
    expect(fmtTime(-12e-3)).toBe('−12 ms');
    expect(fmtTime(2)).toBe('2 s');
    expect(fmtTime(0.35e-9)).toBe('0.35 ns');
    expect(fmtTime(13.4e-9)).toBe('13.4 ns');
    expect(fmtTime(Number.NaN)).toBe('—');
  });
});

describe('linearTicks', () => {
  it('uses 1, 2 or 5 × 10ⁿ steps covering the data', () => {
    expect(linearTicks(0, 1e-6)).toEqual([0, 2e-7, 4e-7, 6e-7, 8e-7, 1e-6]);
    const t = linearTicks(-3.2e-9, 17.1e-9);
    expect(t[0]).toBeLessThanOrEqual(-3.2e-9);
    expect(t[t.length - 1]).toBeGreaterThanOrEqual(17.1e-9);
    expect(t).toContain(0);
    expect(t.map(fmtTime)).toEqual(['−5 ns', '0', '5 ns', '10 ns', '15 ns', '20 ns']);
  });
  it('widens a flat series', () => {
    expect(linearTicks(5e-9, 5e-9).length).toBeGreaterThan(1);
    expect(linearTicks(0, 0).length).toBeGreaterThan(1);
  });
});

describe('symmetric log', () => {
  it('chooses the linear zone from the data', () => {
    expect(symThreshold([13e-9, 9e-9, 17e-9, -11e-9])).toBe(1e-9);
    expect(symThreshold([2e-3, -5e-3, 1e-3])).toBe(1e-3);
    expect(symThreshold([0, 0])).toBe(1e-9);
  });
  it('covers both signs and labels ticks as times', () => {
    const lin = 1e-9;
    const { domain, ticks } = symAxis([-30e-9, 2e-6], lin);
    expect(domain[0]).toBeLessThanOrEqual(symlog(-30e-9, lin));
    expect(domain[1]).toBeGreaterThanOrEqual(symlog(2e-6, lin));
    expect(ticks).toContain(0);
    expect(ticks.map(t => symTimeLabel(t, lin))).toEqual(['−100 ns', '−10 ns', '−1 ns', '0', '1 ns', '10 ns', '100 ns', '1 µs', '10 µs']);
  });
  it('thins ticks over many decades', () => {
    const { ticks } = symAxis([-1, 1], 1e-12);
    expect(ticks.length).toBeLessThanOrEqual(15);
  });
});

describe('log axis', () => {
  it('decade ticks over positive values', () => {
    expect(logTicks([3e-9, 40e-9])).toEqual([1e-9, 1e-8, 1e-7]);
    expect(logTicks([0, -1])).toEqual([]);
  });
  it('counts what a log axis cannot draw', () => {
    expect(positiveOnly([{ v: 0 }, { v: 2 }, { v: -1 }], r => r.v)).toEqual({ rows: [{ v: 2 }], dropped: 2 });
  });
  it('knows the units series are scaled to', () => {
    expect(UNIT_S['µs']).toBe(1e-6);
    expect(UNIT_S.ns).toBe(1e-9);
  });
});

describe('fmtDurationTick', () => {
  it('labels log-axis durations', () => {
    expect([10, 100, 1000, 10000].map(fmtDurationTick)).toEqual(['10s', '100s', '16m 40s', '2h 46m']);
  });
});
