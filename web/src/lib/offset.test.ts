import { describe, expect, it } from 'vitest';
import { fmtSeconds, offsetRows, symDomain, symexp, symlog, symTicks } from './offset';
import type { HistoryPoint } from '../api/types';

describe('symmetric-log axis', () => {
  it('linear within ±1 µs, one unit per decade beyond', () => {
    expect(symlog(0)).toBe(0);
    expect(symlog(500e-9)).toBeCloseTo(0.5);
    expect(symlog(1e-6)).toBeCloseTo(1);
    expect(symlog(10e-6)).toBeCloseTo(2);
    expect(symlog(-1e-3)).toBeCloseTo(-4);
  });
  it('symexp undoes it', () => {
    for (const v of [0, 3e-7, -8e-7, 2.5e-5, -4e-3, 1.2]) expect(symexp(symlog(v))).toBeCloseTo(v, 12);
  });
  it('tick labels', () => {
    expect([0, 1, 2, 4, -2].map(y => fmtSeconds(symexp(y)))).toEqual(['0', '1 µs', '10 µs', '1 ms', '−10 µs']);
    expect(fmtSeconds(5e-7)).toBe('500 ns');
  });
});

const P = (t: number, offset_s: number, offset_sd_s?: number | null, max_error_s?: number | null): HistoryPoint =>
  ({ t, offset_s, offset_sd_s, max_error_s });

describe('offset rows', () => {
  it('band is offset ± chrony’s offset SD, only where reported; never invented', () => {
    const r = offsetRows([P(9_000, 1e-7, 5e-8, 2e-5), P(9_500, -2e-7, null, null)], 3600, 10_000 * 1000);
    expect(r[0].band![0]).toBeCloseTo(symlog(5e-8));
    expect(r[0].band![1]).toBeCloseTo(symlog(1.5e-7));
    expect(r[1].band).toBeNull();
    expect(r[1].maxErr).toBeNull();
  });
  it('max-error bound is ± around zero (a bound on the error, not on the offset)', () => {
    const r = offsetRows([P(9_000, 1e-7, 5e-8, 2e-5)], 3600, 10_000 * 1000);
    expect(r[0].maxErr![1]).toBeCloseTo(symlog(2e-5));
    expect(r[0].maxErr![0]).toBeCloseTo(-symlog(2e-5));
  });
  it('only the chosen range', () => {
    expect(offsetRows([P(1_000, 1e-7), P(9_000, 1e-7)], 3600, 10_000 * 1000)).toHaveLength(1);
  });
  it('domain covers what is drawn, at least ±1.2; ticks every decade', () => {
    const r = offsetRows([P(9_000, 1e-7, 5e-8, 2e-5)], 3600, 10_000 * 1000);
    expect(symDomain(r, false)).toEqual([-1.2, 1.2]);
    const d = symDomain(r, true);
    expect(d[1]).toBeGreaterThanOrEqual(symlog(2e-5));
    expect(symTicks([-2.4, 2.4])).toEqual([-2, -1, 0, 1, 2]);
  });
});
