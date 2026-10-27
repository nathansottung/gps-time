// Administration → SDR receivers (GET /api/sdr; gps_time_pi/sdr.py). Read only: the page starts,
// stops and configures none of it. Values the station couldn't read stay null (UNKNOWN).
import type { SdrDongle, SdrFeed, SdrStatus, SdrUnit } from '../api/types';
import { fmtDuration } from './format';

export type Variant = 'good' | 'warn' | 'error' | 'muted';

/** The card's one-line summary. */
export function sdrSummary(st: SdrStatus): { text: string; variant: Variant } {
  if (st.installed === null) return { text: 'UNKNOWN: systemctl could not be read', variant: 'muted' };
  if (!st.installed) return { text: 'Not installed. It is optional: sudo GTP_SDR=1 … bash install.sh (docs/deploy/sdr-stack.md)', variant: 'muted' };
  const units = (st.units ?? []).filter(u => u.unit !== 'gps-time-modules.service');
  const active = units.filter(u => u.active.value === 'active').length;
  return { text: `${active} of ${units.length} receiver units running`, variant: active === units.length ? 'good' : 'warn' };
}

export function unitState(u: SdrUnit): { label: string; variant: Variant } {
  const a = u.active.value;
  if (a === null) return { label: 'UNKNOWN', variant: 'muted' };
  if (a === 'active') return { label: 'RUNNING', variant: 'good' };
  if (a === 'failed') return { label: 'FAILED', variant: 'error' };
  if (a === 'inactive') return { label: u.enabled === 'enabled' ? 'STOPPED' : 'OFF', variant: u.enabled === 'enabled' ? 'warn' : 'muted' };
  return { label: a.toUpperCase(), variant: 'warn' };
}

const num = (v: number | null, unit: string) => (v === null ? null : `${v} ${unit}`);

export function unitRows(st: SdrStatus): { unit: string; what: string; state: { label: string; variant: Variant };
  cpu: string | null; memory: string | null; restarts: string | null }[] {
  return (st.units ?? []).map(u => ({
    unit: u.unit, what: u.what, state: unitState(u),
    cpu: num(u.cpu_avg_pct.value, '%'), memory: num(u.memory_mib.value, 'MiB'),
    restarts: u.restarts.value === null ? null : String(u.restarts.value),
  }));
}

export function dongleRow(d: SdrDongle): { port: string; serial: string; role: string; speed: string | null; problem: string | null } {
  const speed = d.speed_mbps.value;
  return {
    port: d.port, serial: d.serial ?? 'UNKNOWN', role: d.role ?? 'no role (serial not given to the installer)',
    speed: speed === null ? null : `${speed} Mb/s`,
    problem: d.dvb_driver.value ? 'held by the DVB-T driver: reboot (rtl-sdr blacklists it)'
      : speed !== null && speed < 480 ? 'below USB 2.0 high speed: samples will be dropped' : null,
  };
}

export function feedRow(f: SdrFeed): { band: string; state: { label: string; variant: Variant }; age: string | null; aircraft: string | null } {
  const state = !f.present ? { label: 'NO FILE', variant: 'muted' as Variant }
    : f.fresh ? { label: 'FRESH', variant: 'good' as Variant } : { label: 'STALE', variant: 'warn' as Variant };
  return {
    band: `${f.band} MHz`, state,
    age: f.age_s.value === null ? null : `${fmtDuration(f.age_s.value)} ago`,
    aircraft: f.aircraft.value === null ? null : String(f.aircraft.value),
  };
}
