import { describe, expect, it } from 'vitest';
import type { SdrAircraftDecoder, SdrFeed } from '../api/types';
import { decoderState, fmtRate, mapLine, rateLine, serialLine, unitsLine } from './aircraftstack';

const m = <T,>(value: T, unit: string | null = null) => ({ value, unit, provenance: 'observed' as const });
const feed = (over: Partial<SdrFeed> = {}): SdrFeed => ({
  band: '1090', path: '/run/readsb/aircraft.json', present: true, age_s: m(0.5, 's'), aircraft: m(12, 'count'),
  messages_per_s: { value: 412.3, unit: 'msg/s', provenance: 'calculated' }, fresh: true, ...over });
const dec = (over: Partial<SdrAircraftDecoder> = {}): SdrAircraftDecoder => ({
  band: '1090', decoder: 'readsb', units: [{ unit: 'gps-time-readsb.service', state: 'active' }], serial: '1090',
  serial_plugged: m(true), paused_by_websdr: false, map: { name: 'tar1090', url: '/tar1090/', installed: true },
  feed: feed(), ...over });

describe('decoderState', () => {
  it('is LIVE only with a fresh file', () => {
    expect(decoderState(dec()).label).toBe('LIVE');
    expect(decoderState(dec({ feed: feed({ fresh: false }) })).label).toBe('STALE');
    expect(decoderState(dec({ feed: feed({ present: false, fresh: false }) })).label).toBe('NO DATA');
  });
  it('shows a restart loop as ACTIVATING and a crash as FAILED', () => {
    const s = decoderState(dec({ units: [{ unit: 'gps-time-readsb.service', state: 'activating' }] }));
    expect(s.label).toBe('ACTIVATING');
    expect(s.text).toContain('restart loop');
    expect(decoderState(dec({ units: [{ unit: 'gps-time-readsb.service', state: 'failed' }] })).variant).toBe('error');
  });
  it('is PAUSED only when the web SDR has its dongle', () => {
    const s = decoderState(dec({ paused_by_websdr: true }));
    expect(s.label).toBe('PAUSED');
    expect(s.text).toContain('dongle 1090');
  });
  it('is OFF with no serial, UNKNOWN when systemctl is unreadable', () => {
    const off = decoderState(dec({ band: '978', serial: null }));
    expect(off.label).toBe('OFF');
    expect(off.text).toContain('978 MHz stays off');
    expect(decoderState(dec({ units: [{ unit: 'gps-time-readsb.service', state: null }] })).label).toBe('UNKNOWN');
    expect(decoderState(dec({ units: [{ unit: 'gps-time-readsb.service', state: 'not installed' }] })).label).toBe('NOT INSTALLED');
  });
  it('needs every unit of the 978 pair active', () => {
    const d = dec({ band: '978', units: [{ unit: 'gps-time-dump978.service', state: 'active' },
                                        { unit: 'gps-time-skyaware978.service', state: 'inactive' }] });
    expect(decoderState(d).label).toBe('INACTIVE');
  });
});

describe('lines', () => {
  it('serial, units, rate and map', () => {
    expect(serialLine(dec())).toBe('1090 (on USB)');
    expect(serialLine(dec({ serial_plugged: m(false) }))).toBe('1090 (not on USB now)');
    expect(serialLine(dec({ serial_plugged: m<boolean | null>(null) as never }))).toBe('1090');
    expect(serialLine(dec({ serial: null }))).toBe('none');
    expect(unitsLine(dec())).toBe('gps-time-readsb: active');
    expect(rateLine(dec())).toBe(412.3);
    expect(rateLine(dec({ feed: undefined }))).toBeNull();
    expect(fmtRate(412.3)).toBe('412');
    expect(fmtRate(6.84)).toBe('6.8');
    expect(fmtRate(null)).toBeNull();
    expect(mapLine(dec())).toEqual({ text: 'tar1090 at /tar1090/', link: true });
    expect(mapLine(dec({ map: { name: 'skyaware978', url: '/skyaware978/', installed: false } })).link).toBe(false);
  });
});
