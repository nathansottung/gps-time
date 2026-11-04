// Radio → Web SDR (GET /api/websdr; gps_time_pi/websdr.py). OpenWebRX+ behind the station's
// password gate, LAN only. Started and stopped with the admin actions websdr_start / websdr_stop.
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

/** The line shown after Start or Stop: the station's own answer, never a guess. */
export function websdrOutcome(a: AdminAction, r: AdminResult | null, err?: { message: string; status: number | null }): { variant: Variant; text: string } {
  const label = a === 'websdr_start' ? 'Start web SDR' : 'Stop web SDR';
  if (err) {
    if (err.status === null) return { variant: 'warn', text: `${label}: no answer from the station (${err.message}). It may still have run.` };
    return { variant: 'error', text: `${label}: refused. ${err.message}` };
  }
  if (!r) return { variant: 'muted', text: `${label}: no result.` };
  if (r.simulated) return { variant: 'muted', text: `${label}: demo, not executed.` };
  if (!r.ok) return { variant: 'error', text: `${label}: failed${r.detail ? ` (${r.detail})` : ''}.` };
  return { variant: 'good', text: a === 'websdr_start'
    ? `${label}: done. readsb is stopped until the web SDR stops.`
    : `${label}: done. readsb starts again.` };
}
