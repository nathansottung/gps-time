// Radio → Web SDR (GET /api/websdr; gps_time_pi/websdr.py). OpenWebRX+ behind the station's
// LAN gate, with an optional login. Started and stopped with the admin actions websdr_start /
// websdr_stop, which need no token (anyone on the LAN); websdr_signout_all (token) signs out
// every remembered browser.
// Values the station couldn't read stay null (UNKNOWN).
import type { AdminAction, AdminResult, Measured, WebSdrStatus, WebSdrSummary } from '../api/types';
import { fmtDuration } from './format';

export type Variant = 'good' | 'warn' | 'error' | 'muted';

/** The web SDR's address on the LAN: the station's host name, the gate's port, plain HTTP. */
export function websdrUrl(hostname: string, port: number | null): string | null {
  if (!hostname || port === null) return null;
  const host = hostname.includes(':') && !hostname.startsWith('[') ? `[${hostname}]` : hostname;
  return `http://${host}:${port}/`;
}

export function websdrState(st: WebSdrStatus): { label: string; variant: Variant; running: boolean } {
  if (st.installed === null) return { label: 'UNKNOWN', variant: 'muted', running: false };
  if (!st.installed) return { label: 'NOT INSTALLED', variant: 'muted', running: false };
  const a = st.active.value;
  if (a === 'active') return { label: 'RUNNING', variant: 'good', running: true };
  if (a === 'activating') return { label: 'STARTING', variant: 'warn', running: false };
  if (a === 'deactivating') return { label: 'STOPPING', variant: 'warn', running: false };
  if (a === 'failed') return { label: 'ENDED (FAILED OR TIME LIMIT)', variant: 'warn', running: false };
  if (a === 'inactive') return { label: 'STOPPED', variant: 'muted', running: false };
  return { label: a === null ? 'UNKNOWN' : a.toUpperCase(), variant: 'muted', running: false };
}

const fmt = (x: Measured<number> | undefined, digits: number, unit: string): string | null =>
  x && x.value !== null ? `${x.value.toFixed(digits)} ${unit}` : null;

export interface CompareRow { label: string; before: string | null; during: string | null; provenance: Measured['provenance'] }

/** Before (the minutes just before it started) against during, figure by figure. */
export function compareRows(before: WebSdrSummary | null, during: WebSdrSummary | null): CompareRow[] {
  const row = (label: string, pick: (s: WebSdrSummary) => Measured<number>, digits: number, unit: string): CompareRow => ({
    label, before: before ? fmt(pick(before), digits, unit) : null, during: during ? fmt(pick(during), digits, unit) : null,
    provenance: (during ? pick(during) : before ? pick(before) : null)?.provenance ?? 'calculated',
  });
  const pulses = (s: WebSdrSummary | null) => s && s.pps_pulses.value !== null
    ? `${s.pps_pulses.value} of ${60 * s.minutes}` : null;
  return [
    row('CPU, mean (all cores)', s => s.cpu_mean_pct, 1, '%'),
    row('CPU, largest 10 s', s => s.cpu_max_pct, 1, '%'),
    row('Web SDR and gate CPU (one core)', s => s.websdr_cpu_mean_pct, 1, '%'),
    row('SoC temperature, mean', s => s.temp_mean_c, 1, '°C'),
    row('SoC temperature, highest', s => s.temp_max_c, 1, '°C'),
    row('PPS jitter, median minute', s => s.pps_jitter_median_ns, 0, 'ns'),
    row('PPS jitter, worst minute', s => s.pps_jitter_max_ns, 0, 'ns'),
    row('PPS largest |phase|', s => s.pps_max_abs_ns, 0, 'ns'),
    { label: 'PPS pulses seen', before: pulses(before), during: pulses(during), provenance: 'observed' },
  ];
}

export function sessionLine(start: string, durationS: number | null, minutes: number): string {
  const d = durationS !== null ? fmtDuration(durationS) : `${minutes} min so far`;
  return `${start.replace('T', ' ').replace('+00:00', ' UTC')} · ${d}`;
}

/** The login row: the installer's setting (configured, not observed). */
export function loginLine(st: WebSdrStatus): string | null {
  const a = st.auth;
  if (!a || a.enabled === null) return null;
  if (!a.enabled) return 'off: anyone on the LAN can listen';
  return a.remember_days === null ? 'on' : `on; "Remember this browser" lasts ${a.remember_days} days`;
}

/** The HF row: which band profiles the installer set (GTP_WEBSDR_HF). */
export function hfLine(hf: WebSdrStatus['hf']): string | null {
  if (hf === undefined || hf === null) return null;
  if (hf === 'direct') return 'direct sampling (Q branch), below about 25 MHz';
  if (hf === 'native') return "the dongle's own HF path";
  return 'off: 24 MHz and up only';
}

const LABEL: Partial<Record<AdminAction, string>> = {
  websdr_start: 'Start web SDR', websdr_stop: 'Stop web SDR', websdr_signout_all: 'Sign out all browsers',
};

/** The line shown after Start, Stop or Sign out all: the station's own answer, never a guess. */
export function websdrOutcome(a: AdminAction, r: AdminResult | null, err?: { message: string; status: number | null },
  pauses?: string | null): { variant: Variant; text: string } {
  const label = LABEL[a] ?? a;
  if (err) {
    if (err.status === null) return { variant: 'warn', text: `${label}: no answer from the station (${err.message}). It may still have run.` };
    return { variant: 'error', text: `${label}: refused. ${err.message}` };
  }
  if (!r) return { variant: 'muted', text: `${label}: no result.` };
  if (r.simulated) return { variant: 'muted', text: `${label}: demo, not executed.` };
  if (!r.ok) return { variant: 'error', text: `${label}: failed${r.detail ? ` (${r.detail})` : ''}.` };
  if (a === 'websdr_signout_all') return { variant: 'good', text: `${label}: done. Every browser has to sign in again.` };
  if (pauses === null) return { variant: 'good', text: `${label}: done. No other service uses its dongle.` };
  const who = pauses ?? 'The service on its dongle';
  return { variant: 'good', text: a === 'websdr_start'
    ? `${label}: done. ${who} is stopped until the web SDR stops.`
    : `${label}: done. ${who} starts again.` };
}
