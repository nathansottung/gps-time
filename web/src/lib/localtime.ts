// Local-time display for the main clock. Display only: the station, its API
// and its logs stay on UTC.
//
// Which zone: the station's answer (/api → timezone: the operator's override,
// or the zone found from the station's position), else this browser's zone.
// In hidden privacy mode the station sends no position-derived zone, so the
// override or the browser's zone is used.
//
// Offsets, abbreviations and DST come from the browser's own time-zone
// database (Intl), for the zone named above.

import type { DisplayZone } from '@/api/types';

export type ZoneSource = 'override' | 'position' | 'browser';

export interface ResolvedZone {
  tz: string;
  source: ZoneSource;
  /** Short text for the clock, e.g. "zone from station position". */
  label: string;
}

export function isValidZone(tz: string | null | undefined): tz is string {
  if (!tz) return false;
  try { new Intl.DateTimeFormat('en-US', { timeZone: tz }); return true; } catch { return false; }
}

export function browserZone(): string {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch { return 'UTC'; }
}

const LABEL: Record<ZoneSource, string> = {
  override: 'zone set by the operator',
  position: 'zone from station position',
  browser: "this browser's zone",
};

/** The station's zone if it sent a usable one, else the browser's. */
export function resolveZone(station: DisplayZone | null | undefined, browserTz: string = browserZone()): ResolvedZone {
  if (station && station.source && isValidZone(station.tz)) {
    const rounded = station.source === 'position' && station.basis === 'rounded' ? ' (rounded)' : '';
    return { tz: station.tz, source: station.source, label: LABEL[station.source] + rounded };
  }
  return { tz: isValidZone(browserTz) ? browserTz : 'UTC', source: 'browser', label: LABEL.browser };
}

/** IANA zone names this browser knows, for the override picker; empty on old browsers. */
export function zoneNames(): string[] {
  try {
    const f = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf;
    return f ? f('timeZone') : [];
  } catch { return []; }
}

/** Minutes east of UTC for a zone at an instant. */
export function offsetMinutes(at: Date, tz: string): number {
  const p = new Intl.DateTimeFormat('en-US', {
    timeZone: tz, hourCycle: 'h23', year: 'numeric', month: 'numeric', day: 'numeric',
    hour: 'numeric', minute: 'numeric', second: 'numeric',
  }).formatToParts(at);
  const n = (t: string) => Number(p.find(x => x.type === t)?.value);
  const asUtc = Date.UTC(n('year'), n('month') - 1, n('day'), n('hour'), n('minute'), n('second'));
  return Math.round((asUtc - Math.floor(at.getTime() / 1000) * 1000) / 60000);
}

/** "UTC−4", "UTC+5:30", "UTC+0" (U+2212 minus). */
export function fmtUtcOffset(minutes: number): string {
  const a = Math.abs(minutes), h = Math.floor(a / 60), m = a % 60;
  return `UTC${minutes < 0 ? '−' : '+'}${h}${m ? ':' + String(m).padStart(2, '0') : ''}`;
}

/**
 * Whether daylight-saving time is in effect: the offset now is ahead of the
 * zone's standard offset, taken as the smaller of its January and July offsets
 * in that year (so it works in both hemispheres). Zones without DST: false.
 */
export function isDst(at: Date, tz: string): boolean {
  const y = at.getUTCFullYear();
  const jan = offsetMinutes(new Date(Date.UTC(y, 0, 1, 12)), tz);
  const jul = offsetMinutes(new Date(Date.UTC(y, 6, 1, 12)), tz);
  return jan !== jul && offsetMinutes(at, tz) > Math.min(jan, jul);
}

export interface LocalClock {
  time: string;     // "8:14:05 PM" or "20:14:05"
  date: string;     // "Sun 2026-10-04"
  abbr: string;     // "EDT"; "" where the browser has only an offset name ("GMT+2"), which `offset` already shows
  offset: string;   // "UTC−4"
  dst: boolean;
}

export function formatLocal(at: Date, tz: string, hour12: boolean): LocalClock {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: tz, hourCycle: hour12 ? 'h12' : 'h23', weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: hour12 ? 'numeric' : '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short',
  }).formatToParts(at);
  const g = (t: string) => parts.find(x => x.type === t)?.value ?? '';
  const hms = `${g('hour')}:${g('minute')}:${g('second')}`;
  return {
    time: hour12 ? `${hms} ${g('dayPeriod')}` : hms,
    date: `${g('weekday')} ${g('year')}-${g('month')}-${g('day')}`,
    abbr: /^(GMT|UTC)[+-]/.test(g('timeZoneName').replace('−', '-')) ? '' : g('timeZoneName'),
    offset: fmtUtcOffset(offsetMinutes(at, tz)),
    dst: isDst(at, tz),
  };
}

/** "2026-10-05 00:14:05" */
export function formatUtc(at: Date): string {
  return at.toISOString().slice(0, 19).replace('T', ' ');
}

/** Whole seconds since 1970-01-01T00:00:00Z. */
export function unixSeconds(at: Date): number {
  return Math.floor(at.getTime() / 1000);
}

// ─── 12/24-hour preference, remembered per browser ───────────────────────────

const KEY = 'gtp-clock-hour12';
type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

function store(storage?: StorageLike | null): StorageLike | null {
  if (storage !== undefined) return storage;
  try { return typeof localStorage !== 'undefined' ? localStorage : null; } catch { return null; }
}

/** The locale's own habit, used until the viewer chooses. */
export function localeHour12(): boolean {
  try { return new Intl.DateTimeFormat(undefined, { hour: 'numeric' }).resolvedOptions().hour12 === true; } catch { return false; }
}

export function loadHour12(storage?: StorageLike | null, fallback: boolean = localeHour12()): boolean {
  try {
    const v = store(storage)?.getItem(KEY);
    return v === '12' ? true : v === '24' ? false : fallback;
  } catch { return fallback; }
}

export function saveHour12(hour12: boolean, storage?: StorageLike | null): void {
  try { store(storage)?.setItem(KEY, hour12 ? '12' : '24'); } catch { /* storage unavailable: the choice lasts for this page */ }
}
