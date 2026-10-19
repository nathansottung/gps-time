// Sun & Astronomy → Sky & Objects (legacy /almanac sky map and object lookup; parity 11, 12).
// Lays out what /api/almanac (sky) and /api/object return; computes no positions itself.
// Same projection as the other /app/ sky plots (lib/shadow.ts skyXY): north up, east right.
import type { ObjectReport, ObjectWindow, SkySnapshot } from '../api/types';
import { skyXY } from './shadow';
import { timeOnDay } from './almanac';

export interface SkyLayout {
  stars: { x: number; y: number; r: number }[];
  lines: string[];                        // SVG polyline points, one per run above the horizon
  bodies: { name: string; x: number; y: number; r: number }[];
  target: { x: number; y: number } | 'below' | null;
}

/** Brighter stars are bigger: magnitude 0 → 3 px, 5 and fainter → 0.6 px. */
export function starRadius(mag: number): number {
  return Math.max(0.6, Math.min(3.5, (5 - mag) * 0.6));
}

export function isSky(s: unknown): s is SkySnapshot {
  return !!s && typeof s === 'object' && (s as { available?: unknown }).available === true && Array.isArray((s as SkySnapshot).stars);
}

export function skyLayout(sky: SkySnapshot, cx: number, cy: number, r: number): SkyLayout {
  const xy = (alt: number, az: number) => skyXY(az, alt, cx, cy, r);
  const fmt = (p: { x: number; y: number }) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  const lines: string[] = [];
  for (const line of sky.lines) {
    let run: string[] = [];
    for (const [alt, az] of line) {
      if (alt > 0) run.push(fmt(xy(alt, az)));
      else { if (run.length > 1) lines.push(run.join(' ')); run = []; }   // never draw across the horizon
    }
    if (run.length > 1) lines.push(run.join(' '));
  }
  return {
    stars: sky.stars.filter(([alt]) => alt > 0).map(([alt, az, mag]) => ({ ...xy(alt, az), r: starRadius(mag) })),
    lines,
    bodies: Object.entries(sky.bodies).filter(([, [alt]]) => alt > 0)
      .map(([name, [alt, az]]) => ({ name, ...xy(alt, az), r: name === 'Sun' || name === 'Moon' ? 6 : 3.4 })),
    target: !sky.target ? null : sky.target[0] > 0 ? xy(sky.target[0], sky.target[1]) : 'below',
  };
}

/** The ?at= value: "now", or HH:MM on the selected date. */
export function atParam(useNow: boolean, time: string): string {
  return !useNow && /^([01]\d|2[0-3]):[0-5]\d$/.test(time) ? time : 'now';
}

const fmtWindows = (w: ObjectWindow[], day: string, tz: string) =>
  w.length ? w.map(x => `${timeOnDay(x.start, day, tz)}–${timeOnDay(x.end, day, tz)}`).join(', ') : 'none on this date';

/** The object card's rows, in the legacy order; the window that matters most for this kind of object first. */
export function objectRows(o: ObjectReport, day: string, tz: string): [string, string, string?][] {
  const t = (iso: string | null) => timeOnDay(iso, day, tz) ?? 'none this day';
  const rows: [string, string, string?][] = [
    ['Object', o.name, o.meta || undefined],
    [`At ${o.at_label}`, `${o.now_alt.toFixed(1)}° alt, ${Math.round(o.now_az)}° az`, o.now_alt <= 0 ? 'below the horizon' : undefined],
  ];
  if (o.never_up) rows.push(['Visibility', 'Never rises from this latitude']);
  else if (o.circumpolar) rows.push(['Visibility', 'Circumpolar: always up', `highest at meridian transit ${t(o.transit)}`]);
  else rows.push(['Rise', t(o.rise)]);
  if (!o.never_up) rows.push(['Meridian transit', t(o.transit), o.transit_alt == null ? undefined : `reaches ${o.transit_alt.toFixed(1)}° altitude`]);
  if (!o.never_up && !o.circumpolar) rows.push(['Set', t(o.set)]);
  const dark: [string, string, string] = ['Dark viewing window', fmtWindows(o.dark_windows, day, tz), `object above ${o.min_alt_deg}°, sun below −18°`];
  const moonless: [string, string, string] = ['Moonless viewing window', fmtWindows(o.moonless_windows, day, tz), 'and the moon below the horizon'];
  rows.push(...(o.emphasis === 'moonless' ? [moonless, dark] : [dark, moonless]));
  return rows;
}
