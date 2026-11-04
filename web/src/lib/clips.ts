// Radio → Clips (GET /api/clips; gps_time_pi/clips.py). The page checks a request the way the station
// does before sending it; the station checks again, and its recorder unit does the recording.
import type { ClipKind, ClipRequest, ClipRow, ClipsStatus } from '../api/types';

export type Variant = 'good' | 'warn' | 'error' | 'muted';

export function estimateBytes(req: ClipRequest): number {
  return req.kind === 'iq' ? Math.round((req.rate ?? 1_024_000) * 2 * req.seconds) + 8192 : Math.round(48_000 * 2 * req.seconds) + 8192;
}

export function checkRequest(st: ClipsStatus, kind: ClipKind, mhz: string, seconds: string, rate: number): { req: ClipRequest | null; problem: string | null } {
  const f = Math.round(parseFloat(mhz) * 1e6), s = parseFloat(seconds);
  if (!Number.isFinite(f) || f < st.freq_range_hz[0] || f > st.freq_range_hz[1])
    return { req: null, problem: `Frequency must be ${st.freq_range_hz[0] / 1e6}–${st.freq_range_hz[1] / 1e6} MHz.` };
  if (!Number.isFinite(s) || s < 1 || s > st.max_seconds) return { req: null, problem: `Length must be 1–${st.max_seconds} s.` };
  const req: ClipRequest = { kind, freq_hz: f, seconds: s, ...(kind === 'iq' ? { rate } : {}) };
  const cap = st.storage.max_mb * 1024 * 1024;
  if (estimateBytes(req) > cap) return { req: null, problem: `About ${Math.round(estimateBytes(req) / 1e6)} MB, more than the ${st.storage.max_mb} MB cap.` };
  return { req, problem: null };
}

export function storageLine(st: ClipsStatus): { text: string; variant: Variant } {
  if (st.storage.problem) return { text: `Clips can't be kept: ${st.storage.problem}.`, variant: 'error' };
  const used = st.storage.used.value;
  const where = st.storage.kind === 'ram' ? 'in RAM (cleared at reboot)' : `on ${st.storage.dir}`;
  return { text: `${st.clips.length} clip${st.clips.length === 1 ? '' : 's'} ${where}, ${used === null ? 'UNKNOWN' : (used / 1e6).toFixed(1)} of ${st.storage.max_mb} MB; the oldest go first.`, variant: 'muted' };
}

export function timeLabel(c: ClipRow): string {
  const src = c.time_source === 'pps' ? 'station clock (GNSS/PPS)' : c.time_source === 'ntp' ? 'ntp' : c.time_source === 'free_running' ? 'free running' : 'UNKNOWN';
  const u = c.sample_time_uncertainty_s;
  return `${src}${u !== null ? `, ±${u >= 0.1 ? u.toFixed(2) + ' s' : Math.round(u * 1000) + ' ms'} (USB buffering)` : ''}`;
}

export function lastLine(st: ClipsStatus): { text: string; variant: Variant } | null {
  if (st.pending) return { text: `Recording ${st.pending.kind} at ${(st.pending.freq_hz / 1e6).toFixed(4)} MHz for ${st.pending.seconds} s…`, variant: 'warn' };
  if (!st.last) return null;
  return st.last.ok ? { text: `Last clip recorded: ${st.last.clip}.`, variant: 'good' } : { text: `Last clip failed: ${st.last.error}.`, variant: 'error' };
}
