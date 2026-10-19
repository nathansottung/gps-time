// Pure helpers for Timing → Oscillator (/api/oscillator). Tested in oscillator.test.ts.

import type { OscillatorBin, OscillatorFit } from '../api/types';

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
