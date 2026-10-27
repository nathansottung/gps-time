// Pure helpers for Timing → Oscillator (/api/oscillator). Tested in oscillator.test.ts.

import type {
  HoldoverProjection, OscillatorBin, OscillatorFit, OscillatorHoldover, OscillatorProfile, OscillatorProfileExport,
  ProfileBinding, ProfileImportResult,
} from '../api/types';
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

// ─── Holdover projections (/api/oscillator → holdover; modeled, GPS-008) ─────

export const HOLDOVER_LABEL: Record<HoldoverProjection['name'], string> = {
  free_running: 'Free-running (untrained)',
  trained_skew: 'Trained (skew only)',
  profile: 'Profile (temperature, aging)',
};

/** Seconds for |error| = rate·τ + aging·τ²/2 to reach each threshold (mirrors oscprofile.holdover). */
export function holdoverTimes(thresholdsS: number[], ratePpm: number, agingPpmPerDay = 0): (number | null)[] {
  const r = Math.abs(ratePpm) * 1e-6, a = Math.abs(agingPpmPerDay) * 1e-6 / 86400;
  return thresholdsS.map(e => a > 0 ? (-r + Math.sqrt(r * r + 2 * a * e)) / a : r > 0 ? e / r : null);
}

const sig2 = (v: number) => v >= 10 ? v.toFixed(0) : v.toFixed(1);

/** A holdover duration: "0.47 s", "56 s", "25 min", "15 h", "5.4 d", "3.2 yr"; null → "not reached". */
export function fmtHoldTime(s: number | null | undefined): string {
  if (s === null || s === undefined || !Number.isFinite(s)) return 'not reached';
  if (s < 1) return `${s.toPrecision(2)} s`;
  if (s < 120) return `${sig2(s)} s`;
  if (s < 7200) return `${sig2(s / 60)} min`;
  if (s < 2 * 86400) return `${sig2(s / 3600)} h`;
  if (s < 2 * 365.25 * 86400) return `${sig2(s / 86400)} d`;
  return `${sig2(s / (365.25 * 86400))} yr`;
}

/** "±1 µs" … "±1 s" for a threshold in seconds. */
export function fmtThreshold(s: number): string {
  const units: [number, string][] = [[1, 's'], [1e-3, 'ms'], [1e-6, 'µs'], [1e-9, 'ns']];
  const [div, u] = units.find(([d]) => s >= d * 0.999) ?? units[units.length - 1];
  return `±${+(s / div).toPrecision(3)} ${u}`;
}

export interface HoldoverRow { threshold: string; cells: { name: HoldoverProjection['name']; text: string }[] }

/** One row per threshold, one cell per projection; an unavailable projection shows "—". */
export function holdoverRows(h: OscillatorHoldover | undefined): HoldoverRow[] {
  if (!h) return [];
  return h.thresholds_s.map((t, i) => ({
    threshold: fmtThreshold(t),
    cells: h.projections.map(p => ({ name: p.name, text: p.available ? fmtHoldTime(p.times_s[i]) : '—' })),
  }));
}

// ─── Profile export / import (board binding by serial hash) ──────────────────

export const BINDING_LABEL: Record<ProfileBinding, string> = {
  match: 'same board: in use',
  mismatch: 'another board: reference only',
  unverifiable: "board can't be confirmed: reference only",
};

/** The download name for an export file. */
export function exportFilename(doc: { exported_utc?: string | null }): string {
  const day = (doc.exported_utc ?? '').slice(0, 10);
  return `oscillator-profile${day ? '-' + day : ''}.json`;
}

/** The line shown after an import. */
export function importOutcome(r: ProfileImportResult): { ok: boolean; text: string } {
  if (!r.ok) return { ok: false, text: `Not imported: ${r.error}.` };
  return { ok: true, text: `Imported (${r.bins.toLocaleString()} bins), ${r.detail}.` };
}

const HASH = /^[0-9a-f]{16}$/;

/** The station's binding rule (oscillator.Log.binding), for the demo adapter. */
export function bindingFor(fileHash: unknown, stationHash: string | null): ProfileBinding {
  if (typeof fileHash !== 'string' || !HASH.test(fileHash) || !stationHash || !HASH.test(stationHash)) return 'unverifiable';
  return fileHash === stationHash ? 'match' : 'mismatch';
}

/** What the demo adapter answers to an import: the station's checks, nothing saved. */
export function demoImport(doc: unknown, stationHash: string | null): ProfileImportResult {
  const d = doc as Partial<OscillatorProfileExport> | null;
  if (!d || typeof d !== 'object' || d.format !== 'gps-time-oscillator-profile/1')
    return { ok: false, error: 'not an oscillator profile file (expected format gps-time-oscillator-profile/1)' };
  const rows = d.fit_bins?.rows;
  if (!Array.isArray(rows) || rows.some(r => !Array.isArray(r) || r.length !== 3 || r.some(v => typeof v !== 'number' || !Number.isFinite(v))))
    return { ok: false, error: 'each bin must be [epoch seconds, °C, ppm]' };
  const binding = bindingFor(d.board?.serial_sha256, stationHash);
  const used = binding === 'match';
  const what = used ? `same board: ${rows.length} bins merged into this board's profile`
    : binding === 'mismatch' ? "a different board: kept for reference only; this board's profile carries on from its own log"
    : "the board can't be confirmed (no serial hash on the file or the station): kept for reference only";
  return { ok: true, binding, bins: rows.length, used, simulated: true, detail: `demo mode, nothing was saved. On a station: ${what}` };
}

/** Date ticks for the time charts: local midnights inside [lo, hi] (ms), one per day, or every
 *  n-th day so there are at most `max`; each date appears once (a label per day, never repeated). */
export function dayTicks(lo: number, hi: number, max = 7): number[] {
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return [];
  const d = new Date(lo);
  d.setHours(0, 0, 0, 0);
  if (d.getTime() < lo) d.setDate(d.getDate() + 1);
  const all: number[] = [];
  for (; d.getTime() <= hi; d.setDate(d.getDate() + 1)) all.push(d.getTime());
  const step = Math.max(1, Math.ceil(all.length / max));
  return all.filter((_, i) => i % step === 0);
}
