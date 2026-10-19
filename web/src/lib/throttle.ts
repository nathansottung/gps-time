// Administration → Power: the Pi's get_throttled flags, decoded by the station (system.THROTTLE_BITS),
// as a table of conditions, now and since boot (parity 21, owner decision 2026-10-19).
import type { SystemDiagnostics } from '../api/types';

export interface ThrottleRow { condition: string; now: boolean | null; sinceBoot: boolean | null }

/** "Under-voltage now" / "Under-voltage occurred since boot" → one row per condition, in the station's order. */
export function throttleRows(t: SystemDiagnostics['throttled'] | null | undefined): ThrottleRow[] | null {
  if (!t) return null;
  const rows = new Map<string, ThrottleRow>();
  for (const f of t.flags) {
    const condition = f.label.replace(/\s+(now|occurred since boot|since boot)$/i, '');
    const row = rows.get(condition) ?? { condition, now: null, sinceBoot: null };
    if (f.now) row.now = f.active; else row.sinceBoot = f.active;
    rows.set(condition, row);
  }
  return [...rows.values()];
}

/** Under-voltage first: an unsteady supply is the condition most worth fixing on a timing station. */
export function underVoltage(rows: ThrottleRow[] | null): { now: boolean; ever: boolean } | null {
  const r = rows?.find(x => /under-voltage/i.test(x.condition));
  return r ? { now: !!r.now, ever: !!r.now || !!r.sinceBoot } : null;
}
