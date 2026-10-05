import { describe, expect, it } from 'vitest';
import {
  fmtUtcOffset, formatLocal, formatUtc, isDst, isValidZone, loadHour12, offsetMinutes, resolveZone, saveHour12, unixSeconds,
} from './localtime';
import { demoApi } from '@/api/demo';

const SUMMER = new Date('2026-07-04T00:14:05Z');   // EDT in New York
const WINTER = new Date('2026-01-15T17:05:09Z');   // EST

describe('resolveZone', () => {
  it("uses the operator's override", () => {
    expect(resolveZone({ tz: 'Europe/Paris', source: 'override', provenance: null, basis: null, note: '' }, 'UTC'))
      .toEqual({ tz: 'Europe/Paris', source: 'override', label: 'zone set by the operator' });
  });

  it('uses the zone the station found from its position', () => {
    const z = resolveZone({ tz: 'America/New_York', source: 'position', provenance: 'calculated', basis: 'exact', note: '' }, 'UTC');
    expect(z).toEqual({ tz: 'America/New_York', source: 'position', label: 'zone from station position' });
    expect(resolveZone({ tz: 'America/New_York', source: 'position', provenance: 'calculated', basis: 'rounded', note: '' }, 'UTC').label)
      .toBe('zone from station position (rounded)');
  });

  it("falls back to the browser's zone when the station sends none (hidden mode, no position, old station)", () => {
    const browser = { tz: 'Australia/Sydney', source: 'browser', label: "this browser's zone" };
    expect(resolveZone({ tz: null, source: null, provenance: null, basis: null, note: 'location is hidden' }, 'Australia/Sydney')).toEqual(browser);
    expect(resolveZone(undefined, 'Australia/Sydney')).toEqual(browser);
    expect(resolveZone(null, 'Australia/Sydney')).toEqual(browser);
  });

  it('ignores a zone name this browser does not know', () => {
    expect(resolveZone({ tz: 'Mars/Olympus_Mons', source: 'override', provenance: null, basis: null, note: '' }, 'UTC').source).toBe('browser');
    expect(isValidZone('Mars/Olympus_Mons')).toBe(false);
    expect(isValidZone('America/New_York')).toBe(true);
    expect(isValidZone(null)).toBe(false);
  });
});

describe('offset and DST', () => {
  it('offset in minutes east of UTC', () => {
    expect(offsetMinutes(SUMMER, 'America/New_York')).toBe(-240);
    expect(offsetMinutes(WINTER, 'America/New_York')).toBe(-300);
    expect(offsetMinutes(SUMMER, 'Asia/Kolkata')).toBe(330);
    expect(offsetMinutes(SUMMER, 'UTC')).toBe(0);
  });

  it('formats the offset with a real minus', () => {
    expect(fmtUtcOffset(-240)).toBe('UTC−4');
    expect(fmtUtcOffset(330)).toBe('UTC+5:30');
    expect(fmtUtcOffset(0)).toBe('UTC+0');
  });

  it('DST in both hemispheres, and never for zones without it', () => {
    expect(isDst(SUMMER, 'America/New_York')).toBe(true);
    expect(isDst(WINTER, 'America/New_York')).toBe(false);
    expect(isDst(WINTER, 'Australia/Sydney')).toBe(true);    // southern summer
    expect(isDst(SUMMER, 'Australia/Sydney')).toBe(false);
    expect(isDst(SUMMER, 'Asia/Kolkata')).toBe(false);
    expect(isDst(SUMMER, 'UTC')).toBe(false);
  });

  it('switches at the transition instant', () => {
    // US fall back: 2026-11-01 06:00:00Z (02:00 EDT -> 01:00 EST)
    expect(isDst(new Date('2026-11-01T05:59:59Z'), 'America/New_York')).toBe(true);
    expect(isDst(new Date('2026-11-01T06:00:00Z'), 'America/New_York')).toBe(false);
  });
});

describe('formatLocal', () => {
  it('12-hour with zone and DST', () => {
    expect(formatLocal(SUMMER, 'America/New_York', true))
      .toEqual({ time: '8:14:05 PM', date: 'Fri 2026-07-03', abbr: 'EDT', offset: 'UTC−4', dst: true });
  });

  it('24-hour, standard time', () => {
    expect(formatLocal(WINTER, 'America/New_York', false))
      .toEqual({ time: '12:05:09', date: 'Thu 2026-01-15', abbr: 'EST', offset: 'UTC−5', dst: false });
  });

  it('shows no made-up abbreviation where the browser only has an offset name', () => {
    const c = formatLocal(SUMMER, 'Europe/Paris', false);
    expect(c).toEqual({ time: '02:14:05', date: 'Sat 2026-07-04', abbr: '', offset: 'UTC+2', dst: true });
    expect(formatLocal(SUMMER, 'UTC', false)).toMatchObject({ abbr: 'UTC', offset: 'UTC+0', dst: false });
    expect(formatLocal(WINTER, 'Europe/London', false)).toMatchObject({ abbr: 'GMT', offset: 'UTC+0', dst: false });
  });

  it('midnight is 00 in 24-hour and 12 AM in 12-hour', () => {
    const midnight = new Date('2026-07-04T04:00:00Z');
    expect(formatLocal(midnight, 'America/New_York', false).time).toBe('00:00:00');
    expect(formatLocal(midnight, 'America/New_York', true).time).toBe('12:00:00 AM');
  });
});

describe('UTC and Unix epoch', () => {
  it('formats UTC and whole epoch seconds', () => {
    expect(formatUtc(SUMMER)).toBe('2026-07-04 00:14:05');
    expect(unixSeconds(SUMMER)).toBe(1783124045);
    expect(unixSeconds(new Date(1783124045999))).toBe(1783124045);
  });
});

describe('12/24-hour preference', () => {
  function memory() {
    const m = new Map<string, string>();
    return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => { m.set(k, v); } };
  }

  it('is remembered', () => {
    const s = memory();
    expect(loadHour12(s, false)).toBe(false);
    saveHour12(true, s);
    expect(loadHour12(s, false)).toBe(true);
    saveHour12(false, s);
    expect(loadHour12(s, true)).toBe(false);
  });

  it('survives missing or throwing storage', () => {
    expect(loadHour12(null, true)).toBe(true);
    const broken = { getItem: () => { throw new Error('denied'); }, setItem: () => { throw new Error('denied'); } };
    expect(loadHour12(broken, false)).toBe(false);
    expect(() => saveHour12(true, broken)).not.toThrow();
  });
});

describe('demo adapter mirrors the privacy rule', () => {
  it('hidden mode sends no position-derived zone; the override still applies', async () => {
    const api = demoApi();
    expect((await api.core()).timezone).toMatchObject({ tz: 'America/New_York', source: 'position' });
    await api.setLocationDisplay('hidden');
    expect((await api.core()).timezone).toMatchObject({ tz: null, source: null });
    await api.setTimezone('Europe/Paris');
    expect((await api.core()).timezone).toMatchObject({ tz: 'Europe/Paris', source: 'override' });
    await api.setTimezone(null);
    await api.setLocationDisplay('rounded');
    expect((await api.core()).timezone).toMatchObject({ tz: 'America/New_York', source: 'position', basis: 'rounded' });
  });
});
