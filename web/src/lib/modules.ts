// Administration → Experimental modules (GET /api/modules, POST /api/setting).
// The rules are the station's (gps_time_pi/modkit/settings.py): off by default; with the
// switch off nothing runs; turning the switch on or off leaves every module off, so each is
// turned on by itself. The demo adapter applies the same rules through applySetting().
import type { ModuleLatest, ModuleRow, ModulesState, Provenance, SettingResult } from '../api/types';
import { fmtDuration, fmtOffset } from './format';
import { fmtSci } from './units';

export type Variant = 'good' | 'warn' | 'error' | 'muted';

/** The row's status: what the station reports, never inferred. */
export function rowStatus(row: ModuleRow, s: ModulesState): { label: string; variant: Variant } {
  if (!row.installed) return { label: 'NOT INSTALLED', variant: 'warn' };
  if (!row.valid) return { label: 'INVALID MANIFEST', variant: 'error' };
  if (!row.enabled) return { label: 'OFF', variant: 'muted' };
  if (!s.experimental) return { label: 'OFF (switch off)', variant: 'muted' };
  if (row.host_runs === false) return { label: 'ENABLED · NOT RUN BY THE HOST (runs from its command line)', variant: 'muted' };
  if (!s.supervisor.reporting || row.state === null) return { label: 'ENABLED · state UNKNOWN', variant: 'muted' };
  const st = row.state.toUpperCase();
  if (row.state === 'running' || row.state === 'finished') return { label: st, variant: 'good' };
  if (['failed', 'killed', 'refused'].includes(row.state)) return { label: st, variant: 'error' };
  return { label: st, variant: 'warn' };
}

/** Whether this row's toggle may be used; a module can always be turned off. */
export function canToggle(row: ModuleRow, s: ModulesState, canWrite: boolean): boolean {
  if (!canWrite) return false;
  if (row.enabled) return true;
  return s.experimental && row.installed && row.valid;
}

export function permissionText(row: ModuleRow): string {
  const p = row.permissions;
  if (!p) return 'UNKNOWN';
  const parts = [p.network ? 'network' : 'no network',
                 p.devices.length ? `devices ${p.devices.join(', ')}` : 'no devices',
                 `storage ${p.storage}`];
  return parts.join(' · ');
}

export function switchConfirm(on: boolean): string {
  return on
    ? 'Turn on experimental modules? No module starts by itself: each stays off until you turn it on below. Modules are research or experimental code, not part of the timing core.'
    : 'Turn off experimental modules? Every module stops, and each is off again if the switch is turned back on.';
}

export type Outcome = { variant: Variant; text: string };

/** The line after a change: the station's answer, or why it was refused. */
export function settingOutcome(what: string, r: SettingResult | null, err?: { message: string; status: number | null }): Outcome {
  if (err) {
    if (err.status === null) return { variant: 'warn', text: `${what}: no answer from the station (${err.message}). It may still have changed; reload to see.` };
    return { variant: 'error', text: `${what}: refused. ${err.message}` };
  }
  if (!r || !r.ok) return { variant: 'error', text: `${what}: the station rejected the change.` };
  return { variant: 'good', text: `${what}: saved. gps-time-modules picks it up within about 10 s if it is running.` };
}

/** The station's rules, for the demo adapter. Throws Error(message) on a refusal. */
export function applySetting(s: { experimental: boolean; enabled: string[] }, valid: ReadonlySet<string>,
  body: { modules_experimental: boolean } | { module: string; enabled: boolean }): SettingResult {
  if ('modules_experimental' in body) {
    s.experimental = body.modules_experimental;
    s.enabled = [];
    return { ok: true, modules_experimental: s.experimental, modules_enabled: [] };
  }
  if (body.enabled) {
    if (!s.experimental) throw new Error('experimental modules are off; turn them on first');
    if (!valid.has(body.module)) throw new Error(`no valid module named ${body.module} is installed`);
    if (!s.enabled.includes(body.module)) s.enabled = [...s.enabled, body.module];
  } else {
    s.enabled = s.enabled.filter(n => n !== body.module);
  }
  return { ok: true, module: body.module, enabled: body.enabled, modules_enabled: s.enabled };
}

// ─── A module's latest output (ModuleRow.latest) ───────────────────────────

export interface OutputLine { name: string; value: string | null; unit: string; provenance: Provenance; note?: string }

/** One value as the page shows it; null stays null (MetricRow shows UNKNOWN). Seconds go to
 *  ns/µs/ms; very small or large numbers in ×10ⁿ; everything else as the module gave it. */
export function fmtModuleValue(v: string | number | boolean | null, unit: string | null): { value: string | null; unit: string } {
  if (v === null || v === undefined) return { value: null, unit: unit ?? '' };
  if (typeof v === 'boolean') return { value: v ? 'yes' : 'no', unit: '' };
  if (typeof v === 'string') return { value: v, unit: unit ?? '' };
  if (!Number.isFinite(v)) return { value: null, unit: unit ?? '' };
  if (unit === 's' && v !== 0 && Math.abs(v) < 1) {
    const o = fmtOffset(v, 1);
    return o ? { value: o.value.replace('+', ''), unit: o.unit } : { value: null, unit: 's' };
  }
  const a = Math.abs(v);
  if (Number.isInteger(v) && a < 1e12) return { value: String(v).replace('-', '−'), unit: unit ?? '' };
  if (a !== 0 && (a < 1e-3 || a >= 1e7)) return { value: fmtSci(v, 4), unit: unit ?? '' };
  return { value: String(Number(v.toPrecision(6))).replace('-', '−'), unit: unit ?? '' };
}

export function outputLines(lt: ModuleLatest): OutputLine[] {
  return Object.entries(lt.values).map(([name, v]) => {
    const f = fmtModuleValue(v.value, v.unit);
    return { name, value: f.value, unit: f.unit, provenance: v.provenance, ...(v.note ? { note: v.note } : {}) };
  });
}

/** "observation 12s ago · 20 kept in RAM", and what was left out. */
export function outputHeading(lt: ModuleLatest): string {
  const age = lt.age_s === null ? 'time UNKNOWN' : `${fmtDuration(lt.age_s)} ago`;
  const left = lt.left_out ? ` · ${lt.left_out} value${lt.left_out === 1 ? '' : 's'} not shown (unlabeled, not a single value, a position, or over the limit)` : '';
  return `Latest ${lt.kind} ${age} · ${lt.items_kept} kept in RAM${left}`;
}
