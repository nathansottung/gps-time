import { describe, expect, it } from 'vitest';
import { bullseye, convergenceSeries, fmtMetres, logDomain, rejectedRows, resetConfirmed, resetOutcome, surveyLoss } from './survey';

describe('survey reset: typed confirmation', () => {
  it('the word, any case, spaces ignored', () => {
    expect(resetConfirmed('RESET')).toBe(true);
    expect(resetConfirmed(' reset ')).toBe(true);
  });
  it('anything else is no', () => {
    for (const s of ['', 'RESE', 'RESET!', 'yes', 'reset survey']) expect(resetConfirmed(s)).toBe(false);
  });
});

describe('survey reset: what would be lost', () => {
  it("states the station's counts", () => {
    expect(surveyLoss({ n: 18432, se_horiz_m: 0.18 }))
      .toBe('Discards 18,432 accepted fixes, horizontal standard error of the mean ±0.18 m. The survey starts again from the next fresh fix.');
    expect(surveyLoss({ n: 3 })).toContain('Discards 3 accepted fixes.');
  });
  it('empty is said, unknown is UNKNOWN', () => {
    expect(surveyLoss({ n: 0 })).toContain('nothing to discard');
    expect(surveyLoss(null)).toContain('UNKNOWN');
  });
});

describe('survey reset: outcome', () => {
  it('done only when the station says reset_site', () => {
    expect(resetOutcome({ ok: true, reset_site: true }).variant).toBe('good');
    expect(resetOutcome({ ok: true, location_display: 'exact' }).variant).toBe('error');
    expect(resetOutcome({ ok: false }).variant).toBe('error');
  });
  it('no answer: may or may not have happened', () => {
    const o = resetOutcome(null, { message: '/api/setting: timed out', status: null });
    expect(o.variant).toBe('warn');
    expect(o.text).toContain('may or may not');
  });
  it('a refusal carries the reason', () => {
    expect(resetOutcome(null, { message: 'invalid token (HTTP 401)', status: 401 }).text).toBe('Refused: invalid token (HTTP 401)');
  });
});


describe('survey convergence', () => {
  it('epoch seconds → ms; zero, negative or missing values are gaps, not 0', () => {
    const s = convergenceSeries([[1000, 10, 2.5, 4.1], [2000, 20, 0, null], [3000, 30, null, null], [4000, 40, 0.8, 1.2]]);
    expect(s).toEqual([{ t: 1e6, horiz: 2.5, vert: 4.1 }, { t: 2e6, horiz: null, vert: null }, { t: 4e6, horiz: 0.8, vert: 1.2 }].filter(p => p.horiz !== null || p.vert !== null));
    expect(convergenceSeries(undefined)).toEqual([]);
  });
  it('log domain with margin, floored at 1 cm', () => {
    expect(logDomain([{ t: 0, horiz: 0.012, vert: 3 }])).toEqual([0.01, 4.5]);
    expect(logDomain([])).toBeNull();
  });
});

describe('session scatter', () => {
  const b = bullseye([[1, 0], [0, 2], [-1, -1]], { sd_lat_m: 2, sd_lon_m: 1.5, se_horiz_m: 0.1 }, 300);
  it('3 × scatter fills the plot; rings at 1, 2, 3 × scatter', () => {
    expect(b.sd).toBe(2);
    expect(b.rings[2]).toBeCloseTo(150 - 16);
  });
  it('north up, east right; newest fix most opaque', () => {
    expect(b.fixes[0].y).toBeLessThan(150);
    expect(b.fixes[1].x).toBeGreaterThan(150);
    expect(b.fixes[2].opacity).toBeGreaterThan(b.fixes[0].opacity);
  });
  it('the mean’s ring is at least 3 px so it stays visible', () => {
    expect(b.seRing).toBe(3);
    expect(bullseye([], {}, 300).seRing).toBeNull();
    expect(bullseye([], {}, 300).sd).toBe(0.5);
  });
});

describe('ingest and units', () => {
  it('rejections, largest first, zeros dropped', () => {
    expect(rejectedRows({ stale: 3, no_3d: 12, dup: 0 })).toEqual([['no_3d', 12], ['stale', 3]]);
    expect(rejectedRows(null)).toEqual([]);
  });
  it('metres', () => {
    expect(fmtMetres(0.04)).toBe('4 cm');
    expect(fmtMetres(0.18)).toBe('0.18 m');
    expect(fmtMetres(3.21)).toBe('3.2 m');
    expect(fmtMetres(12.4)).toBe('12 m');
    expect(fmtMetres(null)).toBeNull();
  });
});
