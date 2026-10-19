import { describe, expect, it } from 'vitest';
import { resetConfirmed, resetOutcome, surveyLoss } from './survey';

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
