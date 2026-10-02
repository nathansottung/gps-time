// Display helpers for station API values. null/undefined in → null out, so
// callers render UNKNOWN (MetricRow does this) instead of inventing a value.

const C = 299_792_458; // m/s

/** Signed time offset in seconds → value + unit (ns, µs, ms, s), Unicode minus. */
export function fmtOffset(s: number | null | undefined, digits = 1): { value: string; unit: string } | null {
  if (s === null || s === undefined || !Number.isFinite(s)) return null;
  const a = Math.abs(s);
  const [k, unit] = a < 1e-6 ? [1e9, 'ns'] : a < 1e-3 ? [1e6, 'µs'] : a < 1 ? [1e3, 'ms'] : [1, 's'];
  const v = (s * k).toFixed(digits);
  return { value: (s > 0 ? '+' : s < 0 ? '−' : '') + v.replace('-', ''), unit };
}

/** Unsigned magnitude (uncertainty, RMS) → "4.1 ns". */
export function fmtSeconds(s: number | null | undefined, digits = 1): string | null {
  const o = fmtOffset(s === null || s === undefined ? s : Math.abs(s), digits);
  return o ? `${o.value.replace('+', '')} ${o.unit}` : null;
}

/** Light-travel distance in vacuum for a time interval (calculated). */
export function lightDistance(s: number | null | undefined): string | null {
  if (s === null || s === undefined || !Number.isFinite(s)) return null;
  const d = Math.abs(s) * C;
  if (d < 1) return `${(d * 100).toFixed(1)} cm`;
  if (d < 1000) return `${d.toFixed(2)} m`;
  return `${(d / 1000).toFixed(1)} km`;
}

/** Duration in seconds → "13d 0h 24m", "2m 41s", "34s". */
export function fmtDuration(s: number | null | undefined): string | null {
  if (s === null || s === undefined || !Number.isFinite(s)) return null;
  s = Math.max(0, Math.round(s));
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (d) return `${d}d ${h}h ${m}m`;
  if (h) return `${h}h ${String(m).padStart(2, '0')}m`;
  if (m) return `${m}m ${String(sec).padStart(2, '0')}s`;
  return `${sec}s`;
}

/** Signed change in seconds → "+3m 02.8s" / "−2m 11.3s". */
export function fmtDelta(s: number | null | undefined): string | null {
  if (s === null || s === undefined || !Number.isFinite(s)) return null;
  const sign = s > 0 ? '+' : s < 0 ? '−' : '';
  const a = Math.abs(s), m = Math.floor(a / 60), r = a - m * 60;
  return `${sign}${m ? `${m}m ` : ''}${r.toFixed(1).padStart(m ? 4 : 1, '0')}s`;
}

/** ISO instant → wall-clock time in a time zone ("06:48:04"). */
export function fmtClock(isoStr: string | null | undefined, tz?: string, seconds = true): string | null {
  if (!isoStr) return null;
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString('en-GB', { timeZone: tz, hour: '2-digit', minute: '2-digit', second: seconds ? '2-digit' : undefined, hour12: false });
}

/** ISO instant → "2026-09-29 22:12 UTC". */
export function fmtUtc(isoStr: string | null | undefined): string | null {
  if (!isoStr) return null;
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
}

/**
 * chrony "Frequency" text → fractional frequency offset of the uncorrected
 * system clock (Δf/f). "1.240 ppm slow" → −1.240e-6; "2.117 ppm fast" → +2.117e-6.
 */
export function chronyFreqToFrac(text: string | null | undefined): number | null {
  const mm = /(-?[\d.]+)\s*ppm\s*(fast|slow)/.exec(text ?? '');
  if (!mm) return null;
  const v = parseFloat(mm[1]) * 1e-6;
  return mm[2] === 'slow' ? -v : v;
}

export function browserTimeZone(): string {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch { return 'UTC'; }
}
