// Radio & SDR → Aircraft decoders (GET /api/sdr → aircraft; gps_time_pi/sdr.py aircraft()). readsb on
// the 1090 MHz dongle with tar1090, dump978-fa and skyaware978 on the 978 MHz dongle with its own map,
// each dongle picked by its serial. Read only. Values the station couldn't read stay null (UNKNOWN).
import type { SdrAircraftDecoder } from '../api/types';

export type Variant = 'good' | 'warn' | 'error' | 'muted';

const ROLE_VAR: Record<SdrAircraftDecoder['band'], string> = { '1090': 'GTP_SDR_1090_SERIAL', '978': 'GTP_SDR_978_SERIAL' };

/** The decoder's state from its units, its dongle and its feed: never LIVE without a fresh file. */
export function decoderState(d: SdrAircraftDecoder): { label: string; variant: Variant; text: string } {
  if (d.paused_by_websdr) {
    return { label: 'PAUSED', variant: 'warn', text: `The web SDR has dongle ${d.serial}; ${d.decoder} comes back when it stops.` };
  }
  if (!d.serial) {
    return { label: 'OFF', variant: 'muted', text: d.band === '978'
      ? `No 978 MHz dongle (${ROLE_VAR[d.band]}). With one dongle, it is the 1090 MHz one and 978 MHz stays off.`
      : `No 1090 MHz dongle (${ROLE_VAR[d.band]}=none).` };
  }
  const states = d.units.map(u => u.state);
  if (states.some(s => s === null)) return { label: 'UNKNOWN', variant: 'muted', text: 'systemctl could not be read.' };
  if (states.includes('not installed')) return { label: 'NOT INSTALLED', variant: 'muted', text: 'The SDR stack is not installed (GTP_SDR=1).' };
  if (states.includes('failed')) return { label: 'FAILED', variant: 'error', text: `journalctl -u ${d.units[0].unit} says why.` };
  if (states.every(s => s === 'active')) {
    const f = d.feed;
    if (f?.fresh) return { label: 'LIVE', variant: 'good', text: `Decoding on dongle ${d.serial}.` };
    if (f?.present) return { label: 'STALE', variant: 'warn', text: `Running, but ${f.path} hasn't been written for a while.` };
    return { label: 'NO DATA', variant: 'warn', text: `Running, but no ${f?.path ?? 'aircraft.json'} yet.` };
  }
  const odd = states.find(s => s !== 'active') as string;
  return { label: odd.toUpperCase(), variant: 'warn', text: odd === 'activating'
    ? 'Starting, or restarting after an exit: a restart loop shows here.' : `${d.units.map(u => `${u.unit} ${u.state}`).join(', ')}.` };
}

export function unitsLine(d: SdrAircraftDecoder): string {
  return d.units.map(u => `${u.unit.replace(/\.service$/, '')}: ${u.state ?? 'UNKNOWN'}`).join(' · ');
}

/** The dongle by serial, and whether one with that serial is on USB now. */
export function serialLine(d: SdrAircraftDecoder): string {
  if (!d.serial) return 'none';
  const p = d.serial_plugged.value;
  return p === null ? d.serial : p ? `${d.serial} (on USB)` : `${d.serial} (not on USB now)`;
}

export function rateLine(d: SdrAircraftDecoder): number | null {
  return d.feed?.messages_per_s?.value ?? null;
}

export function fmtRate(v: number | null): string | null {
  if (v === null) return null;
  return v < 10 ? v.toFixed(1) : String(Math.round(v));
}

/** The map: installed or not, and paused with its decoder. */
export function mapLine(d: SdrAircraftDecoder): { text: string; link: boolean } {
  if (!d.map.installed) return { text: `${d.map.name}: not installed`, link: false };
  return { text: `${d.map.name} at ${d.map.url}${d.paused_by_websdr ? ' (paused with its decoder)' : ''}`, link: true };
}
