// Aviation → Live aircraft map (GET /api/aircraft-map; gps_time_pi/tar1090.py). tar1090 on readsb's
// 1090 MHz data, served by the station at /tar1090/. While the web SDR runs it has the dongle, so
// tracking pauses and comes back when it stops. Values the station couldn't read stay null.
import type { AircraftMapStatus } from '../api/types';

export type Variant = 'good' | 'warn' | 'error' | 'muted';

export function mapState(st: AircraftMapStatus): { label: string; variant: Variant; text: string } {
  if (!st.installed) return { label: 'NOT INSTALLED', variant: 'muted', text: 'The map comes with the SDR stack\'s 1090 MHz role.' };
  switch (st.state) {
    case 'live': return { label: 'LIVE', variant: 'good', text: 'readsb is decoding 1090 MHz.' };
    case 'paused': return { label: 'PAUSED', variant: 'warn', text: 'The web SDR has the dongle; tracking resumes when it stops.' };
    case 'stale': return { label: 'STALE', variant: 'warn', text: 'readsb has written nothing for a while: is gps-time-readsb running?' };
    case 'no_data': return { label: 'NO DATA', variant: 'muted', text: 'No aircraft.json from readsb yet.' };
    default: return { label: 'UNKNOWN', variant: 'muted', text: '' };
  }
}

export function markerLine(st: AircraftMapStatus): string {
  if (st.location_display === 'hidden') return 'hidden (privacy mode: hidden)';
  if (!st.station_marker) return 'none (no surveyed position yet)';
  return st.location_display === 'rounded' ? 'shown, rounded to 0.1°' : 'shown';
}

export function ageLine(age: number | null): string | null {
  if (age === null) return null;
  return age < 10 ? `${age.toFixed(1)} s` : `${Math.round(age)} s`;
}

/** The 978 MHz map (skyaware978 on dump978-fa's UAT data, at /skyaware978/); absent before rc.8. */
export type UatMap = NonNullable<AircraftMapStatus['uat']>;

export function uatState(u: UatMap | undefined): { label: string; variant: Variant; text: string } {
  if (!u) return { label: 'UNKNOWN', variant: 'muted', text: 'This station doesn\'t report the 978 MHz map (before v1.6.0-rc.8).' };
  if (!u.installed) return { label: 'NOT INSTALLED', variant: 'muted', text: 'The 978 MHz map comes with the SDR stack\'s 978 MHz role.' };
  switch (u.state) {
    case 'live': return { label: 'LIVE', variant: 'good', text: 'dump978-fa is decoding 978 MHz UAT.' };
    case 'paused': return { label: 'PAUSED', variant: 'warn', text: 'The web SDR has the 978 MHz dongle; tracking resumes when it stops.' };
    case 'stale': return { label: 'STALE', variant: 'warn', text: 'skyaware978 has written nothing for a while: are gps-time-dump978 and gps-time-skyaware978 running?' };
    case 'no_data': return { label: 'NO DATA', variant: 'muted', text: 'No aircraft.json from skyaware978 yet.' };
    default: return { label: 'UNKNOWN', variant: 'muted', text: '' };
  }
}
