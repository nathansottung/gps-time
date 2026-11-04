// Administration → Admin sign-in (POST /api/login, /api/logout; GET /api/auth). The admin token buys a
// signed HttpOnly cookie, so the page never keeps the token: "Remember this browser" makes the cookie
// last 30 days, otherwise it ends when the browser closes. Tested in signin.test.ts.
import type { AuthState } from '../api/types';

export type Variant = 'good' | 'warn' | 'error' | 'muted';

/** The badge on the sign-in card: the station's own answer, never a guess. */
export function signInState(a: AuthState | null, failed: boolean): { label: string; variant: Variant } {
  if (!a) return { label: failed ? 'UNKNOWN' : '…', variant: 'muted' };
  if (a.demo) return { label: 'DEMO: NO SIGN-IN NEEDED', variant: 'good' };
  if (!a.admin_configured) return { label: 'ADMIN DISABLED ON THIS STATION', variant: 'muted' };
  if (a.authenticated) return { label: 'SIGNED IN', variant: 'good' };
  return { label: 'SIGNED OUT', variant: 'warn' };
}

/** "Signed in until …" or "until this browser closes", from the cookie's expiry the station reports. */
export function sessionLine(a: AuthState | null, now = Date.now()): string | null {
  const s = a?.session;
  if (!a?.authenticated || !s) return null;
  if (!s.remembered) return 'Signed in until this browser closes (at most 12 hours).';
  const days = Math.max(0, Math.round((Date.parse(s.expires_utc) - now) / 86_400_000));
  return `This browser is remembered until ${s.expires_utc.slice(0, 10)} (${days} days).`;
}

/** The line after a sign-in attempt. */
export function signInOutcome(r: { ok: boolean; simulated?: boolean } | null, err?: { status: number | null; message: string }): { text: string; variant: Variant } {
  if (err) {
    if (err.status === 401) return { text: 'Wrong admin token.', variant: 'error' };
    if (err.status === 429) return { text: 'Too many wrong tokens; wait a while and try again.', variant: 'error' };
    if (err.status === 403) return { text: `Refused: ${err.message}`, variant: 'error' };
    return { text: `No answer from the station (${err.message}).`, variant: 'warn' };
  }
  if (r?.simulated) return { text: 'Demo: no sign-in needed.', variant: 'muted' };
  return r?.ok ? { text: 'Signed in.', variant: 'good' } : { text: 'Not signed in.', variant: 'error' };
}

/** What the sign-in guards, listed on the card. */
export const GUARDED = 'feeders and MLAT, station actions (reboot, restarts), settings and modules, location privacy, the survey reset';
