// Pure helpers for the NTP service card (/api/ntp-service) and the NMEA
// offset comparison on the PPS page. Tested in ntpservice.test.ts.

import type { NmeaCalibration, NtpService } from '../api/types';

export type Variant = 'good' | 'warn' | 'error' | 'muted' | 'info';

/** Drops are a warning: chrony's rate limit acted. Nothing here is an error state. */
export function serviceVariant(state: NtpService['state'] | undefined): Variant {
  return state === 'SERVING' ? 'good' : state === 'SERVING_WITH_DROPS' ? 'warn' : state === 'NO_REQUESTS' ? 'info' : 'muted';
}

export function serviceLabel(state: NtpService['state'] | undefined): string {
  return state === 'SERVING' ? 'SERVING' : state === 'SERVING_WITH_DROPS' ? 'SERVING · SOME DROPPED'
       : state === 'NO_REQUESTS' ? 'NO REQUESTS' : 'UNKNOWN';
}

/** Packets per second shown per minute, e.g. 0.2533 -> "15.2 /min". null = UNKNOWN. */
export function fmtPerMin(perSecond: number | null | undefined): string | null {
  if (perSecond === null || perSecond === undefined || !Number.isFinite(perSecond)) return null;
  const v = perSecond * 60;
  return `${v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(2)} /min`;
}

/** A share as a percentage with enough digits to show a small one: 0.00078 -> "0.078%". */
export function fmtShare(fraction: number | null | undefined): string | null {
  if (fraction === null || fraction === undefined || !Number.isFinite(fraction)) return null;
  const pct = fraction * 100;
  return `${pct === 0 ? '0' : pct < 0.1 ? pct.toFixed(3) : pct < 10 ? pct.toFixed(2) : pct.toFixed(1)}%`;
}

export function fmtCount(n: number | null | undefined): string | null {
  return n === null || n === undefined ? null : n.toLocaleString('en-US');
}

/** Requests-per-minute series for the chart (same row shape as the offset chart). */
export function requestSeries(history: NtpService['history'] | undefined) {
  return (history ?? []).map(h => ({ ts: h.t * 1000, t: new Date(h.t * 1000).toISOString(), dt: h.received_per_min }));
}

// ─── NMEA refclock offset: configured and suggested, side by side ────────────

export interface NmeaCompare {
  configured: string | null;      // "0.100 s"; null = UNKNOWN
  suggested: string | null;       // "0.135 s"; null = not measurable now
  difference: string | null;      // "+35 ms"
  suggestedReason: string | null; // why there is no suggestion
  same: boolean;                  // the suggestion equals the configured value to the millisecond
}

const secs = (v: number) => `${v.toFixed(3)} s`;

export function nmeaCompare(cal: NmeaCalibration | undefined | null): NmeaCompare {
  const configured = cal?.configured_offset_s?.value ?? null;
  const out: NmeaCompare = {
    configured: configured === null ? null : secs(configured), suggested: null, difference: null,
    suggestedReason: null, same: false,
  };
  if (!cal) return { ...out, suggestedReason: 'not reported by this station version' };
  const suggested = cal.available ? (cal.suggested_offset_s?.value ?? null) : null;
  if (suggested === null || configured === null) return { ...out, suggestedReason: cal.reason ?? 'not measurable now' };
  const diffMs = Math.round((suggested - configured) * 1000);
  return {
    ...out, suggested: secs(suggested), same: diffMs === 0,
    difference: `${diffMs < 0 ? '−' : '+'}${Math.abs(diffMs)} ms`,
  };
}
