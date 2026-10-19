// Sun & Astronomy → Sun & Moon: date navigation, the 24 h twilight bar and the night bar
// (legacy /almanac, parity items 8, 9, 10). All values come from /api/almanac (predicted);
// nothing here computes astronomy, it only lays out what the station sent.
import type { NightBar, SunBarSegment } from '../api/types';

/** The station's ephemeris range (astro.DATE_MIN/DATE_MAX, JPL DE440s). */
export const DATE_MIN = '1850-01-01';
export const DATE_MAX = '2149-12-31';

const YMD = /^\d{4}-\d{2}-\d{2}$/;

export function isSupportedDate(d: string): boolean {
  if (!YMD.test(d)) return false;
  const t = Date.parse(`${d}T12:00:00Z`);
  return Number.isFinite(t) && new Date(t).toISOString().slice(0, 10) === d && d >= DATE_MIN && d <= DATE_MAX;
}

/** Calendar arithmetic on YYYY-MM-DD (noon UTC, so no zone or DST can move the day); clamped to the range. */
export function shiftDate(d: string, days: number): string {
  const t = new Date(`${d}T12:00:00Z`);
  t.setUTCDate(t.getUTCDate() + days);
  const out = t.toISOString().slice(0, 10);
  return out < DATE_MIN ? DATE_MIN : out > DATE_MAX ? DATE_MAX : out;
}

/** Today's date in a zone, YYYY-MM-DD. */
export function todayIn(tz: string, now: Date = new Date()): string {
  try { return now.toLocaleDateString('en-CA', { timeZone: tz }); } catch { return now.toISOString().slice(0, 10); }
}

// Sky states, darkest to brightest. Colors are tokens in index.css (--sky-*).
export const SKY_STATES = [
  { state: 0, label: 'Night',                 color: 'var(--sky-night)' },
  { state: 1, label: 'Astronomical twilight', color: 'var(--sky-astro)' },
  { state: 2, label: 'Nautical twilight',     color: 'var(--sky-naut)' },
  { state: 3, label: 'Civil twilight',        color: 'var(--sky-civil)' },
  { state: 4, label: 'Day',                   color: 'var(--sky-day)' },
] as const;

export interface BarPiece { state: number; label: string; color: string; left: number; width: number; start: string | null }

/** Day bar pieces in percent of the 24 h day. Unknown states or bad fractions are dropped, never guessed. */
export function dayBar(bar: SunBarSegment[] | null | undefined): BarPiece[] {
  const out: BarPiece[] = [];
  let left = 0;
  for (const seg of bar ?? []) {
    const st = SKY_STATES[seg.state];
    if (!st || !Number.isFinite(seg.frac) || seg.frac < 0) continue;
    const width = seg.frac * 100;
    out.push({ state: seg.state, label: st.label, color: st.color, left, width, start: seg.start ?? null });
    left += width;
  }
  return out;
}

export interface NightView {
  defined: true;
  sunset: string; sunrise: string;
  stages: { stage: number; label: string; color: string; left: number; width: number }[];
  moonUp: { left: number; width: number }[];
  dark: { left: number; width: number; start: string; end: string }[];
  darkTotal: string;           // "4 h 12 min", "35 min", "0 min"
  midnight: { left: number; label: string } | null;
  note: string | null;         // e.g. no astronomical darkness tonight
}

const pct = (f: number) => Math.min(100, Math.max(0, f * 100));
const span = (f0: number, f1: number) => ({ left: pct(f0), width: Math.max(0, pct(f1) - pct(f0)) });

export function fmtHoursMinutes(s: number): string {
  const m = Math.round(s / 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')} min` : `${m} min`;
}

/** The night bar, or why there is none. null = the station did not send one (UNKNOWN). */
export function nightView(n: NightBar | null | undefined): NightView | { defined: false; note: string } | null {
  if (!n || !n.available) return null;
  if (!n.defined) return { defined: false, note: n.note ?? 'No sunset-to-sunrise night on this date.' };
  return {
    defined: true,
    sunset: n.sunset, sunrise: n.sunrise,
    stages: n.sun_segments.filter(x => SKY_STATES[x.stage]).map(x => ({
      stage: x.stage, label: SKY_STATES[x.stage].label, color: SKY_STATES[x.stage].color, ...span(x.f0, x.f1) })),
    moonUp: n.moon_up.map(x => span(x.f0, x.f1)),
    dark: n.dark.map(x => ({ ...span(x.f0, x.f1), start: x.start, end: x.end })),
    darkTotal: fmtHoursMinutes(n.dark_total_s),
    midnight: n.midnight ? { left: pct(n.midnight.f), label: n.midnight.label } : null,
    note: n.astro_note,
  };
}

/**
 * A clock time for an event that may fall on another calendar day than the one shown
 * (moonset after midnight, the night's sunrise): "01:33 · 21 Oct". Same day: just the time.
 */
export function timeOnDay(iso: string | null | undefined, day: string, tz: string, seconds = false): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const t = d.toLocaleTimeString('en-GB', { timeZone: tz, hour: '2-digit', minute: '2-digit', second: seconds ? '2-digit' : undefined, hour12: false });
  const onDay = d.toLocaleDateString('en-CA', { timeZone: tz });
  return onDay === day ? t : `${t} · ${d.toLocaleDateString('en-GB', { timeZone: tz, day: 'numeric', month: 'short' })}`;
}
