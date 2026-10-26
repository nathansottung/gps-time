// Pure helpers for Timing → Oscillator (/api/oscillator). Tested in oscillator.test.ts.

import type { OscillatorBin, OscillatorFit, OscillatorProfile } from '../api/types';
import { fmtSci } from './units';

export interface OscPoint { ts: number; temp: number | null; freq: number | null; pps: boolean }

/** Bins as chart points. A bin counts as "PPS" only if PPS was selected for all of it. */
export function oscPoints(bins: OscillatorBin[] | undefined): OscPoint[] {
  return (bins ?? []).map(b => ({
    ts: Date.parse(b.t), temp: b.temp_mean_c, freq: b.freq_mean_ppm, pps: b.pps_samples === b.samples,
  }));
}

/** Points for the frequency-against-temperature scatter: both values present. */
export function scatterPoints(points: OscPoint[], ppsOnly: boolean) {
  return points.filter(p => p.temp !== null && p.freq !== null && (!ppsOnly || p.pps))
               .map(p => ({ x: p.temp as number, y: p.freq as number }));
}

/** The fitted line across the temperature range of the points, or [] without a fit. */
export function fitLine(fit: OscillatorFit | undefined, points: { x: number }[]) {
  if (!fit || fit.slope_ppm_per_c === null || fit.intercept_ppm === null || points.length < 2) return [];
  const xs = points.map(p => p.x);
  const lo = Math.min(...xs), hi = Math.max(...xs);
  return [lo, hi].map(x => ({ x, y: fit.intercept_ppm! + fit.slope_ppm_per_c! * x }));
}

/** "−0.250 ppm/°C (−2.50 × 10⁻⁷ per °C)" style slope text; null without one. */
export function fmtSlope(slope: number | null | undefined): string | null {
  if (slope === null || slope === undefined || !Number.isFinite(slope)) return null;
  const sign = slope < 0 ? '−' : '+';
  return `${sign}${Math.abs(slope).toFixed(3)} ppm/°C`;
}

export function fmtBytes(n: number | null | undefined): string | null {
  if (n === null || n === undefined) return null;
  return n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n >= 1024 ? `${(n / 1024).toFixed(0)} kB` : `${n} B`;
}

/** Span of the log in days, from the first bin to the last. */
export function spanDays(points: OscPoint[]): number | null {
  if (points.length < 2) return null;
  return (points[points.length - 1].ts - points[0].ts) / 86400e3;
}

// ─── The fitted profile (/api/oscillator → profile; modeled) ────────────────

/** The profile's frequency (ppm) at a temperature, at the end of the span it covers. */
export function profileAt(p: OscillatorProfile, tempC: number): number | null {
  if (p.status !== 'fitted' || p.temp_ref_c === null || p.t0_utc_epoch === null || !p.covers) return null;
  const c = Object.fromEntries(p.terms.map(t => [t.name, t.value])) as Record<string, number>;
  const dT = tempC - p.temp_ref_c, days = (p.covers.last_utc_epoch - p.t0_utc_epoch) / 86400;
  return (c.a ?? 0) + (c.b ?? 0) * dT + (c.c ?? 0) * dT * dT + (c.d ?? 0) * days;
}

/** The fitted curve across the temperature range the fit covers (never beyond it). */
export function profileCurve(p: OscillatorProfile | undefined, steps = 24): { x: number; y: number }[] {
  if (!p || p.status !== 'fitted' || !p.covers) return [];
  const { temp_min_c: lo, temp_max_c: hi } = p.covers;
  return Array.from({ length: steps + 1 }, (_, i) => lo + (hi - lo) * i / steps)
    .map(x => ({ x, y: profileAt(p, x) as number }));
}

const TERM_LABEL: Record<string, string> = {
  a: 'Δf/f at the reference temperature', b: 'Temperature coefficient', c: 'Curvature', d: 'Aging',
};
const TERM_UNIT: Record<string, [string, string]> = {
  a: ['', 'ppm'], b: [' per °C', 'ppm/°C'], c: [' per °C²', 'ppm/°C²'], d: [' per day', 'ppm/day'],
};

/** One term as Δf/f (×10⁻ⁿ, Guidelines), ± its standard error, with ppm in brackets. */
export function fmtTerm(t: { name: string; value: number; se: number }): { label: string; text: string } {
  const [per, ppm] = TERM_UNIT[t.name] ?? ['', ''];
  const sign = t.value < 0 ? '−' : t.name === 'a' ? '' : '+';
  const sci = fmtSci(Math.abs(t.value) * 1e-6, 3);
  const se = fmtSci(t.se * 1e-6, 2);
  const ppmText = (t.value < 0 ? '−' : '') + Math.abs(t.value).toFixed(t.name === 'a' ? 3 : 4);
  return { label: TERM_LABEL[t.name] ?? t.name, text: `${sign}${sci} ± ${se}${per} (${ppmText} ${ppm})` };
}

export const MODEL_LABEL: Record<string, string> = {
  linear: 'linear in temperature', quadratic: 'quadratic in temperature',
  'linear+aging': 'linear in temperature, plus aging', 'quadratic+aging': 'quadratic in temperature, plus aging',
};
