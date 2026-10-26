// Typed client for the station HTTP API. Reference: docs/api/README.md.
//
// Two implementations share the StationApi interface:
//   httpApi()  — talks to gps_time_pi/server.py (same origin when served from /app/)
//   demoApi()  — src/api/demo.ts, synthetic payloads in the same shapes, no network
//
// The UI never falls back from http to demo on error: a failed request is shown
// as an error/UNKNOWN, never replaced by synthetic numbers.

import { authHeader, tokenStore, type TokenStore } from './auth';
import type {
  AdminAction, AdminResult, Almanac, AuthState, AlmanacQuery, CoreStatus,
  EvidenceIndex, History, LocationMode, ModulesState, NtpService, ObjectResult, Oscillator, Ping, References, Satellites, SettingResult, Shadow, Stability, Survey, SystemDiagnostics,
  TimeScales, TimingChain, Unavailable,
} from './types';

export type DataSource = 'live' | 'demo';

export interface StationApi {
  readonly source: DataSource;
  core(): Promise<CoreStatus>;
  timingChain(opts?: { scenario?: string }): Promise<TimingChain>;
  history(): Promise<History>;
  /** ADEV/MDEV/TDEV of the system clock against kernel PPS (calculated; RAM history). */
  stability(): Promise<Stability>;
  /** TAI, GPS time, MJD/JD offsets, the leap-second table and UT1 − UTC from a cached file. */
  timescales(): Promise<TimeScales>;
  /** The station compared with NTP servers that are not steering its clock (external). */
  references(opts?: { scenario?: string; history?: string }): Promise<References>;
  /** chrony's NTP server counters (packets received and dropped) with rates. */
  ntpService(): Promise<NtpService>;
  /** SoC temperature logged with chrony's frequency, 10-minute bins (input for the oscillator profile). */
  oscillator(): Promise<Oscillator>;
  /** Outage evidence files kept on the SD card (index only). */
  evidence(): Promise<EvidenceIndex>;
  /** Earth-shadow geometry over the station's sky (modeled). az/alt ask about one direction. */
  shadow(opts?: { shell?: number; az?: number; alt?: number }): Promise<Shadow>;
  /** Individual satellites from cached orbital elements: now, and passes. */
  satellites(opts?: { sat?: number; q?: string }): Promise<Satellites>;
  survey(): Promise<Survey>;
  system(): Promise<SystemDiagnostics>;
  almanac(q?: AlmanacQuery): Promise<Almanac | Unavailable>;
  /** One object for the lookup card; no side effect on the station. */
  object(q: string, o?: AlmanacQuery): Promise<ObjectResult>;
  ping(): Promise<Ping>;
  diagnostics(opts?: { scenario?: string }): Promise<string>;
  setLocationDisplay(mode: LocationMode): Promise<SettingResult>;
  /** Local-time display zone override (IANA name); null = automatic. Display only. */
  setTimezone(tz: string | null): Promise<SettingResult>;
  resetSite(): Promise<SettingResult>;
  /** Installed modules, the experimental switch and each module's setting (read only). */
  modules(): Promise<ModulesState>;
  /** The experimental modules switch; either way every module is off afterwards. Admin token. */
  setModulesExperimental(on: boolean): Promise<SettingResult>;
  /** One module on or off (on needs the switch). Admin token. */
  setModule(name: string, enabled: boolean): Promise<SettingResult>;
  admin(action: AdminAction): Promise<AdminResult>;
  /** Whether admin is enabled on the station and whether the stored token is accepted. */
  auth(): Promise<AuthState>;
  /** Admin token for state-changing requests (POST + Bearer); kept per tab. */
  readonly token: TokenStore;
}

export class ApiError extends Error {
  constructor(public readonly path: string, public readonly status: number | null, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

/** The server reports handler exceptions as HTTP 200 with {"error": "..."}. */
function rejectServerError(path: string, body: unknown) {
  if (body && typeof body === 'object' && 'error' in body && Object.keys(body).length === 1) {
    throw new ApiError(path, 200, String((body as { error: unknown }).error));
  }
}

function query(params: Record<string, string | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') q.set(k, v);
  const s = q.toString();
  return s ? `?${s}` : '';
}

/**
 * @param base URL prefix of the station, '' for same origin. The built app is
 *             served from /app/ and the API from /api, both on the station.
 */
export function httpApi(base = '', timeoutMs = 8000, token: TokenStore = tokenStore()): StationApi {
  async function request(path: string, init?: RequestInit): Promise<Response> {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), timeoutMs);
    try {
      const r = await fetch(base + path, { cache: 'no-store', ...init, signal: ctl.signal });
      if (!r.ok) {
        // Auth/method errors carry {"ok": false, "error": "..."}; surface the station's reason.
        let reason = `HTTP ${r.status}`;
        try { const b = await r.json(); if (b && typeof b.error === 'string') reason = `${b.error} (HTTP ${r.status})`; } catch { /* not JSON */ }
        throw new ApiError(path, r.status, `${path}: ${reason}`);
      }
      return r;
    } catch (e) {
      if (e instanceof ApiError) throw e;
      const msg = (e as Error).name === 'AbortError' ? `${path}: timed out` : `${path}: ${(e as Error).message}`;
      throw new ApiError(path, null, msg);
    } finally {
      clearTimeout(timer);
    }
  }
  async function json<T>(path: string, init?: RequestInit): Promise<T> {
    const body = await (await request(path, init)).json();
    rejectServerError(path, body);
    return body as T;
  }
  // State changes: POST, JSON body, admin token (the station refuses GET, other
  // content types, cross-origin requests and missing/wrong tokens).
  const post = (body?: unknown): RequestInit => ({
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader(token.get()) },
    body: body === undefined ? '{}' : JSON.stringify(body),
  });

  return {
    source: 'live',
    core: () => json('/api'),
    timingChain: (o) => json('/api/timing-chain' + query({ scenario: o?.scenario })),
    history: () => json('/api/history'),
    stability: () => json('/api/stability'),
    timescales: () => json('/api/timescales'),
    references: (o) => json('/api/references' + query({ scenario: o?.scenario, history: o?.history })),
    ntpService: () => json('/api/ntp-service'),
    oscillator: () => json('/api/oscillator'),
    evidence: () => json('/api/evidence'),
    shadow: (o) => json('/api/shadow' + query({ shell: o?.shell?.toString(), az: o?.az?.toString(), alt: o?.alt?.toString() })),
    satellites: (o) => json('/api/satellites' + query({ sat: o?.sat?.toString(), q: o?.q })),
    survey: () => json('/api/survey'),
    system: () => json('/api/system'),
    almanac: (q) => json('/api/almanac' + query({ date: q?.date, tz: q?.tz, at: q?.at, target: q?.target })),
    object: async (q, o) => {
      try {
        return await json<ObjectResult>('/api/object' + query({ q, date: o?.date, tz: o?.tz, at: o?.at }));
      } catch (e) {
        // {"error": "unparsed"} is an answer (the query wasn't understood), not a server failure.
        if (e instanceof ApiError && e.status === 200 && e.message === 'unparsed') return { error: 'unparsed' as const };
        throw e;
      }
    },
    ping: () => json('/api/ping' + query({ n: String(Math.random()).slice(2, 10) })),
    diagnostics: async (o) => (await request('/api/diagnostics' + query({ scenario: o?.scenario }))).text(),
    setLocationDisplay: (mode) => json('/api/setting', post({ location_display: mode })),
    setTimezone: (tz) => json('/api/setting', post({ timezone: tz })),
    resetSite: () => json('/api/setting', post({ reset_site: true })),
    modules: () => json('/api/modules'),
    setModulesExperimental: (on) => json('/api/setting', post({ modules_experimental: on })),
    setModule: (name, enabled) => json('/api/setting', post({ module: name, enabled })),
    admin: (action) => json('/api/admin', post({ action })),
    auth: () => json('/api/auth', { headers: authHeader(token.get()) }),
    token,
  };
}

// ─── Browser ↔ station clock estimate ────────────────────────────────────────

export interface PingSample {
  rttMs: number;      // round trip minus server hold time
  offsetMs: number;   // station clock minus browser clock
  at: number;         // browser epoch ms of the response
}

/**
 * One NTP-style four-timestamp exchange against /api/ping.
 * offset = ((t2 − t1) + (t3 − t4)) / 2, delay = (t4 − t1) − (t3 − t2).
 * The estimate assumes a symmetric path; browser timer resolution and
 * asymmetric routes limit it to roughly the millisecond level (inferred, not observed).
 */
export async function pingOnce(api: StationApi): Promise<PingSample> {
  const t1 = Date.now();
  const p = await api.ping();
  const t4 = Date.now();
  const t2 = p.server_receive_epoch_ms;
  const t3 = p.server_send_epoch_ms;
  return { rttMs: (t4 - t1) - (t3 - t2), offsetMs: ((t2 - t1) + (t3 - t4)) / 2, at: t4 };
}
