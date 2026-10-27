import { describe, expect, it } from 'vitest';
import type { SdrStatus, SdrUnit } from '../api/types';
import { dongleRow, feedRow, sdrSummary, unitRows, unitState } from './sdr';
import { demoApi } from '../api/demo';

const m = <T,>(value: T | null, unit: string | null = null) => ({ value, unit, provenance: 'observed' as const });
const unit = (o: Partial<SdrUnit> = {}): SdrUnit => ({
  unit: 'gps-time-readsb.service', what: 'readsb (1090 MHz)', active: m('active'), sub: 'running', enabled: 'enabled',
  restarts: m(0), cpu_s: m(30), cpu_avg_pct: { ...m(25), provenance: 'calculated' }, memory_mib: m(20), ...o,
});
const st = (o: Partial<SdrStatus> = {}): SdrStatus => ({ installed: true, units: [unit()], dongles: [], feeds: [], note: '', ...o });

describe('SDR receivers', () => {
  it('says UNKNOWN or not installed rather than guessing', () => {
    expect(sdrSummary(st({ installed: null, units: null })).text).toMatch(/^UNKNOWN/);
    expect(sdrSummary(st({ installed: false, units: [] })).text).toMatch(/GTP_SDR=1/);
    expect(sdrSummary(st()).text).toBe('1 of 1 receiver units running');
    expect(sdrSummary(st({ units: [unit(), unit({ unit: 'x', active: m('failed') }),
      unit({ unit: 'gps-time-modules.service' })] }))).toEqual({ text: '1 of 2 receiver units running', variant: 'warn' });
  });

  it('unit states and figures as reported', () => {
    expect(unitState(unit()).label).toBe('RUNNING');
    expect(unitState(unit({ active: m('inactive'), enabled: 'disabled' })).label).toBe('OFF');
    expect(unitState(unit({ active: m('inactive') })).label).toBe('STOPPED');
    expect(unitState(unit({ active: m(null) })).label).toBe('UNKNOWN');
    expect(unitRows(st())[0]).toMatchObject({ cpu: '25 %', memory: '20 MiB', restarts: '0' });
    expect(unitRows(st({ units: [unit({ cpu_avg_pct: m(null), restarts: m(null) })] }))[0]).toMatchObject({ cpu: null, restarts: null });
  });

  it('flags a dongle the DVB driver holds or a slow port', () => {
    const d = { port: '1-1.2', serial: '00001090', product: null, role: '1090 MHz', speed_mbps: m(480), dvb_driver: m(false) };
    expect(dongleRow(d)).toMatchObject({ role: '1090 MHz', speed: '480 Mb/s', problem: null });
    expect(dongleRow({ ...d, dvb_driver: m(true) }).problem).toMatch(/DVB-T driver/);
    expect(dongleRow({ ...d, speed_mbps: m(12) }).problem).toMatch(/high speed/);
    expect(dongleRow({ ...d, role: null, serial: null })).toMatchObject({ serial: 'UNKNOWN', role: expect.stringMatching(/no role/) });
  });

  it('feeds: age and counts only', () => {
    const f = { band: '1090' as const, path: '/run/readsb/aircraft.json', present: true, age_s: m(3), aircraft: m(2), fresh: true };
    expect(feedRow(f)).toEqual({ band: '1090 MHz', state: { label: 'FRESH', variant: 'good' }, age: '3s ago', aircraft: '2' });
    expect(feedRow({ ...f, fresh: false }).state.label).toBe('STALE');
    expect(feedRow({ ...f, present: false, age_s: m(null), aircraft: m(null) })).toMatchObject({ state: { label: 'NO FILE' }, age: null });
  });

  it('the demo answer has the station shape and says it is synthetic', async () => {
    const d = await demoApi().sdr();
    expect(d.note).toMatch(/synthetic/);
    expect(d.units?.map(u => u.unit)).toContain('gps-time-readsb.service');
    expect(JSON.stringify(d)).not.toMatch(/38\.92|77\.06/);
  });
});
