// Administration → Experimental modules (GET /api/modules, POST /api/setting).
// The rules are the station's (gps_time_pi/modkit/settings.py): off by default; with the
// switch off nothing runs; turning the switch on or off leaves every module off, so each is
// turned on by itself. The demo adapter applies the same rules through applySetting().
import type { ModuleRow, ModulesState, SettingResult } from '../api/types';

export type Variant = 'good' | 'warn' | 'error' | 'muted';

/** The row's status: what the station reports, never inferred. */
export function rowStatus(row: ModuleRow, s: ModulesState): { label: string; variant: Variant } {
  if (!row.installed) return { label: 'NOT INSTALLED', variant: 'warn' };
  if (!row.valid) return { label: 'INVALID MANIFEST', variant: 'error' };
  if (!row.enabled) return { label: 'OFF', variant: 'muted' };
  if (!s.experimental) return { label: 'OFF (switch off)', variant: 'muted' };
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
