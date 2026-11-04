import { describe, expect, it } from 'vitest';
import { confirmed, feederState, locationWarning, outcome, sharingSummary } from './feeders';
import { demoApi } from '../api/demo';
import type { FeederRow } from '../api/types';

const row = (over: Partial<FeederRow> = {}): FeederRow => ({
  name: 'adsbfi', service: 'adsb.fi', unit: 'gps-time-feed@adsbfi.service', on: false,
  active: { value: 'inactive', unit: null, provenance: 'observed' }, target: 'feed.adsb.fi:30004', confirm: 'adsb.fi', shares: '', ...over,
});

describe('feeders', () => {
  it('says exact location only when MLAT is on', () => {
    expect(locationWarning(row()).text).toContain("Doesn't share your location with adsb.fi");
    const pa = row({ name: 'piaware', service: 'FlightAware', mlat: { on: true, allowed: true, confirm: 'share my exact location', refused: null } });
    expect(locationWarning(pa)).toEqual({ text: 'Shares your exact location with FlightAware.', variant: 'warn' });
  });

  it('warns on the PiAware card with MLAT off too', () => {
    const pa = row({ name: 'piaware', service: 'FlightAware', mlat: { on: false, allowed: true, confirm: 'share my exact location', refused: null } });
    const w = locationWarning(pa);
    expect(w.variant).toBe('warn');
    expect(w.text).toMatch(/^Shares your location with FlightAware/);
    expect(w.text).toContain('exact location only with MLAT, which is off');
    const hidden = row({ name: 'piaware', service: 'FlightAware', mlat: { on: false, allowed: false, confirm: 'share my exact location', refused: 'MLAT is refused in hidden privacy mode' } });
    expect(locationWarning(hidden).variant).toBe('warn');
  });

  it('states follow the switch and the unit', () => {
    expect(feederState(row()).label).toBe('OFF');
    expect(feederState(row({ on: true, active: { value: 'active', unit: null, provenance: 'observed' } })).label).toBe('SENDING');
    expect(feederState(row({ on: true, active: { value: null, unit: null, provenance: 'observed' } })).label).toBe('UNKNOWN');
  });

  it('needs the confirmation typed exactly', () => {
    expect(confirmed('adsb.fi', 'adsb.fi')).toBe(true);
    expect(confirmed('adsb.fi ', 'adsb.fi')).toBe(false);
    expect(confirmed('ADSB.FI', 'adsb.fi')).toBe(false);
  });

  it('the demo refuses without the typed name, and MLAT in hidden mode', async () => {
    const api = demoApi();
    await expect(api.setFeeder('airplaneslive', true, 'nope')).rejects.toThrow('type "airplanes.live"');
    await expect(api.setFeeder('airplaneslive', true, 'airplanes.live')).resolves.toMatchObject({ ok: true });
    await api.setLocationDisplay('hidden');
    await expect(api.setFeederMlat('piaware', true, 'share my exact location')).rejects.toThrow('hidden privacy mode');
    const st = await api.feeders();
    expect(sharingSummary(st).variant).not.toBe('warn');
  });

  it('reports the outcome', () => {
    expect(outcome('adsb.fi on', null, { message: 'x', status: 403 }).variant).toBe('error');
    expect(outcome('adsb.fi on', { ok: true, simulated: true } as never).text).toContain('demo');
  });
});
