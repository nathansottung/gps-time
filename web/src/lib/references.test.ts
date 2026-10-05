import { describe, expect, it } from 'vitest';
import { assessmentVariant, countsLine, fmtSigned, fmtSpan, historySeries, verdictVariant } from './references';
import { demoApi } from '../api/demo';

describe('labels', () => {
  it('a disagreement is a warning, not an error', () => {
    expect(verdictVariant('AGREE')).toBe('good');
    expect(verdictVariant('DISAGREE')).toBe('warn');
    expect(verdictVariant('ONE_REFERENCE')).toBe('info');
    for (const code of ['NONE_REACHABLE', 'NONE_CONFIGURED', 'UNKNOWN', undefined] as const) {
      expect(verdictVariant(code)).toBe('muted');
    }
    expect(['agrees', 'disagrees', 'inconclusive', 'not usable'].map(a => assessmentVariant(a as never)))
      .toEqual(['good', 'warn', 'info', 'muted']);
  });

  it('signed offsets', () => {
    expect(fmtSigned(0.002648)).toBe('+2.65 ms');
    expect(fmtSigned(-0.18)).toBe('−180 ms');
    expect(fmtSigned(0.000895)).toBe('+895 µs');
    expect(fmtSigned(1.5)).toBe('+1.50 s');
    expect(fmtSigned(null)).toBeNull();
    expect(fmtSigned(undefined)).toBeNull();
  });

  it('spans', () => {
    expect(fmtSpan(0.031)).toBe('31.0 ms');
    expect(fmtSpan(0.0004)).toBe('400 µs');
    expect(fmtSpan(2.03e-7)).toBe('203 ns');
    expect(fmtSpan(null)).toBeNull();
  });

  it('counts', () => {
    expect(countsLine({ code: 'AGREE', headline: '', detail: '', provenance: 'calculated', threshold_s: 0.05, usable: 2, configured: 3 }))
      .toBe('2 answering of 3 independent');
    expect(countsLine({ code: 'UNKNOWN', headline: '', detail: '', provenance: 'calculated', threshold_s: 0.05 })).toBeNull();
  });
});

describe('historySeries', () => {
  const pts = [
    { t: 1000, offset_s: 0.002, error_bound_s: 0.015, delay_s: 0.031 },
    { t: 1300, offset_s: -0.003, error_bound_s: 0.015, delay_s: null },
  ];

  it('scales to one unit per series', () => {
    const s = historySeries(pts);
    expect(s.offset.unit).toBe('ms');
    expect(s.offset.data.map(d => d.dt)).toEqual([2, -3]);
    expect(s.offset.data[0].ts).toBe(1_000_000);
  });

  it('leaves a point with no delay out of the delay series instead of drawing zero', () => {
    const s = historySeries(pts);
    expect(s.delay.data.length).toBe(1);
    expect(s.delay.data[0].dt).toBeCloseTo(31, 9);
  });

  it('microsecond offsets and no data', () => {
    expect(historySeries([{ t: 1, offset_s: 0.0002, error_bound_s: null, delay_s: null }]).offset.unit).toBe('µs');
    expect(historySeries(undefined).offset.data).toEqual([]);
  });
});

describe('demo adapter', () => {
  it('agree, disagree, unreachable and none', async () => {
    const api = demoApi();
    const agree = await api.references();
    expect(agree.verdict.code).toBe('AGREE');
    expect(agree.provenance).toBe('external');
    expect(agree.references.every(r => r.provenance === 'external' && r.history.length > 0)).toBe(true);
    const dis = await api.references({ scenario: 'disagree' });
    expect(dis.verdict.code).toBe('DISAGREE');
    expect(dis.verdict.detail).toMatch(/does not say which clock is wrong or why/);
    const off = await api.references({ scenario: 'unreachable' });
    expect(off.verdict.headline).toBe('NO EXTERNAL REFERENCES REACHABLE');
    expect(off.references.every(r => r.offset_s === null && !r.usable)).toBe(true);
    expect((await api.references({ scenario: 'none' })).verdict.code).toBe('NONE_CONFIGURED');
  });

  it('never names a cause', async () => {
    for (const scenario of ['agree', 'disagree', 'unreachable', 'none']) {
      const text = JSON.stringify((await demoApi().references({ scenario })).verdict).toUpperCase();
      for (const word of ['JAMMING', 'SPOOF', 'INTERFERENCE', 'ANTENNA', 'ATTACK', 'FAULT']) expect(text).not.toContain(word);
    }
  });
});
