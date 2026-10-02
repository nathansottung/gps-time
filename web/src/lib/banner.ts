// Pure banner logic (no React), shared by the banner, header chip and
// timing-chain card, and unit-tested in banner.test.ts.

import type { TimingChain, TimingStatus } from '../api/types';
import { fmtDuration, fmtUtc } from './format';

export type Variant = 'good' | 'warn' | 'error' | 'muted' | 'info';

export function statusVariant(code: string | undefined): Variant {
  if (!code || code === 'UNKNOWN') return 'muted';
  if (code === 'GPS_PPS') return 'good';
  if (code === 'UNSYNCHRONIZED') return 'error';
  return 'warn';
}

export interface BannerView {
  variant: Variant;
  title: string;
  detail: string | null;
  outage: string | null;      // "PPS unavailable for 2d 07h 14m (since …)"
}

/**
 * The banner text, with two guards so the UI can never overstate timing:
 * - a GPS/PPS status while chrony reports a non-PPS selected source is shown
 *   as UNKNOWN (inconsistent), not as Stratum 1 GPS/PPS;
 * - a status without a source qualifier gets the selected source appended,
 *   so a bare "SYNCHRONIZED" is never shown.
 */
export function bannerView(chain: TimingChain | null, unreachable: boolean): BannerView {
  if (!chain) {
    return { variant: unreachable ? 'error' : 'muted',
             title: unreachable ? 'TIMING STATUS UNKNOWN · STATION UNREACHABLE' : 'TIMING STATUS UNKNOWN',
             detail: null, outage: null };
  }
  const st: TimingStatus = chain.status;
  const sel = chain.chrony.selected;
  if (st.code === 'GPS_PPS' && sel && !sel.is_pps) {
    return { variant: 'warn', title: 'TIMING STATUS UNKNOWN · INCONSISTENT REPORT',
             detail: `Status says GPS/PPS but chrony's selected source is ${sel.name}.`, outage: outageText(chain) };
  }
  let title = st.banner || st.headline || 'UNKNOWN';
  if (!title.includes('·') && st.code !== 'UNKNOWN') {
    title += ` · SOURCE ${sel ? sel.name.toUpperCase() : 'UNKNOWN'}`;
  }
  return { variant: statusVariant(st.code), title, detail: st.detail || null, outage: outageText(chain) };
}

function outageText(chain: TimingChain): string | null {
  const ev = chain.events.open;
  if (!ev) return null;
  const since = fmtUtc(ev.start_utc);
  const bound = ev.start_bound ? ' or earlier' : '';
  return `PPS unavailable for ${fmtDuration(ev.duration_s) ?? 'UNKNOWN'}${since ? ` (since ${since}${bound})` : ''}`;
}
