import { describe, expect, it } from 'vitest';
import { ageLine, mapState, markerLine, uatState } from './aircraftmap';
import type { AircraftMapStatus } from '../api/types';

const st = (over: Partial<AircraftMapStatus> = {}): AircraftMapStatus => ({
  installed: true, url: '/tar1090/', state: 'live', aircraft_json_age_s: 0.6, aircraft: 12,
  station_marker: true, location_display: 'exact', note: '', ...over,
});

describe('aircraft map', () => {
  it('says live, paused for the web SDR, stale, no data and not installed', () => {
    expect(mapState(st()).label).toBe('LIVE');
    expect(mapState(st({ state: 'paused' }))).toMatchObject({ label: 'PAUSED', variant: 'warn' });
    expect(mapState(st({ state: 'paused' })).text).toContain('web SDR');
    expect(mapState(st({ state: 'stale' })).label).toBe('STALE');
    expect(mapState(st({ state: 'no_data' })).label).toBe('NO DATA');
    expect(mapState(st({ installed: false })).label).toBe('NOT INSTALLED');
  });

  it('never claims a station marker in hidden mode', () => {
    expect(markerLine(st({ location_display: 'hidden', station_marker: false }))).toContain('hidden');
    expect(markerLine(st({ location_display: 'rounded' }))).toContain('0.1°');
    expect(markerLine(st({ station_marker: false }))).toContain('no surveyed position');
    expect(markerLine(st())).toBe('shown');
  });

  it('formats the data age', () => {
    expect(ageLine(null)).toBeNull();
    expect(ageLine(0.64)).toBe('0.6 s');
    expect(ageLine(42.4)).toBe('42 s');
  });

  it('says what the 978 MHz map is doing, and UNKNOWN for a station that does not say', () => {
    const u = { installed: true, url: '/skyaware978/', state: 'live' as const, aircraft_json_age_s: 1.4, aircraft: 3 };
    expect(uatState(u)).toMatchObject({ label: 'LIVE', variant: 'good' });
    expect(uatState({ ...u, state: 'paused' }).text).toContain('web SDR');
    expect(uatState({ ...u, state: 'stale' }).label).toBe('STALE');
    expect(uatState({ ...u, state: 'no_data' }).label).toBe('NO DATA');
    expect(uatState({ ...u, installed: false }).label).toBe('NOT INSTALLED');
    expect(uatState(undefined).label).toBe('UNKNOWN');
  });
});
