// Administration → Feeders and Location sharing (GET /api/feeders; gps_time_pi/feeders.py).
// Turning a feeder (or MLAT) on needs the admin token and the confirmation typed exactly; off needs
// neither confirmation. The station checks the same rules; these only explain them before sending.
import type { FeederRow, FeedersStatus, SettingResult } from '../api/types';

export type Variant = 'good' | 'warn' | 'error' | 'muted';

/** The location warning on a card, in plain words: exact location only when MLAT is on. Every card carries
 *  the warning in amber, MLAT on or off, Beast feeders too (owner, 2026-11-04): the aircraft a feed carries
 *  show roughly where the station is. */
export function locationWarning(row: FeederRow): { text: string; variant: Variant } {
  if (row.mlat?.on) return { text: `Shares your exact location with ${row.service}.`, variant: 'warn' };
  if (row.mlat) return { text: `Shares your location with ${row.service}: the aircraft it receives show roughly where the station is. Your exact location only with MLAT, which is off.`, variant: 'warn' };
  return { text: `Shares your location with ${row.service}: the aircraft it receives show roughly where the station is. Never your exact location: the feed carries no position.`, variant: 'warn' };
}

export function feederState(row: FeederRow): { label: string; variant: Variant } {
  const a = row.active.value;
  if (!row.on) return { label: 'OFF', variant: 'muted' };
  if (a === 'active') return { label: 'SENDING', variant: 'good' };
  if (a === null) return { label: 'UNKNOWN', variant: 'muted' };
  if (a === 'failed') return { label: 'FAILED', variant: 'error' };
  return { label: a.toUpperCase(), variant: 'warn' };
}

/** Whether the typed text turns it on (exactly, as the station checks). */
export function confirmed(typed: string, want: string): boolean {
  return typed === want;
}

export function sharingSummary(st: FeedersStatus): { text: string; variant: Variant } {
  const active = st.sharing.rows.filter(r => r.active);
  if (st.sharing.exact_location_shared) return { text: 'The station’s exact location is being shared (see below).', variant: 'warn' };
  if (!active.length) return { text: 'Nothing shares the station’s location.', variant: 'good' };
  return { text: `${active.length} item${active.length === 1 ? '' : 's'} active; none shares the exact location.`, variant: 'muted' };
}

export function outcome(what: string, r: SettingResult | null, err?: { message: string; status: number | null }): { text: string; variant: Variant } {
  if (err) return { text: `${what}: ${err.status === null ? 'no answer from the station' : 'refused'}. ${err.message}`, variant: err.status === null ? 'warn' : 'error' };
  if (!r) return { text: `${what}: no result.`, variant: 'muted' };
  if ('simulated' in r && r.simulated) return { text: `${what}: demo, nothing was started or sent.`, variant: 'muted' };
  return { text: `${what}: done.`, variant: 'good' };
}
