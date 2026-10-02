// View-model helpers: map API payloads onto the shapes the UI components use.
// No values are invented here; missing inputs stay null.

import type { CoreStatus, HistoryPoint, Satellite, TimingChain, TimingEvent } from './types';
import { chronyFreqToFrac } from '../lib/format';

const SYS: Record<string, { key: string; prefix: string }> = {
  GPS: { key: 'GPS', prefix: 'G' }, GLONASS: { key: 'GLONASS', prefix: 'R' }, GALILEO: { key: 'GALILEO', prefix: 'E' },
  BEIDOU: { key: 'BEIDOU', prefix: 'C' }, QZSS: { key: 'QZSS', prefix: 'J' }, SBAS: { key: 'SBAS', prefix: 'S' },
};

export interface SkySat { sys: string; svid: string; az: number; el: number; cn0: number; state: 'used' | 'tracked' }

/** gpsd satellites → sky plot/table rows. Rows without az/el are kept for the table (az/el NaN) but not plotted. */
export function toSkySats(sats: Satellite[]): SkySat[] {
  return sats.map(s => {
    const sys = SYS[(s.gnss || '').toUpperCase()] ?? { key: (s.gnss || '?').toUpperCase(), prefix: '' };
    const id = typeof s.id === 'number' ? String(s.id).padStart(2, '0') : String(s.id);
    return { sys: sys.key, svid: sys.prefix + id, az: s.az ?? NaN, el: s.el ?? NaN, cn0: s.snr ?? NaN,
             state: s.used ? 'used' : 'tracked' };
  });
}

export const plottable = (xs: SkySat[]) => xs.filter(s => Number.isFinite(s.az) && Number.isFinite(s.el));

export function cn0Stats(sats: SkySat[]) {
  const v = sats.map(s => s.cn0).filter(Number.isFinite).sort((a, b) => a - b);
  if (!v.length) return { best: null, median: null, mean: null };
  return { best: v[v.length - 1], median: v[Math.floor(v.length / 2)], mean: v.reduce((a, b) => a + b, 0) / v.length };
}

/** chrony tracking-log points → chart series for the last rangeS seconds, in a unit that fits the data. */
export function toOffsetSeries(points: HistoryPoint[] | undefined, rangeS: number, nowMs = Date.now()) {
  const from = nowMs / 1000 - rangeS;
  const pts = (points ?? []).filter(p => p.t >= from);
  const maxAbs = pts.reduce((a, p) => Math.max(a, Math.abs(p.offset_s)), 0);
  const [k, unit] = maxAbs < 1e-6 ? [1e9, 'ns'] : maxAbs < 1e-3 ? [1e6, 'µs'] : [1e3, 'ms'];
  return { unit, data: pts.map(p => ({ ts: p.t * 1000, t: new Date(p.t * 1000).toISOString(), dt: p.offset_s * k })) };
}

/** RMS of offsets over a window (calculated from the tracking log). */
export function rmsOffset(points: HistoryPoint[] | undefined, rangeS: number, nowMs = Date.now()): number | null {
  const from = nowMs / 1000 - rangeS;
  const v = (points ?? []).filter(p => p.t >= from).map(p => p.offset_s);
  return v.length ? Math.sqrt(v.reduce((a, x) => a + x * x, 0) / v.length) : null;
}

/** Frequency of the uncorrected system clock (Δf/f) from chrony tracking. */
export function fracFreq(core: CoreStatus | null): number | null {
  if (!core) return null;
  return chronyFreqToFrac(core.quality.frequency);
}

/** Events newest first, open event on top. */
export function allEvents(open: TimingEvent | null | undefined, recent: TimingEvent[] | undefined): TimingEvent[] {
  const xs = [...(recent ?? [])].sort((a, b) => b.start_epoch - a.start_epoch);
  return open ? [open, ...xs.filter(e => e.id !== open.id)] : xs;
}

/** Satellite counts, or null when gpsd's sky report is stale or missing (old counts are not current observations). */
export function satCounts(gps: CoreStatus['gps'] | undefined): { visible: number | null; used: number | null } {
  if (!gps || gps.sky_stale) return { visible: null, used: null };
  return { visible: gps.visible, used: gps.used };
}

/**
 * NTP client count. chrony.clients() returns [] both for "no clients" and for
 * "chronyc failed", so the count is UNKNOWN whenever the timing chain says
 * chronyc tracking is unavailable. (chronyc clients can also be refused without
 * privileges while tracking works; see docs/api/README.md.)
 */
export function ntpClientCount(core: CoreStatus | null, chain: TimingChain | null): number | null {
  if (!core) return null;
  if (!chain || !chain.chrony.available.tracking) return null;
  return core.clients.length;
}
