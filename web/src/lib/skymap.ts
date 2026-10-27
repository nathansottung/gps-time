// GNSS & Site → Sky Obstruction (GET /api/sky-obstruction; gps_time_pi/skymap.py). Every class
// is the station's (inferred); nothing here classifies. Polar layout from lib/shadow.ts
// (zenith at the centre, north up, east to the right, as in the sky plot).
import type { SkyCell, SkyCellClass, SkyLossClass, SkyObstruction, SkySectorState } from '../api/types';
import { segmentPath } from './shadow';

export type Variant = 'good' | 'warn' | 'error' | 'muted' | 'info';
export type ShadeBy = 'class' | 'cn0';

export const CLASS_LABEL: Record<SkyCellClass, string> = {
  clear: 'Clear', attenuated: 'Attenuated', blocked: 'Blocked', unknown: 'Not enough data',
};
const CLASS_FILL: Record<SkyCellClass, string | null> = {
  clear: 'var(--good-text)', attenuated: 'var(--warn-text)', blocked: 'var(--err-text)', unknown: 'var(--t4)',
};
const CLASS_OPACITY: Record<SkyCellClass, number> = { clear: 0.22, attenuated: 0.5, blocked: 0.6, unknown: 0.1 };

/** C/N₀ shading runs from CN0_LO (faint) to CN0_HI (strong), in dB-Hz. */
export const CN0_LO = 20, CN0_HI = 50;

export function cellShade(c: SkyCell, by: ShadeBy): { fill: string; opacity: number } {
  if (by === 'cn0') {
    if (c.cn0_mean === null) return { fill: 'var(--t4)', opacity: 0.08 };
    const f = Math.min(1, Math.max(0, (c.cn0_mean - CN0_LO) / (CN0_HI - CN0_LO)));
    return { fill: 'var(--info-text)', opacity: Math.round((0.08 + 0.62 * f) * 100) / 100 };
  }
  return { fill: CLASS_FILL[c.class] ?? 'var(--t4)', opacity: CLASS_OPACITY[c.class] };
}

/** One SVG path per cell (an annular sector of az_step × el_step). */
export function cellPath(c: SkyCell, azStep: number, elStep: number, cx: number, cy: number, r: number): string {
  return segmentPath({ code: 'U', az0: c.az0, az1: c.az0 + azStep, alt0: c.el0, alt1: Math.min(90, c.el0 + elStep) }, cx, cy, r);
}

export function cellTitle(c: SkyCell, azStep: number, elStep: number): string {
  const parts = [`${c.az0}–${c.az0 + azStep}° az, ${c.el0}–${c.el0 + elStep}° el: ${CLASS_LABEL[c.class]}`,
    `${c.samples} satellite-minutes`];
  if (c.cn0_mean !== null) parts.push(`mean C/N₀ ${c.cn0_mean} dB-Hz` +
    (c.delta_db !== null ? ` (${c.delta_db > 0 ? '+' : ''}${c.delta_db} dB against its elevation band)` : ''));
  if (c.tracked_pct !== null) parts.push(`tracked ${c.tracked_pct} %`);
  return parts.join(' · ');
}

export function sectorVariant(s: SkySectorState): Variant {
  return s === 'clear' ? 'good' : s === 'attenuated' ? 'warn' : s === 'obstructed' ? 'error' : 'muted';
}

export const LOSS_LABEL: Record<SkyLossClass, string> = {
  EXPECTED: 'EXPECTED', 'NOT EXPLAINED': 'NOT EXPLAINED', UNKNOWN: 'UNKNOWN', SET: 'SET',
};
/** An expected loss is the environment as learned: never a warning. A loss the map doesn't explain is. */
export function lossVariant(c: SkyLossClass): Variant {
  return c === 'EXPECTED' || c === 'SET' ? 'muted' : c === 'NOT EXPLAINED' ? 'warn' : 'muted';
}

export function summaryLine(m: SkyObstruction): { text: string; variant: Variant } {
  const s = m.summary;
  if (!s.cells_with_data) return { text: 'Learning: no satellites recorded yet', variant: 'muted' };
  const days = `${s.days} day${s.days === 1 ? '' : 's'}`;
  if (s.state === 'learning') {
    return { text: `Learning: ${days} so far (${m.thresholds.learned_days} needed), ${s.cells_classified} of ${s.cells_total} cells classified`, variant: 'muted' };
  }
  return { text: `Learned over ${days}: ${s.clear_pct ?? '—'} % of classified cells clear`, variant: 'info' };
}

/** The rows of the loss table, newest first, as the station sent them. */
export function lossRows(m: SkyObstruction): { when: string; sat: string; dir: string; cls: SkyLossClass; note: string }[] {
  return m.losses.recent.map(l => ({
    when: l.utc.slice(11, 19) + ' UTC',
    sat: `${l.gnss} ${l.sat ?? '?'}`,
    dir: `${Math.round(l.az)}° / ${Math.round(l.el)}°`,
    cls: l.class, note: l.note,
  }));
}

export function lossTotals(m: SkyObstruction): string {
  const c = m.losses.counts;
  const all = c.EXPECTED + c['NOT EXPLAINED'] + c.UNKNOWN + c.SET;
  return `${all} since ${m.losses.since}: ${c.EXPECTED} expected, ${c['NOT EXPLAINED']} not explained, ${c.SET} set, ${c.UNKNOWN} unknown`;
}
