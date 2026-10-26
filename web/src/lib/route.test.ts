import { describe, expect, it } from 'vitest';
import { hashFor, pageFromHash, PAGE_IDS } from './route';

describe('route', () => {
  it('reads the page from the hash', () => {
    expect(pageFromHash('#timing')).toBe('timing');
    expect(pageFromHash('#/admin')).toBe('admin');
    expect(pageFromHash('#PPS')).toBe('pps');
    expect(pageFromHash('#gnss?x=1')).toBe('gnss');
  });
  it('falls back to the Overview', () => {
    expect(pageFromHash('')).toBe('overview');
    expect(pageFromHash('#nope')).toBe('overview');
    expect(pageFromHash('#constructor')).toBe('overview');
  });
  it('round-trips every page', () => {
    for (const p of PAGE_IDS) expect(pageFromHash(hashFor(p))).toBe(p);
  });
});
