import { describe, expect, it } from 'vitest';
import { fmtShift, shiftSeconds, sunShifts } from './sun';
import { demoApi } from '@/api/demo';
import type { Almanac } from '@/api/types';

function almanac(over: Partial<Almanac> = {}): Almanac {
  return {
    available: true,
    sun: { available: true, date: '2026-10-02', tz: 'America/New_York',
           events: { sunrise: '2026-10-02T07:05:56-04:00', sunset: '2026-10-02T18:47:00-04:00' },
           noon: '2026-10-02T12:56:28-04:00', daylight_s: 42064, bar: [], notes: [] },
    moon: { available: false, reason: 'n/a' },
    night: { available: false },
    delta_yesterday: -142.4, delta_tomorrow: -142.9,
    neighbors: {
      yesterday: { sunrise: '2026-10-01T07:05:00-04:00', sunset: '2026-10-01T18:48:26.4-04:00',
                   noon: '2026-10-01T12:56:47-04:00', daylight_s: 42206.4 },
      tomorrow:  { sunrise: '2026-10-03T07:06:53-04:00', sunset: '2026-10-03T18:45:34-04:00',
                   noon: '2026-10-03T12:56:09-04:00', daylight_s: 41921.1 },
    },
    sky: {}, sky_when: '', position_provenance: 'live', position_age: null,
    ...over,
  } as Almanac;
}

describe('shiftSeconds', () => {
  it('is the change in clock time from one day to the next', () => {
    expect(shiftSeconds('2026-10-01T07:05:00-04:00', '2026-10-02T07:05:56-04:00')).toBe(56);
    expect(shiftSeconds('2026-10-01T18:48:26-04:00', '2026-10-02T18:47:00-04:00')).toBe(-86);
  });

  it('is null when either event is missing (polar day/night) or unparseable', () => {
    expect(shiftSeconds(null, '2026-10-02T07:05:56-04:00')).toBeNull();
    expect(shiftSeconds('2026-10-01T07:05:00-04:00', undefined)).toBeNull();
    expect(shiftSeconds('not a time', '2026-10-02T07:05:56-04:00')).toBeNull();
  });

  it('excludes a DST clock change', () => {
    // US fall-back night 2026-11-01: wall clock moves back 1 h; the sun only ~+1 min
    expect(shiftSeconds('2026-10-31T07:40:00-04:00', '2026-11-01T06:41:05-05:00')).toBe(65);
  });
});

describe('sunShifts', () => {
  it('signs every event: today − yesterday and tomorrow − today', () => {
    const s = sunShifts(almanac())!;
    expect(s.rows.sunrise).toEqual({ vsYesterday: 56, toTomorrow: 57 });
    expect(s.rows.noon).toEqual({ vsYesterday: -19, toTomorrow: -19 });
    expect(s.rows.sunset.vsYesterday).toBeCloseTo(-86.4, 6);
    expect(s.rows.sunset.toTomorrow).toBe(-86);
    expect(s.rows.daylight).toEqual({ vsYesterday: -142.4, toTomorrow: -142.9 });
    expect(s.clockChange).toBe(false);
  });

  it('keeps missing values null instead of 0', () => {
    const a = almanac({ delta_tomorrow: null, neighbors: { yesterday: {}, tomorrow: { sunrise: null } } });
    const s = sunShifts(a)!;
    expect(s.rows.sunrise).toEqual({ vsYesterday: null, toTomorrow: null });
    expect(s.rows.daylight.toTomorrow).toBeNull();
  });

  it('flags a clock change between the days', () => {
    const a = almanac();
    a.neighbors.tomorrow.sunrise = '2026-10-03T06:06:53-05:00';
    expect(sunShifts(a)!.clockChange).toBe(true);
  });

  it('is null when the sun is unavailable', () => {
    expect(sunShifts(almanac({ sun: { available: false, reason: 'x' } }))).toBeNull();
  });

  it('demo adapter neighbors are consistent with its daylight deltas', async () => {
    const a = await demoApi().almanac({});
    if (!a.available) throw new Error('demo almanac unavailable');
    const s = sunShifts(a)!;
    for (const k of ['vsYesterday', 'toTomorrow'] as const) {
      const fromEvents = s.rows.sunset[k]! - s.rows.sunrise[k]!;
      expect(Math.abs(fromEvents - s.rows.daylight[k]!)).toBeLessThanOrEqual(1);
      expect(s.rows.noon[k]).not.toBeNull();
    }
  });
});

describe('fmtShift', () => {
  it('signed whole seconds with a real minus sign', () => {
    expect(fmtShift(56.4)).toBe('+56 s');
    expect(fmtShift(-131.3)).toBe('−131 s');
    expect(fmtShift(0.4)).toBe('0 s');
    expect(fmtShift(-0.4)).toBe('0 s');
  });

  it('null stays null (shown as unknown)', () => {
    expect(fmtShift(null)).toBeNull();
    expect(fmtShift(undefined)).toBeNull();
    expect(fmtShift(NaN)).toBeNull();
  });
});
