// Time scales shown on Timing → Time Scales, calculated from the station's
// UTC instant and the TAI − UTC offset the station reports (/api/timescales).
// Pure; tested in timescales.test.ts. No offset is assumed here: without the
// station's value, TAI and GPS time are UNKNOWN (null).

import type { LeapSeconds } from '../api/types';

const GPS_EPOCH_UNIX = 315964800;   // 1980-01-06T00:00:00Z
const TAI_GPS_S = 19;
const MJD_UNIX_EPOCH = 40587;       // MJD of 1970-01-01
const WEEK_S = 604800;

export interface ScaleValues {
  unix: number;
  tai: string | null;               // 'YYYY-MM-DD HH:MM:SS'
  gps: string | null;
  gpsUtcS: number | null;
  gpsWeek: number | null;
  gpsWeekMod1024: number | null;
  gpsSecondsOfWeek: number | null;
  mjd: string;                      // 5 decimals (0.86 s)
  jd: string;
}

const pad = (n: number) => String(n).padStart(2, '0');

/** A second count on a scale without leap seconds, written as a calendar date and time. */
function clock(unixLike: number): string {
  const d = new Date(unixLike * 1000);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ` +
         `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}

export function scaleValues(at: Date, taiUtcS: number | null | undefined): ScaleValues {
  const ms = at.getTime();
  const unix = Math.floor(ms / 1000);
  const mjd = ms / 86400000 + MJD_UNIX_EPOCH;
  const out: ScaleValues = {
    unix, tai: null, gps: null, gpsUtcS: null, gpsWeek: null, gpsWeekMod1024: null, gpsSecondsOfWeek: null,
    mjd: mjd.toFixed(5), jd: (mjd + 2400000.5).toFixed(5),
  };
  if (taiUtcS === null || taiUtcS === undefined || !Number.isFinite(taiUtcS)) return out;
  out.tai = clock(unix + taiUtcS);
  out.gpsUtcS = taiUtcS - TAI_GPS_S;
  const gpsS = unix + out.gpsUtcS - GPS_EPOCH_UNIX;
  if (gpsS >= 0) {
    out.gps = clock(unix + out.gpsUtcS);
    out.gpsWeek = Math.floor(gpsS / WEEK_S);
    out.gpsWeekMod1024 = out.gpsWeek % 1024;
    out.gpsSecondsOfWeek = gpsS % WEEK_S;
  }
  return out;
}

export type LeapVariant = 'good' | 'warn' | 'error' | 'muted';

export function leapVariant(status: LeapSeconds['status'] | undefined): LeapVariant {
  return status === 'OK' ? 'good' : status === 'EXPIRES_SOON' ? 'warn' : status === 'EXPIRED' ? 'error' : 'muted';
}

export function leapLabel(status: LeapSeconds['status'] | undefined): string {
  return status === 'OK' ? 'TABLE VALID' : status === 'EXPIRES_SOON' ? 'TABLE EXPIRES SOON'
       : status === 'EXPIRED' ? 'TABLE EXPIRED' : 'EXPIRY UNKNOWN';
}

/** "UTC + 37 s" / "UTC − 1 s"; null without a value. */
export function fmtScaleOffset(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return null;
  return `UTC ${seconds < 0 ? '−' : '+'} ${Math.abs(seconds)} s`;
}

/** UT1 − UTC in milliseconds with a sign, e.g. "+70.4 ms". */
export function fmtUt1(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return null;
  return `${seconds < 0 ? '−' : '+'}${Math.abs(seconds * 1000).toFixed(1)} ms`;
}

/** "2026-12-28 (84 days)" for the expiry line. */
export function fmtExpiry(expiresUtc: string | null | undefined, days: number | null | undefined): string | null {
  if (!expiresUtc) return null;
  const date = expiresUtc.slice(0, 10);
  if (days === null || days === undefined) return date;
  return days >= 0 ? `${date} (in ${Math.floor(days)} days)` : `${date} (${Math.ceil(-days)} days ago)`;
}
