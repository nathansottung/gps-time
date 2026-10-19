// Timing → Overview, offset history (legacy /history chart; parity 13). Lays out chrony's own
// tracking.log columns (/api/history, named since review GPS-003): the offset, the band of
// ± chrony's offset SD where it reported one, and ± chrony's max-error bound. Nothing is
// synthesized. The axis is symmetric-log: linear within ±1 µs, logarithmic beyond.
import type { HistoryPoint } from '../api/types';

export const SYMLIN = 1e-6;

export function symlog(v: number, lin = SYMLIN): number {
  const a = Math.abs(v), s = Math.sign(v) || 1;
  return a <= lin ? v / lin : s * (1 + Math.log10(a / lin));
}

export function symexp(y: number, lin = SYMLIN): number {
  const a = Math.abs(y), s = Math.sign(y) || 1;
  return a <= 1 ? y * lin : s * lin * 10 ** (a - 1);
}

/** "0", "500 ns", "1 µs", "−10 µs", "1 ms", "1 s" (U+2212 minus). */
export function fmtSeconds(v: number): string {
  if (v === 0) return '0';
  const a = Math.abs(v), sign = v < 0 ? '−' : '';
  const [k, u] = a >= 1 ? [1, 's'] : a >= 1e-3 ? [1e3, 'ms'] : a >= 1e-6 ? [1e6, 'µs'] : [1e9, 'ns'];
  const n = a * k;
  return `${sign}${Number.isInteger(Math.round(n * 10) / 10) ? Math.round(n) : n.toFixed(1)} ${u}`;
}

export interface OffsetRow {
  ts: number;                        // ms
  y: number;                         // symlog(offset)
  band: [number, number] | null;     // symlog(offset ∓ sd)
  maxErr: [number, number] | null;   // symlog(∓ max error)
  offset: number; sd: number | null; maxError: number | null;
}

const num = (v: number | null | undefined): number | null => (v != null && Number.isFinite(v) ? v : null);

export function offsetRows(points: HistoryPoint[] | undefined, rangeS: number, nowMs = Date.now()): OffsetRow[] {
  const from = nowMs / 1000 - rangeS;
  return (points ?? []).filter(p => p.t >= from && Number.isFinite(p.offset_s)).map(p => {
    const sd = num(p.offset_sd_s), me = num(p.max_error_s);
    return {
      ts: p.t * 1000, y: symlog(p.offset_s), offset: p.offset_s, sd, maxError: me,
      band: sd === null || sd < 0 ? null : [symlog(p.offset_s - sd), symlog(p.offset_s + sd)],
      maxErr: me === null || me < 0 ? null : [symlog(-me), symlog(me)],
    };
  });
}

/** Symmetric y domain covering what is drawn (the bound only when shown), at least ±1 µs. */
export function symDomain(rows: OffsetRow[], withMaxErr: boolean): [number, number] {
  let m = 1.2;
  for (const r of rows) {
    m = Math.max(m, Math.abs(r.y));
    if (r.band) m = Math.max(m, Math.abs(r.band[0]), Math.abs(r.band[1]));
    if (withMaxErr && r.maxErr) m = Math.max(m, Math.abs(r.maxErr[1]));
  }
  const top = Math.ceil(m * 10) / 10;
  return [-top, top];
}

/** Ticks at 0, ±1 µs and each decade beyond, inside the domain (in symlog units). */
export function symTicks(domain: [number, number]): number[] {
  const out = [0];
  for (let k = 1; k <= domain[1]; k++) out.push(k, -k);
  return out.sort((a, b) => a - b);
}
