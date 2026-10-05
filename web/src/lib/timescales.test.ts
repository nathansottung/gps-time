import { describe, expect, it } from 'vitest';
import { fmtExpiry, fmtScaleOffset, fmtUt1, leapLabel, leapVariant, scaleValues } from './timescales';
import { demoApi } from '../api/demo';

const at = (iso: string) => new Date(iso);

describe('scaleValues', () => {
  it('TAI and GPS time from the station offset', () => {
    const v = scaleValues(at('2026-10-05T02:23:20Z'), 37);
    expect(v.unix).toBe(1791167000);
    expect(v.tai).toBe('2026-10-05 02:23:57');
    expect(v.gps).toBe('2026-10-05 02:23:38');
    expect(v.gpsUtcS).toBe(18);
  });

  it('GPS week and seconds of week (weeks start on Sunday)', () => {
    const v = scaleValues(at('2026-10-05T02:23:20Z'), 37);    // a Monday
    expect(v.gpsWeek).toBe(2439);
    expect(v.gpsWeekMod1024).toBe(391);
    expect(v.gpsSecondsOfWeek).toBe(86400 + 2 * 3600 + 23 * 60 + 38);
  });

  it('known epochs: GPS start and the first week rollover', () => {
    const start = scaleValues(at('1980-01-06T00:00:00Z'), 19);
    expect([start.gpsWeek, start.gpsSecondsOfWeek, start.gpsUtcS]).toEqual([0, 0, 0]);
    const rollover = scaleValues(at('1999-08-21T23:59:47Z'), 32);
    expect([rollover.gpsWeek, rollover.gpsWeekMod1024, rollover.gpsSecondsOfWeek]).toEqual([1024, 0, 0]);
  });

  it('Julian dates', () => {
    const j2000 = scaleValues(at('2000-01-01T12:00:00Z'), 32);
    expect(j2000.mjd).toBe('51544.50000');
    expect(j2000.jd).toBe('2451545.00000');
    expect(scaleValues(at('2026-10-05T02:23:20Z'), 37).mjd).toBe('61318.09954');
  });

  it('without the station offset TAI and GPS are unknown, never assumed', () => {
    for (const missing of [null, undefined, NaN]) {
      const v = scaleValues(at('2026-10-05T02:23:20Z'), missing);
      expect([v.tai, v.gps, v.gpsWeek, v.gpsSecondsOfWeek, v.gpsUtcS]).toEqual([null, null, null, null, null]);
      expect(v.mjd).toBe('61318.09954');
    }
  });

  it('the calendar rolls over with the offset', () => {
    expect(scaleValues(at('2026-12-31T23:59:50Z'), 37).tai).toBe('2027-01-01 00:00:27');
  });
});

describe('labels', () => {
  it('leap-table status', () => {
    expect([leapVariant('OK'), leapVariant('EXPIRES_SOON'), leapVariant('EXPIRED'), leapVariant('UNKNOWN'), leapVariant(undefined)])
      .toEqual(['good', 'warn', 'error', 'muted', 'muted']);
    expect(leapLabel('EXPIRED')).toBe('TABLE EXPIRED');
    expect(leapLabel(undefined)).toBe('EXPIRY UNKNOWN');
  });

  it('offsets and UT1', () => {
    expect(fmtScaleOffset(37)).toBe('UTC + 37 s');
    expect(fmtScaleOffset(-1)).toBe('UTC − 1 s');
    expect(fmtScaleOffset(null)).toBeNull();
    expect(fmtUt1(0.0704)).toBe('+70.4 ms');
    expect(fmtUt1(-0.1234567)).toBe('−123.5 ms');
    expect(fmtUt1(null)).toBeNull();
  });

  it('expiry', () => {
    expect(fmtExpiry('2026-12-28T00:00:00+00:00', 83.9)).toBe('2026-12-28 (in 83 days)');
    expect(fmtExpiry('2026-12-28T00:00:00+00:00', -35.2)).toBe('2026-12-28 (36 days ago)');
    expect(fmtExpiry(null, null)).toBeNull();
  });
});

describe('demo adapter', () => {
  it('serves the station shape, with no UT1 file', async () => {
    const t = await demoApi().timescales();
    expect(t.provenance).toBe('calculated');
    expect(t.tai_utc_s.value).toBe(37);
    expect(t.gps_utc_s.value).toBe(18);
    expect(t.leap_seconds.provenance).toBe('external');
    expect(t.leap_seconds.status).toBe('OK');
    expect(t.ut1.available).toBe(false);
    expect(t.ut1.ut1_utc_s).toBeNull();
  });
});
