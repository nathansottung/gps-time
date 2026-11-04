// Radio → Web SDR → Airband bookmarks (GET /api/airband; gps_time_pi/airband.py). The NASR set carries
// its cycle date and is flagged once it's more than 28 days old; Refresh now is the admin action
// refresh_airband (the station fetches; this page never does).
import type { AirbandBookmark, AirbandStatus } from '../api/types';

export type Variant = 'good' | 'warn' | 'error' | 'muted';

export function mhz(hz: number): string {
  return (hz / 1e6).toFixed(3);
}

export function cycleLine(st: AirbandStatus): { text: string; variant: Variant } {
  const n = st.nasr;
  if (!n) return { text: `No FAA set yet: only the ${st.built_in.length} built-in channels. The current NASR cycle is ${st.current_cycle}.`, variant: 'muted' };
  const age = n.age_days.value;
  const ageText = age === null ? 'age UNKNOWN' : `${age} day${age === 1 ? '' : 's'} old`;
  if (n.stale) return { text: `FAA NASR cycle ${n.cycle} (${ageText}): past 28 days, out of date. The current cycle is ${st.current_cycle}.`, variant: 'warn' };
  return { text: `FAA NASR cycle ${n.cycle} (${ageText}), ${n.count} channel${n.count === 1 ? '' : 's'} within ${n.radius_km} km.`, variant: 'good' };
}

export function refreshLine(st: AirbandStatus): { text: string; variant: Variant } | null {
  const r = st.last_refresh;
  if (!r) return null;
  if (r.ok) return { text: `Last refresh ${r.at_utc.replace('T', ' ').replace('+00:00', ' UTC')}: cycle ${r.cycle}, ${r.count} channels.`, variant: 'muted' };
  return { text: `Last refresh ${r.at_utc.replace('T', ' ').replace('+00:00', ' UTC')} failed: ${r.error}. The previous bookmarks stay.`, variant: 'error' };
}

export function rows(st: AirbandStatus): AirbandBookmark[] {
  return [...st.built_in, ...(st.nasr?.bookmarks ?? [])];
}
