// Value axes for time-offset and stability charts, linear or logarithmic (Guidelines → Charts →
// Axis scale). Values are seconds (or dimensionless for ADEV/MDEV); labels carry their own unit
// (ns, µs, ms, s), so an axis never needs a separate unit caption.
//
// Signed data (offsets) use a symmetric-log axis on "log": linear within ±lin, one decade per
// step beyond, so zero and both signs stay on the chart. Positive data (delays, holdover error,
// ADEV) use a plain log axis. Nothing here changes the data; it only places and labels it.
import { symexp, symlog } from './offset';

export type AxisScale = 'linear' | 'log';

/** Seconds per unit, for series already scaled to a unit (lib/references.ts, api/view.ts). */
export const UNIT_S: Record<string, number> = { ps: 1e-12, ns: 1e-9, 'µs': 1e-6, us: 1e-6, ms: 1e-3, s: 1 };

const MINUS = '−';
const trim = (s: string) => (s.includes('.') ? s.replace(/\.?0+$/, '') : s);

/** A time with the unit that fits: "0", "850 ns", "1.5 µs", "−12 ms", "2 s", "0.35 ns". */
export function fmtTime(v: number): string {
  if (!Number.isFinite(v)) return '—';
  if (v === 0) return '0';
  const a = Math.abs(v), sign = v < 0 ? MINUS : '';
  const [k, u] = a >= 1 ? [1, 's'] : a >= 1e-3 ? [1e3, 'ms'] : a >= 1e-6 ? [1e6, 'µs'] : [1e9, 'ns'];
  const n = a * k;
  const body = n >= 100 ? n.toFixed(0) : n >= 10 ? trim(n.toFixed(1)) : trim(n.toFixed(2));
  return `${sign}${body} ${u}`;
}

/** Evenly spaced "nice" ticks (1, 2 or 5 × 10ⁿ) covering [min, max]; the domain is first..last. */
export function linearTicks(min: number, max: number, target = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [];
  if (min === max) {
    const pad = min === 0 ? 1e-9 : Math.abs(min) * 0.5;
    min -= pad; max += pad;
  }
  if (min > max) [min, max] = [max, min];
  const raw = (max - min) / Math.max(1, target);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
  const start = Math.floor(min / step + 1e-9) * step;
  const end = Math.ceil(max / step - 1e-9) * step;
  const out: number[] = [];
  for (let i = 0; start + i * step <= end + step * 1e-9 && i < 50; i++) {
    const t = start + i * step;
    out.push(Math.abs(t) < step * 1e-9 ? 0 : Number(t.toPrecision(12)));
  }
  return out;
}

/**
 * The linear zone of a symmetric-log axis: the decade at or below the 10th percentile of |v|
 * (non-zero values), within 1 ps … 1 s. Small enough that most of the data is on the log part,
 * large enough that noise around zero doesn't spread over many empty decades.
 */
export function symThreshold(values: number[]): number {
  const a = values.map(Math.abs).filter(x => x > 0 && Number.isFinite(x)).sort((p, q) => p - q);
  if (!a.length) return 1e-9;
  const p10 = a[Math.floor((a.length - 1) * 0.1)];
  return Math.min(1, Math.max(1e-12, 10 ** Math.floor(Math.log10(p10))));
}

/** Symmetric-log domain and ticks (in symlog units) covering the values; zero always included. */
export function symAxis(values: number[], lin: number): { domain: [number, number]; ticks: number[] } {
  let lo = 0, hi = 0;
  for (const v of values) {
    if (!Number.isFinite(v)) continue;
    const y = symlog(v, lin);
    lo = Math.min(lo, y); hi = Math.max(hi, y);
  }
  const top = Math.max(1, Math.ceil(hi - 1e-9)), bottom = Math.min(lo < 0 ? -1 : 0, Math.floor(lo + 1e-9));
  const ticks: number[] = [];
  const span = top - bottom;
  const every = span > 12 ? 2 : 1;            // thin to at most about 7 labels
  for (let k = bottom; k <= top; k++) if (k === 0 || k % every === 0) ticks.push(k);
  return { domain: [bottom, top], ticks };
}

/** Label for a symmetric-log tick (symlog units) as a time. */
export function symTimeLabel(y: number, lin: number): string {
  return fmtTime(Number(symexp(y, lin).toPrecision(6)));
}

/** Decade ticks covering positive values (log axis). Values ≤ 0 can't be drawn on it and are ignored. */
export function logTicks(values: number[]): number[] {
  const p = values.filter(v => v > 0 && Number.isFinite(v));
  if (!p.length) return [];
  const lo = Math.floor(Math.log10(Math.min(...p)) + 1e-9);
  const hi = Math.ceil(Math.log10(Math.max(...p)) - 1e-9);
  return Array.from({ length: Math.max(hi, lo + 1) - lo + 1 }, (_, i) => 10 ** (lo + i));
}

/** Values drawn on a log axis: what is ≤ 0 has no place on it (counted, so the chart can say so). */
export function positiveOnly<T>(rows: T[], value: (r: T) => number): { rows: T[]; dropped: number } {
  const kept = rows.filter(r => value(r) > 0);
  return { rows: kept, dropped: rows.length - kept.length };
}

export { symexp, symlog };
