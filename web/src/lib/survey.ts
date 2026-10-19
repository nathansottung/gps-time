// Survey reset on the Administration page (POST /api/setting {"reset_site": true}). It discards
// the stored position survey, which may hold weeks of averaged fixes, so the page asks the
// operator to type a word first rather than accepting a single click.
import type { SettingResult, Survey, SurveyStats } from '../api/types';

export const RESET_WORD = 'RESET';

/** The typed confirmation: the word itself, any case, surrounding spaces ignored. */
export function resetConfirmed(input: string): boolean {
  return input.trim().toUpperCase() === RESET_WORD;
}

/** What would be lost, from the station's own counts. null stats = UNKNOWN, never "nothing". */
export function surveyLoss(s: SurveyStats | null | undefined): string {
  if (!s) return 'The station has not reported its survey; what would be discarded is UNKNOWN.';
  if (!s.n) return 'The survey is empty: there is nothing to discard.';
  const se = s.se_horiz_m == null ? '' : `, horizontal standard error of the mean ±${s.se_horiz_m.toFixed(2)} m`;
  return `Discards ${s.n.toLocaleString('en-US')} accepted fixes${se}. The survey starts again from the next fresh fix.`;
}

export type ResetOutcome = { variant: 'good' | 'warn' | 'error'; text: string };

export function resetOutcome(r: SettingResult | null, err?: { message: string; status: number | null }): ResetOutcome {
  if (err) {
    if (err.status === null) return { variant: 'warn', text: `No answer from the station (${err.message}). The survey may or may not have been reset; check the accepted-fix count.` };
    return { variant: 'error', text: `Refused: ${err.message}` };
  }
  if (r && r.ok && 'reset_site' in r) return { variant: 'good', text: 'Survey reset. The accepted-fix count starts again from 0.' };
  return { variant: 'error', text: 'The station did not reset the survey.' };
}

// ─── Survey convergence and session scatter (GNSS & Site → Survey; parity 14, 15) ──────────


export interface ConvergencePoint { t: number; horiz: number | null; vert: number | null }

/** /api/survey history → chart rows. A log axis can't show 0 or negatives, so those become gaps, not 0. */
export function convergenceSeries(history: Survey['history'] | null | undefined): ConvergencePoint[] {
  const pos = (v: number | null) => (v != null && Number.isFinite(v) && v > 0 ? v : null);
  return (history ?? []).map(([t, , h, v]) => ({ t: t * 1000, horiz: pos(h), vert: pos(v) }))
    .filter(p => p.horiz !== null || p.vert !== null);
}

/** Log-axis domain with a little room, never below 1 cm (the legacy chart's floor). */
export function logDomain(points: ConvergencePoint[]): [number, number] | null {
  const vals = points.flatMap(p => [p.horiz, p.vert]).filter((v): v is number => v !== null);
  if (!vals.length) return null;
  return [Math.max(Math.min(...vals) / 1.5, 0.01), Math.max(...vals) * 1.5];
}

export interface Bullseye {
  scale: number;                                          // px per metre
  sd: number;                                             // per-fix scatter used for the rings (m)
  rings: number[];                                        // radii of the 1, 2, 3 × scatter rings (px)
  seRing: number | null;                                  // the mean's standard error (px), min 3 px
  fixes: { x: number; y: number; opacity: number }[];     // oldest faint, newest strong
}

/** Session fixes around the mean, north up, east right; scaled so 3 × scatter fills the plot. */
export function bullseye(fixes: [number, number][], stats: { sd_lat_m?: number; sd_lon_m?: number; se_horiz_m?: number },
                         size: number, pad = 16): Bullseye {
  const c = size / 2;
  const sd = Math.max(stats.sd_lat_m ?? 0, stats.sd_lon_m ?? 0, 0.5);
  const scale = (c - pad) / (3 * sd);
  const n = fixes.length || 1;
  return {
    scale, sd,
    rings: [1, 2, 3].map(k => k * sd * scale),
    seRing: stats.se_horiz_m ? Math.max(stats.se_horiz_m * scale, 3) : null,
    fixes: fixes.map(([north, east], i) => ({ x: c + east * scale, y: c - north * scale, opacity: 0.25 + 0.6 * (i / n) })),
  };
}

/** Rejected-fix counts, largest first. */
export function rejectedRows(rejected: Record<string, number> | null | undefined): [string, number][] {
  return Object.entries(rejected ?? {}).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]);
}

/** Metres for these small numbers: "0.18 m", "3.2 m", "12 m", "4 cm". */
export function fmtMetres(m: number | null | undefined): string | null {
  if (m == null || !Number.isFinite(m)) return null;
  const a = Math.abs(m);
  return a < 0.1 ? `${(m * 100).toFixed(0)} cm` : a < 1 ? `${m.toFixed(2)} m` : a < 10 ? `${m.toFixed(1)} m` : `${m.toFixed(0)} m`;
}
