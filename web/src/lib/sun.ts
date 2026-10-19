// Day-to-day shifts of sunrise, solar noon, sunset and daylight length, from
// the almanac's predicted times (/api/almanac → sun, neighbors). The shifts are
// predicted too.
//
// An event's shift is (later instant − earlier instant − 86 400 s). That's the
// solar change, without any clock change: on a DST switch day the wall clock
// moves by an extra hour, which `clockChange` reports instead of mixing it in.
// Daylight shifts use the server's delta_yesterday / delta_tomorrow.

import type { Almanac } from '@/api/types';

export type SunEvent = 'sunrise' | 'noon' | 'sunset' | 'daylight';

export interface Shift {
  vsYesterday: number | null;   // today − yesterday, s
  toTomorrow: number | null;    // tomorrow − today, s
}

export interface SunShifts {
  rows: Record<SunEvent, Shift>;
  /** True if the UTC offset differs between yesterday, today and tomorrow (DST switch). */
  clockChange: boolean;
}

const DAY_S = 86400;

function instant(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t / 1000 : null;
}

/** Shift of one event from one day to the next, in s; null if either is missing. */
export function shiftSeconds(earlier: string | null | undefined, later: string | null | undefined): number | null {
  const a = instant(earlier), b = instant(later);
  return a === null || b === null ? null : b - a - DAY_S;
}

function offset(iso: string | null | undefined): string | null {
  const m = iso?.match(/(Z|[+-]\d\d:?\d\d)$/);
  return m ? m[1].replace('Z', '+00:00') : null;
}

function finite(x: number | null | undefined): number | null {
  return typeof x === 'number' && Number.isFinite(x) ? x : null;
}

export function sunShifts(almanac: Almanac): SunShifts | null {
  const sun = almanac.sun;
  if (!sun.available) return null;
  const y = almanac.neighbors?.yesterday ?? {}, t = almanac.neighbors?.tomorrow ?? {};
  const today = { sunrise: sun.events.sunrise, noon: sun.noon, sunset: sun.events.sunset };
  const ev = (k: 'sunrise' | 'noon' | 'sunset'): Shift => ({
    vsYesterday: shiftSeconds(y[k], today[k]),
    toTomorrow: shiftSeconds(today[k], t[k]),
  });
  const offsets = new Set([y.sunrise, today.sunrise, t.sunrise, y.noon, today.noon, t.noon].map(offset).filter(Boolean));
  return {
    rows: {
      sunrise: ev('sunrise'),
      noon: ev('noon'),
      sunset: ev('sunset'),
      daylight: { vsYesterday: finite(almanac.delta_yesterday), toTomorrow: finite(almanac.delta_tomorrow) },
    },
    clockChange: offsets.size > 1,
  };
}

/**
 * Signed shift in hours, minutes and seconds, whole seconds:
 * "+56 s", "−2 m 11 s", "+1 h 00 m 05 s" (U+2212 minus), "0 s". null stays null (UNKNOWN).
 */
export function fmtShift(s: number | null | undefined): string | null {
  if (s === null || s === undefined || !Number.isFinite(s)) return null;
  const r = Math.round(s);
  if (r === 0) return '0 s';
  const sign = r > 0 ? '+' : '−';
  const a = Math.abs(r), h = Math.floor(a / 3600), m = Math.floor((a % 3600) / 60), sec = a % 60;
  const p2 = (n: number) => String(n).padStart(2, '0');
  if (h) return `${sign}${h} h ${p2(m)} m ${p2(sec)} s`;
  if (m) return `${sign}${m} m ${p2(sec)} s`;
  return `${sign}${sec} s`;
}
