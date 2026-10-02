// Version shown in the footer. The UI version comes from the git tag at build
// time (vite.config.ts); the station version is /api → versions.app, from the
// same tag (gps_time_pi/version.py). They differ when web/dist was built from
// another commit than the station code, so both are shown then.

export const UI_VERSION: string = __GTP_UI_VERSION__;

const UNKNOWN = 'unknown';

function known(v: string | null | undefined): string | null {
  const s = (v ?? '').trim().replace(/^v(?=\d)/, '');
  return s && s !== UNKNOWN ? s : null;
}

/** Footer text. `station` is undefined while /api hasn't answered. */
export function versionLine(ui: string, station: string | null | undefined): string {
  const u = known(ui);
  const s = known(station);
  const uiText = u ? `UI v${u}` : 'UI version unknown';
  if (station === undefined) return uiText;
  if (u && s && u === s) return `v${u}`;
  return `${uiText} · ${s ? `station v${s}` : 'station version unknown'}`;
}
