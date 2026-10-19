import { describe, expect, it } from 'vitest';
import { STATION_ACTIONS, actionInfo, actionOutcome } from './admin';
import type { AdminAction } from '../api/types';

const ALL: AdminAction[] = ['flush_logs', 'restart_gpsd', 'restart_chrony', 'restart_web', 'reboot'];

describe('station actions', () => {
  it('one entry per action the station knows (system.ADMIN_ACTIONS), in a fixed order', () => {
    expect(STATION_ACTIONS.map(a => a.action)).toEqual(ALL);
  });

  it('everything that interrupts timing or the page asks first; flushing the log does not', () => {
    expect(actionInfo('flush_logs').confirm).toBeNull();
    for (const a of ALL.filter(a => a !== 'flush_logs')) expect(actionInfo(a).confirm).toMatch(/\?/);
  });

  it('never names a cause or claims timing is unaffected', () => {
    for (const a of STATION_ACTIONS) expect(`${a.effect} ${a.confirm ?? ''}`).not.toMatch(/no effect|unaffected|safe/i);
  });
});

describe('actionOutcome', () => {
  it("reports the station's answer", () => {
    expect(actionOutcome('flush_logs', { ok: true, action: 'flush_logs', detail: '' })).toEqual({ variant: 'good', text: 'Flush logs to SD now: done.' });
    expect(actionOutcome('restart_gpsd', { ok: false, action: 'restart_gpsd', detail: 'Interactive authentication required.' }))
      .toEqual({ variant: 'error', text: 'Restart gpsd: failed (Interactive authentication required.).' });
  });

  it('restart_web and reboot: accepted, and the page expects to lose the station', () => {
    const o = actionOutcome('reboot', { ok: true, action: 'reboot', detail: 'rebooting in 2 s' });
    expect(o.variant).toBe('good');
    expect(o.text).toContain('accepted (rebooting in 2 s)');
    expect(o.text).toContain('unreachable');
  });

  it('demo: says it was not executed', () => {
    expect(actionOutcome('reboot', { ok: true, action: 'reboot', detail: 'x', simulated: true }).text).toBe('Reboot the Pi: demo, not executed.');
  });

  it('no answer is not a failure: it may have run', () => {
    const o = actionOutcome('restart_chrony', null, { message: '/api/admin: timed out', status: null });
    expect(o.variant).toBe('warn');
    expect(o.text).toContain('may still have run');
  });

  it('an HTTP refusal (wrong token) is an error with the reason', () => {
    expect(actionOutcome('restart_chrony', null, { message: 'invalid token (HTTP 401)', status: 401 }))
      .toEqual({ variant: 'error', text: 'Restart chrony: refused. invalid token (HTTP 401)' });
  });
});
