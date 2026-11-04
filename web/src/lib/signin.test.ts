import { describe, expect, it } from 'vitest';
import { sessionLine, signInOutcome, signInState } from './signin';
import type { AuthState } from '../api/types';

const a = (over: Partial<AuthState> = {}): AuthState => ({ demo: false, auth_required: true, admin_configured: true, authenticated: false, ...over });

describe('admin sign-in', () => {
  it('says signed in or out from the station, UNKNOWN when it cannot tell', () => {
    expect(signInState(null, true).label).toBe('UNKNOWN');
    expect(signInState(a(), false)).toMatchObject({ label: 'SIGNED OUT', variant: 'warn' });
    expect(signInState(a({ authenticated: true }), false).label).toBe('SIGNED IN');
    expect(signInState(a({ admin_configured: false }), false).label).toContain('DISABLED');
    expect(signInState(a({ demo: true, authenticated: true }), false).label).toContain('DEMO');
  });

  it('describes how long this browser stays signed in', () => {
    const now = Date.parse('2026-11-04T12:00:00Z');
    expect(sessionLine(a(), now)).toBeNull();
    expect(sessionLine(a({ authenticated: true, session: { expires_utc: '2026-11-05T00:00:00+00:00', remembered: false } }), now))
      .toContain('until this browser closes');
    expect(sessionLine(a({ authenticated: true, session: { expires_utc: '2026-12-04T12:00:00+00:00', remembered: true } }), now))
      .toBe('This browser is remembered until 2026-12-04 (30 days).');
  });

  it('reports wrong tokens, the backoff and no answer', () => {
    expect(signInOutcome(null, { status: 401, message: '' }).text).toBe('Wrong admin token.');
    expect(signInOutcome(null, { status: 429, message: '' }).text).toContain('Too many');
    expect(signInOutcome(null, { status: null, message: 'timeout' }).variant).toBe('warn');
    expect(signInOutcome({ ok: true }).text).toBe('Signed in.');
    expect(signInOutcome({ ok: true, simulated: true }).variant).toBe('muted');
  });
});
