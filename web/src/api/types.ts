// Types for the GPS Time station HTTP API (gps_time_pi/server.py).
// Reference: docs/api/README.md. These mirror what the server sends today;
// fields the server can omit or null are typed that way on purpose, so the UI
// has to handle UNKNOWN instead of assuming a value.

export type Provenance = 'observed' | 'calculated' | 'modeled' | 'predicted' | 'inferred' | 'external';

/** A labeled measurement as emitted by gps_time_pi/labels.py. */
export interface Measured<T = number> {
  value: T | null;
  unit: string | null;
  provenance: Provenance;
  note?: string;
}

// ─── GET /api ────────────────────────────────────────────────────────────────

export interface ChronyQuality {
  system_time_s: number | null;
  last_offset_s: number | null;
  rms_offset_s: number | null;
  root_delay_s: number | null;
  root_dispersion_s: number | null;
  frequency: string | null;          // chrony text, e.g. "2.117 ppm fast"
  frequency_ppm?: number | null;     // only present in demo payloads today
  residual_freq: string | null;
  skew: string | null;
  update_interval: string | null;
  leap: string | null;
  stratum: string | null;
  reference: string | null;
  ref_time: string | null;
}

export interface ChronySource {
  mode: string;
  state: string;
  state_label: string;
  name: string;
  stratum: number;
  poll: number;
  reach: string;
  lastrx: string;
  sample: string;
}

export interface NtpClient {
  host: string;
  ntp_packets: number;
  dropped: string;
  last: string;
}

export interface Satellite {
  id: number | string;
  gnss: string;
  el: number | null;
  az: number | null;
  snr: number | null;   // C/N0, dB-Hz
  used: boolean;
}

export interface GpsSummary {
  fix: string | null;
  sats: Satellite[];
  used: number | null;
  visible: number | null;
  tdop: number | null;
  hdop: number | null;
  last_fix: string | null;
  last_fix_time: string | null;
  stale: boolean;
  data_age_s: number | null;
  sky_stale: boolean;
  sky_age_s: number | null;
}

export type LocationMode = 'exact' | 'rounded' | 'hidden';

/** Already filtered by the server's location privacy mode. Never re-derive more precision. */
export interface DisplayedLocation {
  mode: LocationMode;
  lat: number | null;
  lon: number | null;
  alt_msl?: number | null;
  alt_hae?: number | null;
}

export interface SurveyStats {
  n: number;
  n_fresh?: number;
  n_legacy?: number;
  ingest_rule?: string | null;
  se_horiz_m?: number;
  se_alt_m?: number;
  sd_lat_m?: number;
  sd_lon_m?: number;
  sd_alt_m?: number;
  updated?: string;
}

export interface TimingStatus {
  code: string;            // GPS_PPS, GPS_NMEA_ONLY, NETWORK, HOLDOVER, DEGRADED, UNSYNCHRONIZED, ACQUIRING, UNKNOWN, ...
  headline: string;
  banner: string;
  detail: string;
  source: { name: string; kind: string; stratum: string | number } | null;
  gnss_healthy: boolean | null;
  provenance: Provenance;
}

export interface CoreStatus {
  demo?: boolean;                          // present (true) only in server demo mode
  epoch_ms: number;
  utc: string;
  state: [string, string];                 // [headline, banner — detail]
  timing_status?: TimingStatus;            // live mode only
  quality: ChronyQuality;
  fmt: { system_pair: string; rms: string; root_dispersion: string; root_delay: string };
  sources: ChronySource[];
  sourcestats: string;
  clients: NtpClient[] | null;          // null: chronyc clients failed or was refused (UNKNOWN)
  gps: GpsSummary;
  location: DisplayedLocation;
  survey: SurveyStats;
  position_provenance: 'live' | 'stored' | 'none' | 'demo';
  sidereal: string | null;
  astro_available: boolean;
  cpu_temp_c: number | null;
  versions: {
    app: string;
    chrony: string | null;
    gpsd: string | null;
    receiver: { driver?: string; firmware?: string; path?: string } | null;
    python: string;
  };
}

// ─── GET /api/timing-chain ───────────────────────────────────────────────────

export type StageStatus = 'OK' | 'DEGRADED' | 'FAILED' | 'UNKNOWN' | 'NOT_OBSERVABLE' | 'NOT_APPLICABLE' | 'INFO';

export interface TimingStage {
  id: string;
  label: string;
  status: StageStatus;
  summary: string;
  evidence: Record<string, unknown>;
}

export interface EventSnapshot {
  pps_state: string | null;
  pulse_health: string | null;
  gnss_healthy: boolean | null;
  satellites_used: number | null;
  best_cn0: number | null;
  chrony_pps_status: string | null;
  nmea_status: string | null;
  selected_source: string | null;
  status_code: string | null;
}

export interface TimingEvent {
  schema: 'gps-time.event/1';
  id: string;
  type: string;                      // PPS_OUTAGE, ...
  start_epoch: number;
  start_utc: string;
  end_utc: string | null;
  duration_s: number | null;
  open: boolean;
  severity: string;
  classification: string | null;
  initial_classification?: string | null;
  confidence: string | null;
  boundary: string | null;
  classification_provenance: Provenance;
  evidence: {
    at_start?: EventSnapshot;
    latest?: EventSnapshot;
    satellites_used_range?: [number, number] | null;
    fallback_sources?: string[];
    max_abs_system_time_s?: number | null;
    gnss_unhealthy_seen?: boolean;
    [k: string]: unknown;
  };
  recovery: EventRecovery | null;
  notes: string[];
  start_bound?: string;
}

export interface EventRecovery {
  recovered_utc: string;
  duration_s: Measured;
  time_to_accept_s: Measured;
  time_to_select_s: Measured;
  fallback_sources: string[];
  max_abs_system_time_s: Measured;
  end_bounds_utc?: [string | null, string];
  note?: string;
}

export interface ChronyRefclock {
  name: string;
  mode: string;
  state_symbol: Measured<string>;
  state_meaning: string;
  reach: Measured<string>;
  reach_successes_of_8: Measured;
  last_rx_s: Measured;
  poll_log2_s: number;
  offset_s: Measured;
  error_bound_s: Measured;
  frequency_ppm: Measured;
  skew_ppm: Measured;
  std_dev_s: Measured;
}

export interface TimingChain {
  schema: 'gps-time.timing-chain/1';
  generated_utc: string;
  status: TimingStatus;
  pps_state: Measured<string>;
  pps: {
    device: Measured<string>;
    device_present: Measured<boolean>;
    pulse_health: string;
    pulse_health_provenance: Provenance;
    measurement_layer: string;
    note: string | null;
    metadata?: { name: string | null; path: string | null };
    thresholds_s?: { degraded_after: number; lost_after: number };
    last_event_utc?: Measured<string>;
    last_sequence?: Measured;
    age_s?: Measured;
    last_interval_s?: Measured;
    rate_hz?: Measured;
    missed_pulses?: Measured;
    consecutive_pulses?: Measured;
    sequence_resets?: number;
    interval_stats?: Measured<{ count: number; mean: number; min: number; max: number; stdev: number | null }> | null;
    boot_config?: { gpio: number | null; assert_edge: string | null; source: string };
    [k: string]: unknown;
  };
  gnss: {
    receiver_comms: string;
    satellite_reception: string;
    nav_time_solution: string;
    healthy: boolean | null;
    fix?: Measured<string>;
    satellites_visible?: Measured;
    satellites_used?: Measured;
    best_cn0?: Measured;
    median_cn0_used?: Measured;
    tdop?: Measured;
    data_age_s?: Measured;
  };
  chrony: {
    available: { tracking: boolean; sources: boolean; sourcestats: boolean };
    refclocks: { pps: string | null; nmea: string | null; identified_from: string; pps_lock?: string | null };
    pps_status: string;
    nmea_status: string;
    pps: ChronyRefclock | null;
    nmea: ChronyRefclock | null;
    selected: { name: string; kind: string; stratum: number; is_pps: boolean; is_nmea: boolean } | null;
    any_selected: boolean;
    tracking: {
      leap: string | null;
      stratum: string | null;
      reference: string | null;
      system_time_s: Measured;
      root_delay_s: Measured;
      root_dispersion_s: Measured;
      frequency: string | null;
    } | null;
  };
  classification: { classification: string; confidence: string; boundary: string; notes: string[] } | null;
  stages: TimingStage[];
  events: { open: TimingEvent | null; recent: TimingEvent[] };
  boot: {
    phase: string;
    boot_utc: string | null;
    since_boot_s: Measured;
    pps_selected_this_boot: boolean;
    [k: string]: unknown;
  };
  raw: { tracking: string; sources: string; sourcestats: string };
  demo?: { scenario: string; description: string; scenarios: string[]; note: string };
}

// ─── GET /api/history ────────────────────────────────────────────────────────

export interface HistoryPoint { t: number; offset_s: number; err_s: number | null }  // t: Unix seconds
export type History =
  | { available: true; points: HistoryPoint[]; note: string | null }
  | { available: false; points: HistoryPoint[]; note: string };

// ─── GET /api/survey ─────────────────────────────────────────────────────────

export interface Survey {
  available: boolean;
  history: [epoch_s: number, n: number, se_horiz_m: number | null, se_alt_m: number | null][];
  fixes: [number, number][];   // [north_m, east_m] around the mean; no absolute position
  stats: SurveyStats;
  ingest: {
    accepted_this_session: number;
    rejected_this_session: Record<string, number>;
    last_reason: string | null;
    collector_running: boolean;
  };
  persistence: {
    loaded_from: string;
    corrupt_moved_to: string | null;
    last_write_utc: string | null;
    last_write_error: string | null;
  };
  note: string | null;
}

// ─── GET /api/system ─────────────────────────────────────────────────────────

export interface SystemDiagnostics {
  model: string | null;
  kernel: string | null;
  uptime_s: number | null;
  load: [number, number, number] | null;
  mem: { total_mb: number; available_mb: number; used_pct: number } | null;
  disk: { total_gb: number; free_gb: number; used_pct: number } | null;
  cpu_mhz: number | null;
  core_volts: string | null;     // vcgencmd text, e.g. "0.8563V"
  throttled: {
    raw: string;
    flags: { label: string; active: boolean; now: boolean }[];   // now=false: "since boot" bit
    any_now: boolean;
    any_ever: boolean;
  } | null;
  power: { volts: number; amps: number; watts: number } | null;  // Pi 5 PMIC only
  power_note: string | null;
  ramlog: { path: string; in_ram: boolean; size_kb: number | null; flushed_age_s: number | null } | null;
}

// ─── GET /api/almanac ────────────────────────────────────────────────────────

export type Unavailable = { available: false; reason: string; location_display?: LocationMode };

export interface SolarDay {
  available: true;
  date: string;
  tz: string;
  events: Record<string, string | null>;   // sunrise, sunset, civil/nautical/astro dawn & dusk (ISO with offset)
  noon: string | null;
  daylight_s: number | null;
  bar: unknown[];
  notes: string[];
}

export interface LunarDay {
  available: true;
  rise: string | null;
  set: string | null;
  transit?: string | null;
  transit_alt?: number | null;
  phase: string;
  illum: number;             // percent
  age_days?: number;
  up_s?: number;
}

export interface Almanac {
  available: true;
  demo?: boolean;
  sun: SolarDay | Unavailable;
  moon: LunarDay | Unavailable;
  night: { available: boolean; defined?: boolean; [k: string]: unknown };
  delta_yesterday: number | null;
  delta_tomorrow: number | null;
  neighbors: Record<'yesterday' | 'tomorrow', { sunrise?: string | null; sunset?: string | null; daylight_s?: number | null }>;
  sky: Record<string, unknown>;
  sky_when: string;
  position_provenance: string;
  position_age: string | null;
  location_display?: LocationMode;   // the privacy mode the values were computed under
}

export interface AlmanacQuery { date?: string; tz?: string; at?: string }

// ─── GET /api/ping ───────────────────────────────────────────────────────────

export interface Ping { server_receive_epoch_ms: number; server_send_epoch_ms: number }

// ─── GET/POST /api/dashboard ─────────────────────────────────────────────────

export interface DashboardWidget { id: string; visible: boolean; size: 'normal' | 'wide' }
export interface DashboardLayout {
  schema_version: number;
  title: string;
  pages: { id: string; title: string; widgets: DashboardWidget[] }[];
}
export interface DashboardConfig extends DashboardLayout {
  _meta: { writable: boolean; auth_required: boolean; demo: boolean; path: string | null; known_widgets: string[] };
}
export type DashboardWriteResult = { ok: true; dashboard: DashboardLayout } | { ok: false; error: string };

// ─── GET /api/setting ────────────────────────────────────────────────────────

export type SettingResult =
  | { ok: true; location_display: LocationMode }
  | { ok: true; reset_site: true }
  | { ok: false };

// ─── GET /api/admin ──────────────────────────────────────────────────────────

export type AdminAction = 'flush_logs' | 'restart_gpsd' | 'restart_chrony' | 'restart_web' | 'reboot';
export interface AdminResult { ok: boolean; action: string; detail: string; simulated?: true }

// ─── GET /api/auth ───────────────────────────────────────────────────────────

export interface AuthState {
  demo: boolean;
  auth_required: boolean;     // false only in demo mode
  admin_configured: boolean;  // a token hash exists on the station
  authenticated: boolean;     // the Authorization header sent was valid (always true in demo)
}
