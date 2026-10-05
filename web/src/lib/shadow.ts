// Pure helpers for Sun & Astronomy → Earth Shadow and → Satellites
// (/api/shadow, /api/satellites): sky-map geometry, labels, ages.
// Tested in shadow.test.ts.

import type { SatelliteNow, ShadowMap, ShadowState } from '../api/types';

export type Variant = 'good' | 'warn' | 'error' | 'muted' | 'info';

export const SHELL_PRESETS = [350, 550, 1200];

/** For someone avoiding satellite trails: shadow is good, sunlight is the warning. */
export function stateVariant(state: ShadowState | undefined | null): Variant {
  return state === 'UMBRA' ? 'good' : state === 'PENUMBRA' ? 'info' : state === 'SUNLIT' ? 'warn' : 'muted';
}

export function stateLabel(state: ShadowState | undefined | null): string {
  return state === 'UMBRA' ? 'IN SHADOW (UMBRA)' : state === 'PENUMBRA' ? 'PENUMBRA' : state === 'SUNLIT' ? 'SUNLIT' : 'UNKNOWN';
}

export const STATE_FILL: Record<string, string> = {
  S: 'var(--warn-text)', P: 'var(--mod-text)', U: 'var(--t4)',
};
export const STATE_OPACITY: Record<string, number> = { S: 0.4, P: 0.55, U: 0.12 };

export interface MapSegment { code: 'S' | 'P' | 'U'; alt0: number; alt1: number; az0: number; az1: number }

/**
 * The sky grid as runs of equal state along each altitude ring, so a ring that
 * is all one state is one shape instead of 72. Each cell is centred on its
 * grid point; the rings at the horizon and the zenith are half cells.
 */
export function mapSegments(map: ShadowMap | undefined | null): MapSegment[] {
  if (!map) return [];
  const out: MapSegment[] = [];
  const dAlt = map.alt_step_deg / 2, dAz = map.az_step_deg / 2;
  map.rows.forEach((row, i) => {
    const alt = map.alts_deg[i];
    const alt0 = Math.max(0, alt - dAlt), alt1 = Math.min(90, alt + dAlt);
    let start = 0;
    for (let j = 1; j <= row.length; j++) {
      if (j === row.length || row[j] !== row[start]) {
        out.push({ code: row[start] as MapSegment['code'], alt0, alt1,
                   az0: map.azs_deg[start] - dAz, az1: map.azs_deg[j - 1] + dAz });
        start = j;
      }
    }
  });
  return out;
}

/** Sky position → plot coordinates: zenith at the centre, north up, east to the right. */
export function skyXY(az: number, alt: number, cx: number, cy: number, r: number): { x: number; y: number } {
  const p = (1 - alt / 90) * r;
  const a = (az - 90) * Math.PI / 180;
  return { x: cx + p * Math.cos(a), y: cy + p * Math.sin(a) };
}

/** Plot coordinates → sky position, or null outside the horizon circle. */
export function xyToSky(x: number, y: number, cx: number, cy: number, r: number): { az: number; alt: number } | null {
  const dx = x - cx, dy = y - cy;
  const p = Math.hypot(dx, dy);
  if (p > r) return null;
  const az = (Math.atan2(dy, dx) * 180 / Math.PI + 90 + 360) % 360;
  return { az: Math.round(az * 10) / 10, alt: Math.round((1 - p / r) * 900) / 10 };
}

/** SVG path of one annular sector. A full ring is drawn as two halves (an arc can't span 360°). */
export function segmentPath(s: MapSegment, cx: number, cy: number, r: number): string {
  const span = s.az1 - s.az0;
  if (span >= 359.999) {
    const mid = s.az0 + 180;
    return segmentPath({ ...s, az1: mid }, cx, cy, r) + ' ' + segmentPath({ ...s, az0: mid }, cx, cy, r);
  }
  const f = (n: number) => n.toFixed(2);
  const outer = (1 - s.alt0 / 90) * r, inner = (1 - s.alt1 / 90) * r;
  const a = skyXY(s.az0, s.alt0, cx, cy, r), b = skyXY(s.az1, s.alt0, cx, cy, r);
  const c = skyXY(s.az1, s.alt1, cx, cy, r), d = skyXY(s.az0, s.alt1, cx, cy, r);
  const large = span > 180 ? 1 : 0;
  return `M${f(a.x)},${f(a.y)} A${f(outer)},${f(outer)} 0 ${large} 1 ${f(b.x)},${f(b.y)} ` +
         `L${f(c.x)},${f(c.y)} A${f(inner)},${f(inner)} 0 ${large} 0 ${f(d.x)},${f(d.y)} Z`;
}

export function fmtKm(km: number | null | undefined): string | null {
  if (km === null || km === undefined || !Number.isFinite(km)) return null;
  return `${km >= 100 ? Math.round(km).toLocaleString('en-US') : km.toFixed(1)} km`;
}

export function fmtDeg(deg: number | null | undefined, digits = 1): string | null {
  if (deg === null || deg === undefined || !Number.isFinite(deg)) return null;
  return `${deg < 0 ? '−' : ''}${Math.abs(deg).toFixed(digits)}°`;
}

const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];

export function compass(az: number | null | undefined): string | null {
  if (az === null || az === undefined || !Number.isFinite(az)) return null;
  return COMPASS[Math.round((((az % 360) + 360) % 360) / 22.5) % 16];
}

/** A custom shell height typed by the user: 100 to 50 000 km, else null. */
export function parseShell(text: string): number | null {
  const v = Number(text.trim());
  return text.trim() !== '' && Number.isFinite(v) && v >= 100 && v <= 50000 ? v : null;
}

// ─── Satellites ──────────────────────────────────────────────────────────────

/** Age of orbital elements, shown prominently: "1.3 days old", "40 days old — unreliable". */
export function elementAge(ageDays: number | null | undefined, staleAfter = 14): { text: string; variant: Variant } {
  if (ageDays === null || ageDays === undefined || !Number.isFinite(ageDays)) return { text: 'AGE UNKNOWN', variant: 'muted' };
  const a = Math.abs(ageDays);
  const amount = a < 2 ? `${(a * 24).toFixed(0)} h` : `${a.toFixed(a < 10 ? 1 : 0)} days`;
  const text = ageDays < 0 ? `ELEMENTS DATED ${amount} AHEAD` : `ELEMENTS ${amount} OLD`;
  return a > staleAfter ? { text: `${text} · UNRELIABLE`, variant: 'error' }
       : a > staleAfter / 2 ? { text, variant: 'warn' } : { text, variant: 'good' };
}

export function fmtDurationShort(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined) return null;
  return `${Math.floor(seconds / 60)}m ${String(Math.round(seconds % 60)).padStart(2, '0')}s`;
}

/** One line for where a satellite is now. */
export function nowLine(s: SatelliteNow): string {
  if (!s.available) return s.reason ?? 'UNKNOWN';
  const where = s.above_horizon ? `${fmtDeg(s.altitude_deg)} up, ${compass(s.azimuth_deg)} (${fmtDeg(s.azimuth_deg, 0)})`
                                : `below the horizon (${fmtDeg(s.altitude_deg)})`;
  return `${where} · ${fmtKm(s.range_km)} away`;
}
