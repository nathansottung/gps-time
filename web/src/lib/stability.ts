// Pure helpers for the Stability tab (/api/stability): chart rows, log-axis
// ticks and labels. Tested in stability.test.ts.

import type { StabilityPoint } from '../api/types';
import { fmtSci } from './units';

export type StabilityMetric = 'adev' | 'mdev' | 'tdev';

export const METRIC_LABEL: Record<StabilityMetric, string> = {
  adev: 'Allan deviation (ADEV)', mdev: 'Modified Allan deviation (MDEV)', tdev: 'Time deviation (TDEV)',
};

export interface StabilityRow {
  tau: number;
  v: number;
  /** [below, above] the value, for the confidence bar; absent when no interval was calculated. */
  err?: [number, number];
  point: StabilityPoint;
}

const value = (p: StabilityPoint, metric: StabilityMetric): number | null =>
  metric === 'adev' ? p.adev : metric === 'mdev' ? p.mdev : p.tdev_s;

/** Rows for a log–log plot. A point without a positive value is left out, never drawn as zero. */
export function chartRows(points: StabilityPoint[] | undefined, metric: StabilityMetric): StabilityRow[] {
  const rows: StabilityRow[] = [];
  for (const p of points ?? []) {
    const v = value(p, metric);
    if (v === null || !(v > 0) || !(p.tau_s > 0)) continue;
    const row: StabilityRow = { tau: p.tau_s, v, point: p };
    if (metric === 'adev' && p.adev_low !== null && p.adev_high !== null && p.adev_low > 0) {
      row.err = [v - p.adev_low, p.adev_high - v];
    }
    rows.push(row);
  }
  return rows.sort((a, b) => a.tau - b.tau);
}

/** Whole decades covering [min, max], e.g. 3e-10..4e-7 -> [1e-10, 1e-9, 1e-8, 1e-7, 1e-6]. */
export function decadeTicks(min: number, max: number): number[] {
  if (!(min > 0) || !(max > 0) || max < min) return [];
  const lo = Math.floor(Math.log10(min) + 1e-9);
  const hi = Math.ceil(Math.log10(max) - 1e-9);
  return Array.from({ length: Math.max(hi, lo + 1) - lo + 1 }, (_, i) => 10 ** (lo + i));
}

/** Lowest and highest value drawn, confidence bars included. */
export function valueExtent(rows: StabilityRow[]): [number, number] | null {
  if (!rows.length) return null;
  let lo = Infinity, hi = -Infinity;
  for (const r of rows) {
    lo = Math.min(lo, r.v - (r.err?.[0] ?? 0));
    hi = Math.max(hi, r.v + (r.err?.[1] ?? 0));
  }
  return [lo, hi];
}

export function fmtTau(s: number): string {
  if (s >= 86400 && s % 86400 === 0) return s === 86400 ? '1 day' : `${s / 86400} days`;
  if (s >= 3600 && s % 3600 === 0) return `${s / 3600} h`;
  return `${s} s`;
}

/** A deviation for the table: ×10⁻ⁿ for the dimensionless ones, a time for TDEV. */
export function fmtDeviation(v: number | null | undefined, metric: StabilityMetric): string | null {
  if (v === null || v === undefined || !Number.isFinite(v)) return null;
  if (metric !== 'tdev') return fmtSci(v, 3);
  const a = Math.abs(v);
  const [k, unit] = a < 1e-6 ? [1e9, 'ns'] : a < 1e-3 ? [1e6, 'µs'] : a < 1 ? [1e3, 'ms'] : [1, 's'];
  return `${(v * k).toPrecision(3)} ${unit}`;
}

/** "4.32 – 4.39 × 10⁻⁸"-style interval, or null when none was calculated. */
export function fmtInterval(p: StabilityPoint): string | null {
  if (p.adev_low === null || p.adev_high === null) return null;
  return `${fmtSci(p.adev_low, 3)} to ${fmtSci(p.adev_high, 3)}`;
}
