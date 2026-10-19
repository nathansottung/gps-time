import { describe, expect, it } from 'vitest';
import { DATE_MAX, DATE_MIN, dayBar, fmtHoursMinutes, isSupportedDate, nightView, shiftDate, timeOnDay, todayIn } from './almanac';
import type { NightBar } from '../api/types';

describe('date navigation', () => {
  it('steps across months, years and DST changes by calendar day', () => {
    expect(shiftDate('2026-10-31', 1)).toBe('2026-11-01');
    expect(shiftDate('2026-11-01', 1)).toBe('2026-11-02');   // US DST ends this day
    expect(shiftDate('2027-01-01', -1)).toBe('2026-12-31');
    expect(shiftDate('2028-02-28', 1)).toBe('2028-02-29');
  });
  it('stays inside the ephemeris range', () => {
    expect(shiftDate(DATE_MIN, -1)).toBe(DATE_MIN);
    expect(shiftDate(DATE_MAX, 1)).toBe(DATE_MAX);
  });
  it('accepts only real dates in range', () => {
    expect(isSupportedDate('2026-10-19')).toBe(true);
    expect(isSupportedDate('1849-12-31')).toBe(false);
    expect(isSupportedDate('2150-01-01')).toBe(false);
    expect(isSupportedDate('2026-02-30')).toBe(false);
    expect(isSupportedDate('19-10-2026')).toBe(false);
  });
  it("today is the zone's date, not UTC's", () => {
    const late = new Date('2026-10-20T02:30:00Z');   // 22:30 on the 19th in New York
    expect(todayIn('America/New_York', late)).toBe('2026-10-19');
    expect(todayIn('UTC', late)).toBe('2026-10-20');
  });
});

describe('day bar', () => {
  it('lays segments end to end in percent of the day', () => {
    const b = dayBar([
      { state: 0, start: '2026-10-19T00:00:00-04:00', frac: 0.25 },
      { state: 4, start: '2026-10-19T06:00:00-04:00', frac: 0.5 },
      { state: 0, start: '2026-10-19T18:00:00-04:00', frac: 0.25 },
    ]);
    expect(b.map(x => [x.left, x.width, x.label])).toEqual([[0, 25, 'Night'], [25, 50, 'Day'], [75, 25, 'Night']]);
  });
  it('drops what it cannot place instead of guessing', () => {
    expect(dayBar([{ state: 9, start: 'x', frac: 0.5 }, { state: 1, start: 'x', frac: Number.NaN }])).toEqual([]);
    expect(dayBar(undefined)).toEqual([]);
  });
});

const NIGHT: NightBar = {
  available: true, defined: true, sunset: '2026-10-19T18:30:00-04:00', sunrise: '2026-10-20T07:20:00-04:00', span_s: 46200,
  sun_segments: [{ stage: 3, f0: 0, f1: 0.04 }, { stage: 0, f0: 0.12, f1: 0.88 }],
  moon_up: [{ f0: 0, f1: 0.3 }],
  dark: [{ f0: 0.3, f1: 0.88, start: '2026-10-19T22:21-04:00', end: '2026-10-20T05:47-04:00' }],
  dark_total_s: 26820, midnight: { f: 0.428, label: 'midnight · Tue 20' }, astro_note: null, tz: 'America/New_York',
};

describe('night bar', () => {
  it('maps the station’s fractions to percent, with the darkness total', () => {
    const v = nightView(NIGHT);
    expect(v && v.defined).toBe(true);
    if (!v || !v.defined) return;
    expect(v.stages[1]).toMatchObject({ label: 'Night', left: 12, width: 76 });
    expect(v.moonUp).toEqual([{ left: 0, width: 30 }]);
    expect(v.dark[0]).toMatchObject({ left: 30, start: '2026-10-19T22:21-04:00' });
    expect(v.dark[0].width).toBeCloseTo(58);
    expect(v.darkTotal).toBe('7 h 27 min');
    expect(v.midnight?.label).toBe('midnight · Tue 20');
  });
  it('no night, or none sent', () => {
    expect(nightView({ available: true, defined: false, note: 'No sunset-to-sunrise night on this date at this latitude.' }))
      .toEqual({ defined: false, note: 'No sunset-to-sunrise night on this date at this latitude.' });
    expect(nightView({ available: false, reason: 'hidden' })).toBeNull();
    expect(nightView(null)).toBeNull();
  });
  it('durations', () => {
    expect(fmtHoursMinutes(0)).toBe('0 min');
    expect(fmtHoursMinutes(35 * 60)).toBe('35 min');
    expect(fmtHoursMinutes(3600 * 4 + 60 * 5)).toBe('4 h 05 min');
  });
});

describe('timeOnDay', () => {
  it('adds the date only when the event is on another day', () => {
    expect(timeOnDay('2026-10-19T19:51:00-04:00', '2026-10-19', 'America/New_York')).toBe('19:51');
    expect(timeOnDay('2026-10-20T01:33:00-04:00', '2026-10-19', 'America/New_York')).toBe('01:33 · 20 Oct');
    expect(timeOnDay(null, '2026-10-19', 'UTC')).toBeNull();
  });
});
