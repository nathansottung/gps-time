// Administration → Experimental modules (GET /api/modules, POST /api/setting).
// The rules are the station's (gps_time_pi/modkit/settings.py): off by default; with the
// switch off nothing runs; turning the switch on or off leaves every module off, so each is
// turned on by itself. The demo adapter applies the same rules through applySetting().
import type { ModuleConfigField, ModuleLatest, ModuleRow, ModulesState, Provenance, ReadinessCheck, SettingResult } from '../api/types';
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

// ─── Readiness (ModuleRow.readiness: what an SDR module needs that the station observes) ───

export interface ReadinessLine { check: string; mark: 'OK' | 'MISSING' | 'UNKNOWN'; variant: Variant; detail: string }

/** One line per check; ok null is UNKNOWN (not observable), never assumed fine. */
export function readinessLines(checks: ReadinessCheck[] | null | undefined): ReadinessLine[] {
  return (checks ?? []).map(c => ({
    check: c.check, detail: c.detail,
    mark: c.ok === true ? 'OK' : c.ok === false ? 'MISSING' : 'UNKNOWN',
    variant: c.ok === true ? 'good' : c.ok === false ? 'warn' : 'muted',
  }));
}

// ─── A module's settings (ModuleRow.config, POST /api/setting {module, config}) ───

/** What the settings box starts with: the owner's settings, pretty-printed; "{}" for none. */
export function configText(config: Record<string, unknown> | undefined): string {
  return config && Object.keys(config).length ? JSON.stringify(config, null, 2) : '{}';
}

/** The manifest's settings as rows: name, type and unit, default, description. */
export function schemaRows(schema: Record<string, ModuleConfigField> | undefined):
  { name: string; type: string; dflt: string; description: string }[] {
  return Object.entries(schema ?? {}).map(([name, f]) => ({
    name,
    type: [f.type ?? 'UNKNOWN', f.unit].filter(Boolean).join(', '),
    dflt: f.default === undefined ? 'none: must be set' : JSON.stringify(f.default),
    description: f.description ?? '',
  }));
}

// The station's rules (gps_time_pi/modkit/settings.py check_config), checked here first so a typo
// is caught before it is sent; the station checks again.
const POSITION_KEYS = new Set(['lat', 'lon', 'latitude', 'longitude', 'alt', 'alt_m', 'alt_msl', 'alt_hae', 'height_m',
  'position', 'site', 'location', 'x_m', 'y_m', 'z_m']);
const MAX_CONFIG_BYTES = 8192;

function positionKey(v: unknown, path = ''): string | null {
  if (Array.isArray(v)) {
    for (let i = 0; i < v.length; i++) { const h = positionKey(v[i], `${path}${i}.`); if (h) return h; }
  } else if (v && typeof v === 'object') {
    for (const [k, x] of Object.entries(v)) {
      if (POSITION_KEYS.has(k.toLowerCase())) return `${path}${k}`;
      const h = positionKey(x, `${path}${k}.`); if (h) return h;
    }
  }
  return null;
}

/** Why the station would refuse these settings; null when it wouldn't. */
export function configProblem(value: unknown, schema: Record<string, ModuleConfigField> | undefined): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return 'settings must be a JSON object, e.g. {"interval_s": 10}';
  if (JSON.stringify(value).length > MAX_CONFIG_BYTES) return `settings are larger than ${MAX_CONFIG_BYTES} bytes`;
  const known = schema ?? {};
  const unknown = Object.keys(value).filter(k => !(k in known)).sort();
  if (unknown.length) return `no setting ${unknown.join(', ')} (the manifest declares: ${Object.keys(known).join(', ') || 'none'})`;
  const pos = positionKey(value);
  if (pos) return `${pos}: positions are not set here; a module gets the station's site, privacy-filtered, from the station`;
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    const t = known[k].type;
    if (v === null || t === undefined) continue;
    const ok = t === 'float' ? typeof v === 'number'
      : t === 'int' ? typeof v === 'number' && Number.isInteger(v)
      : t === 'string' || t === 'path' ? typeof v === 'string' && v.length <= 300
      : t === 'table' ? typeof v === 'object' && !Array.isArray(v)
      : t === 'bool' ? typeof v === 'boolean' : true;
    if (!ok) return `${k} must be a ${t}${(t === 'string' || t === 'path') ? ' of at most 300 characters' : ''}`;
  }
  return null;
}

/** The settings box's text as the value to send, or the reason it can't be sent. */
export function parseConfig(text: string, schema: Record<string, ModuleConfigField> | undefined):
  { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  let value: unknown;
  try { value = JSON.parse(text.trim() || '{}'); } catch (e) { return { ok: false, error: `not valid JSON: ${(e as Error).message}` }; }
  const problem = configProblem(value, schema);
  return problem ? { ok: false, error: problem } : { ok: true, value: value as Record<string, unknown> };
}
