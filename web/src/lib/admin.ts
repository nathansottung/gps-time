// Station actions on the Administration page (POST /api/admin). The station runs a fixed
// command for each (gps_time_pi/system.py, authorized by polkit); nothing from the page is
// passed to it. Actions that interrupt timing or this page ask for confirmation first.
import type { AdminAction, AdminResult } from '../api/types';

export interface ActionInfo {
  action: AdminAction;
  label: string;
  /** What happens, shown under the buttons and in the confirmation. */
  effect: string;
  /** Asked before sending; null = sent on the first click. */
  confirm: string | null;
}

export const STATION_ACTIONS: readonly ActionInfo[] = [
  { action: 'flush_logs', label: 'Flush logs to SD now', confirm: null,
    effect: "Writes the tracking log's new lines from RAM to the SD card now instead of at the next hourly flush." },
  { action: 'restart_gpsd', label: 'Restart gpsd',
    effect: 'GNSS data from the receiver pauses for a few seconds.',
    confirm: "Restart gpsd? The station's GNSS data pauses for a few seconds." },
  { action: 'restart_chrony', label: 'Restart chrony',
    effect: 'NTP clients see a brief gap, and PPS selection takes a few minutes to come back.',
    confirm: 'Restart chrony? NTP clients see a brief gap, and selecting PPS again takes a few minutes.' },
  { action: 'restart_web', label: 'Restart web service',
    effect: 'This page loses the station for a few seconds. The RAM histories (stability, references, NTP service, PPS counters) start empty.',
    confirm: 'Restart the web service? The RAM histories (stability, references, NTP service, PPS counters) start empty.' },
  { action: 'reboot', label: 'Reboot the Pi',
    effect: 'Time service stops until the Pi is back. The RAM histories start empty.',
    confirm: 'Reboot the Pi? NTP service stops until it is back, and chrony has to select PPS again.' },
];

export function actionInfo(a: AdminAction): ActionInfo {
  const i = STATION_ACTIONS.find(x => x.action === a);
  if (!i) throw new Error(`unknown action ${a}`);
  return i;
}

/** Actions after which the station is expected to drop off for a while. */
export const GOES_AWAY: ReadonlySet<AdminAction> = new Set(['restart_web', 'reboot']);

export type ActionOutcome = { variant: 'good' | 'warn' | 'error' | 'muted'; text: string };

/**
 * The line shown after an action: the station's own answer, never a guess. A request with no
 * answer (status null: timeout or network) may still have run on the station, so it says so.
 */
export function actionOutcome(a: AdminAction, r: AdminResult | null, err?: { message: string; status: number | null }): ActionOutcome {
  const label = actionInfo(a).label;
  if (err) {
    if (err.status === null) return { variant: 'warn', text: `${label}: no answer from the station (${err.message}). It may still have run; check the timing banner.` };
    return { variant: 'error', text: `${label}: refused. ${err.message}` };
  }
  if (!r) return { variant: 'muted', text: `${label}: no result.` };
  if (r.simulated) return { variant: 'muted', text: `${label}: demo, not executed.` };
  const detail = r.detail ? ` (${r.detail})` : '';
  if (!r.ok) return { variant: 'error', text: `${label}: failed${detail}.` };
  if (GOES_AWAY.has(a)) return { variant: 'good', text: `${label}: accepted${detail}. The station will be unreachable for a while; this page reconnects by itself.` };
  return { variant: 'good', text: `${label}: done${detail}.` };
}
