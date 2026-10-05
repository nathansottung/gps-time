// Pure helpers for Timing → References (/api/references): labels, units and
// chart series. Tested in references.test.ts.

import type { ReferencePoint, ReferenceVerdict, ReferenceServer } from '../api/types';

export type Variant = 'good' | 'warn' | 'error' | 'muted' | 'info';

/** A disagreement is a warning, never an error: it doesn't say which clock is wrong. */
export function verdictVariant(code: ReferenceVerdict['code'] | undefined): Variant {
  return code === 'AGREE' ? 'good' : code === 'DISAGREE' ? 'warn' : code === 'ONE_REFERENCE' ? 'info' : 'muted';
}

export function assessmentVariant(a: ReferenceServer['assessment']): Variant {
  return a === 'agrees' ? 'good' : a === 'disagrees' ? 'warn' : a === 'inconclusive' ? 'info' : 'muted';
}

/** Signed time difference with a sensible unit: "+2.65 ms", "−180 ms", "+895 µs". null = UNKNOWN. */
export function fmtSigned(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return null;
  const sign = seconds < 0 ? '−' : '+';
  return sign + fmtSpan(Math.abs(seconds));
}

/** Unsigned duration with a sensible unit: "31 ms", "15.0 ms", "400 µs". */
export function fmtSpan(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return null;
  const a = Math.abs(seconds);
  if (a >= 1) return `${a.toPrecision(3)} s`;
  if (a >= 1e-3) return `${(a * 1e3).toPrecision(3)} ms`;
  if (a >= 1e-6) return `${(a * 1e6).toPrecision(3)} µs`;
  return `${(a * 1e9).toPrecision(3)} ns`;
}

export interface Series { unit: string; data: { ts: number; t: string; dt: number }[] }

function series(points: ReferencePoint[], pick: (p: ReferencePoint) => number | null): Series {
  const pts = points.filter(p => pick(p) !== null);
  const maxAbs = pts.reduce((a, p) => Math.max(a, Math.abs(pick(p)!)), 0);
  const [k, unit] = maxAbs < 1e-3 ? [1e6, 'µs'] : maxAbs < 1 ? [1e3, 'ms'] : [1, 's'];
  return { unit, data: pts.map(p => ({ ts: p.t * 1000, t: new Date(p.t * 1000).toISOString(), dt: pick(p)! * k })) };
}

/** Offset and delay histories of one server; a point without a delay is left out of the delay series. */
export function historySeries(points: ReferencePoint[] | undefined): { offset: Series; delay: Series } {
  const pts = points ?? [];
  return { offset: series(pts, p => p.offset_s), delay: series(pts, p => p.delay_s) };
}

/** "3 answering of 3" style summary for the header line. */
export function countsLine(v: ReferenceVerdict | undefined): string | null {
  if (!v || v.usable === undefined || v.configured === undefined) return null;
  return `${v.usable} answering of ${v.configured} independent`;
}
