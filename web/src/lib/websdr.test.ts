import { describe, expect, it } from 'vitest';
import { compareRows, hfLine, loginLine, sessionLine, websdrOutcome, websdrState, websdrUrl } from './websdr';
import type { Measured, WebSdrStatus, WebSdrSummary } from '../api/types';

const m = (value: number | null, provenance: Measured['provenance'] = 'calculated'): Measured<number> => ({ value, unit: null, provenance });
const summary = (cpu: number | null, jit: number | null, minutes = 10): WebSdrSummary => ({
  minutes, cpu_mean_pct: m(cpu), cpu_max_pct: m(cpu, 'observed'), websdr_cpu_mean_pct: m(null),
  temp_mean_c: m(50), temp_max_c: m(51, 'observed'), pps_jitter_median_ns: m(jit), pps_jitter_max_ns: m(jit),
  pps_max_abs_ns: m(1200, 'observed'), pps_pulses: m(60 * minutes - 2, 'observed'),
});
const status = (installed: boolean | null, active: string | null): WebSdrStatus => ({
  installed, active: { value: active, unit: null, provenance: 'observed' }, port: 8073, serial: 'x', max_hours: 4,
  usage: { session: null, baseline: null, recent: [], file: { name: 'f', error: null }, note: '' }, note: '',
});

describe('websdr', () => {
  it('says whether the login is on, and UNKNOWN (null) when the station does not say', () => {
    const st = status(true, 'inactive');
    expect(loginLine(st)).toBeNull();
    expect(loginLine({ ...st, auth: { enabled: null, remember_days: null } })).toBeNull();
    expect(loginLine({ ...st, auth: { enabled: false, remember_days: null } })).toContain('anyone on the LAN');
    expect(loginLine({ ...st, auth: { enabled: true, remember_days: 30 } })).toContain('30 days');
  });

  it('names the HF profiles the installer set', () => {
    expect(hfLine(undefined)).toBeNull();
    expect(hfLine('off')).toContain('24 MHz');
    expect(hfLine('direct')).toContain('Q branch');
    expect(hfLine('native')).toContain('HF path');
  });

  it('reports sign-out-all from the station answer', () => {
    expect(websdrOutcome('websdr_signout_all', { ok: true, action: 'websdr_signout_all', detail: '' }).text).toContain('sign in again');
    expect(websdrOutcome('websdr_signout_all', { ok: true, action: 'websdr_signout_all', simulated: true, detail: '' }).text).toContain('demo');
  });

  it('builds the LAN address from the host name and the gate port', () => {
    expect(websdrUrl('192.0.2.10', 8073)).toBe('http://192.0.2.10:8073/');
    expect(websdrUrl('fe80::1', 8073)).toBe('http://[fe80::1]:8073/');
    expect(websdrUrl('[fe80::1]', 8073)).toBe('http://[fe80::1]:8073/');
    expect(websdrUrl('station', null)).toBeNull();
  });

  it('says UNKNOWN when it cannot tell, and running only when active', () => {
    expect(websdrState(status(null, null)).label).toBe('UNKNOWN');
    expect(websdrState(status(false, null)).label).toBe('NOT INSTALLED');
    expect(websdrState(status(true, 'active'))).toMatchObject({ label: 'RUNNING', running: true });
    expect(websdrState(status(true, 'inactive')).running).toBe(false);
    expect(websdrState(status(true, 'failed')).label).toContain('TIME LIMIT');
  });

  it('compares before with during and keeps UNKNOWN as null', () => {
    const rows = compareRows(summary(10, 420), summary(38, 566, 15));
    expect(rows[0]).toMatchObject({ before: '10.0 %', during: '38.0 %' });
    const jitter = rows.find(r => r.label.startsWith('PPS jitter, median'))!;
    expect(jitter).toMatchObject({ before: '420 ns', during: '566 ns', provenance: 'calculated' });
    expect(rows.find(r => r.label.startsWith('Web SDR'))!.during).toBeNull();
    expect(rows.at(-1)).toMatchObject({ before: '598 of 600', during: '898 of 900' });
    expect(compareRows(null, summary(1, 2))[0].before).toBeNull();
  });

  it('formats a session line', () => {
    expect(sessionLine('2026-11-03T18:00:00+00:00', 2700, 45)).toBe('2026-11-03 18:00:00 UTC · 45m 00s');
    expect(sessionLine('2026-11-03T18:00:00+00:00', null, 7)).toContain('7 min so far');
  });

  it('reports the station answer, never a guess', () => {
    expect(websdrOutcome('websdr_start', { ok: true, action: 'websdr_start', detail: '' }, undefined, 'readsb (1090 MHz)').text).toContain('readsb (1090 MHz) is stopped');
    expect(websdrOutcome('websdr_start', { ok: true, action: 'websdr_start', detail: '' }, undefined, null).text).toContain('No other service');
    expect(websdrOutcome('websdr_stop', { ok: false, action: 'websdr_stop', detail: 'Unit not found' }).variant).toBe('error');
    expect(websdrOutcome('websdr_start', null, { message: 'timed out', status: null }).variant).toBe('warn');
    expect(websdrOutcome('websdr_start', { ok: true, action: 'websdr_start', detail: 'd', simulated: true }).text).toContain('demo');
  });
});
