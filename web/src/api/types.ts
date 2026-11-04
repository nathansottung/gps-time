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
  /** |System time| + root dispersion + ½ root delay: chronyc's bound, if the reference is right (GPS-007). */
  max_error_bound_s: number | null;
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
  is_self?: boolean;   // the source is this station's own address: not an external reference
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
  timing_status?: TimingStatus;            // live mode only
  quality: ChronyQuality;
  sources: ChronySource[];
  sourcestats: string;
  clients: NtpClient[] | null;          // null: chronyc clients failed or was refused (UNKNOWN)
  gps: GpsSummary;
  location: DisplayedLocation;
  survey: SurveyStats;
  position_provenance: 'live' | 'stored' | 'none' | 'demo';
  sidereal: string | null;
  timezone?: DisplayZone;         // local-time display zone; absent on stations before this field
  astro_available: boolean;
  astro_reason?: string | null;   // why astronomy is unavailable; null when available
  cpu_temp_c: number | null;
  versions: {
    app: string;
    chrony: string | null;
    gpsd: string | null;
    receiver: { driver?: string; firmware?: string; path?: string } | null;
    python: string;
  };
}

/** /api → timezone. Display only; every timestamp in the API is UTC. */
export interface DisplayZone {
  tz: string | null;                          // IANA name; null = use the browser's zone
  source: 'override' | 'position' | null;     // operator setting | found from the station's position
  provenance: 'calculated' | null;            // set for 'position'
  basis: 'exact' | 'rounded' | null;          // which position the lookup used (never in hidden mode)
  note: string;
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
  network_ntp?: Measured<boolean>;   // chrony selected a network NTP source during the outage (observed)
  network_ntp_sources?: string[];
  holdover_check?: { measured_error_s: Measured; eligible: boolean; flags: string[] };
  max_abs_system_time_s: Measured;
  end_bounds_utc?: [string | null, string];
  note?: string;
}

/** A measured recommendation for the NMEA refclock's `offset` in chrony.conf. The station never changes chrony. */
export interface NmeaCalibration {
  available: boolean;
  reason: string | null;
  configured_offset_s?: Measured;
  residual_s?: Measured;          // chronyc sourcestats Offset for NMEA while PPS is selected
  std_dev_s?: Measured;
  samples?: Measured;
  span_s?: Measured;
  suggested_offset_s?: Measured;  // configured + residual
  change_worthwhile?: boolean;
  advice?: string;
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
    missed_pulses?: Measured;       // pulses the kernel never counted (from its sequence number)
    unread_pulses?: Measured;       // pulses the kernel counted that no poll read on its own; not lost
    poller?: { polls: number; late_polls: number; max_poll_gap_s: number | null; late_after_s: number; note: string };
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
    selected: { name: string; kind: string; stratum: number; is_pps: boolean; is_nmea: boolean; is_self?: boolean } | null;
    self_sources?: string[];   // chrony sources that are this station's own address
    any_selected: boolean;
    nmea_calibration?: NmeaCalibration;
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

/** One chrony tracking.log record, by column name (chrony 4.x; review GPS-003). t: Unix seconds. */
export interface HistoryPoint {
  t: number;
  offset_s: number;                  // "Offset"
  offset_sd_s?: number | null;       // "Offset sd": chrony's standard deviation of the offset
  remaining_correction_s?: number | null;   // "Rem. corr."
  root_delay_s?: number | null;
  root_dispersion_s?: number | null;
  max_error_s?: number | null;       // "Max. error": a bound, conditional on the reference
  freq_ppm?: number | null;
  skew_ppm?: number | null;
  leap?: string;
  n_combined?: number;               // "Co": how many sources were combined (a count)
  stratum?: number;
  source?: string;
}
export type History =
  | { available: true; points: HistoryPoint[]; note: string | null; skipped_lines?: number; columns?: string[] }
  | { available: false; points: HistoryPoint[]; note: string };

// ─── GET /api/stability ──────────────────────────────────────────────────────

export interface StabilityPoint {
  tau_s: number;
  series: 'seconds' | 'minutes';     // which stored series the value comes from
  adev: number;                      // overlapping Allan deviation, dimensionless
  adev_terms: number;
  adev_low: number | null;           // confidence interval; null when the noise type could not be identified
  adev_high: number | null;
  edf: number | null;
  noise: string | null;              // identified power-law noise type (inferred)
  noise_assumed: boolean;            // too few points at this tau: the type from a shorter tau was kept
  mdev: number | null;               // modified Allan deviation; null when the data is too short
  mdev_terms: number;
  tdev_s: number | null;             // time deviation, seconds
}
export interface StabilitySeries {
  tau0_s: number;
  samples: number;
  gaps: number;
  span_s: number;
  capacity_s: number;
  pps_selected_fraction: number | null;   // share of samples taken while chrony had PPS selected
}
export interface Stability {
  available: boolean;
  reason: string | null;
  provenance: Provenance;
  measurement_layer: string;
  method: string;
  confidence: { level: number; applies_to: string; method: string; noise_provenance: Provenance };
  storage: string;
  since_utc: string | null;
  history_resets: number;
  series: { seconds: StabilitySeries; minutes: StabilitySeries };
  points: StabilityPoint[];
  key_points: { tau_s: number; label: string; point: StabilityPoint | null; reason: string | null }[];
  notes: string[];
}

// ─── GET /api/shadow ─────────────────────────────────────────────────────────

export type ShadowState = 'SUNLIT' | 'PENUMBRA' | 'UMBRA';
export interface ShadowMap {
  shell_km: number;
  alt_step_deg: number;
  az_step_deg: number;
  alts_deg: number[];
  azs_deg: number[];
  rows: string[];                  // one string per altitude ring; one of S, P, U per azimuth step
}
export interface ShadowShell {
  altitude_km: number;
  zenith: ShadowState;
  sunlit_sky_fraction: number;     // of the sky above 10°, by solid angle
  sunlit_max_altitude_deg: number | null;
  sunlit_sectors: string[];
  summary: string;
}
export interface ShadowReport {
  available: true;
  reason: null;
  provenance: Provenance;          // modeled
  model: string;
  meaning: string;
  as_of_utc: string;
  location_display?: LocationMode;
  sun: { altitude_deg: number; azimuth_deg: number; depression_deg: number; distance_au: number;
         antisolar: { azimuth_deg: number; altitude_deg: number }; note: string };
  darkness: { stage: string; astronomical_darkness: boolean };
  cone: { umbra_half_angle_deg: number; penumbra_half_angle_deg: number; umbra_length_km: number; axis: string };
  zenith: { umbra_top_km: number | null; penumbra_top_km: number | null; ground_state: ShadowState;
            beyond_limit: boolean; search_limit_km: number; note: string };
  shells: ShadowShell[];
  map: ShadowMap;
  query: { azimuth_deg: number; altitude_deg: number; shell_km: number; state: ShadowState;
           sunlit_fraction: number; range_km: number; note: string } | null;
  messages: string[];
}
export type Shadow = ShadowReport | Unavailable;

// ─── GET /api/satellites ─────────────────────────────────────────────────────

export interface SatelliteNow {
  norad: number;
  name?: string;
  group?: string | null;
  epoch_utc?: string;              // epoch of the orbital elements
  age_days?: number;
  stale?: boolean;
  age_note?: string | null;
  available: boolean;
  reason: string | null;
  provenance?: Provenance;         // modeled
  azimuth_deg?: number;
  altitude_deg?: number;
  above_horizon?: boolean;
  range_km?: number;
  height_km?: number;
  angular_speed_deg_s?: number | null;
  state?: ShadowState;
  sunlit_fraction?: number;
  could_be_seen?: boolean;
}
export interface PassPoint { utc: string; azimuth_deg: number; altitude_deg: number; range_km: number; state: ShadowState }
export interface SatellitePass {
  rise: PassPoint | null;          // null: the pass was already under way
  culmination: PassPoint;
  set: PassPoint | null;
  in_progress: boolean;
  duration_s: number;
  shadow_changes: { utc: string; kind: string; from: ShadowState; to: ShadowState; azimuth_deg: number; altitude_deg: number }[];
  visible: { start_utc: string; end_utc: string; duration_s: number; max_altitude_deg: number; max_azimuth_deg: number } | null;
  sun_altitude_deg: number;
  provenance: Provenance;          // predicted
}
export interface TleGroup {
  group: string; file: string; count: number; rejected: number;
  source: string | null; fetched_utc: string | null;
  newest_epoch_utc: string | null; oldest_epoch_utc: string | null;
}
export interface SatelliteReport {
  available: boolean;
  reason: string | null;
  provenance: Provenance;          // external: the orbital elements
  meaning: string;
  as_of_utc: string;
  location_display?: LocationMode;
  cache: { dir: string; satellites: number; groups: TleGroup[]; newest_epoch_utc: string | null;
           newest_age_days: number | null; oldest_age_days: number | null; stale_after_days: number;
           problems: string[]; provenance: Provenance } | null;
  featured: SatelliteNow[];
  satellite: SatelliteNow | null;
  passes: SatellitePass[];
  matches: SatelliteNow[];
  window_hours?: number;
  demo?: { note: string };
}
export type Satellites = SatelliteReport | Unavailable;

// ─── GET /api/evidence ───────────────────────────────────────────────────────

export interface EvidenceFile {
  id: string;
  phase: 'open' | 'closed';
  written_utc: string;
  start_utc: string | null;
  end_utc: string | null;
  duration_s: number | null;
  classification: string | null;
  bytes: number;
  tracking_lines: number;
  timeline_points: number;
}
export interface EvidenceIndex {
  available: boolean;
  dir: string;
  files: EvidenceFile[];
  total_bytes: number;
  max_bytes: number;
  max_files: number;
  removed_for_space: number;
  problems: string[];
  note: string;
}

// ─── GET /api/oscillator ─────────────────────────────────────────────────────

export interface OscillatorBin {
  t: string;                         // bin start, UTC (10 minutes)
  samples: number;
  pps_samples: number;               // samples taken while chrony had PPS selected
  temp_mean_c: number | null; temp_min_c: number | null; temp_max_c: number | null;
  freq_mean_ppm: number | null; freq_min_ppm: number | null; freq_max_ppm: number | null;   // + = fast
  skew_mean_ppm: number | null;
  residual_mean_ppm: number | null;
}
export interface OscillatorFit {
  bins_used: number;
  slope_ppm_per_c: number | null;
  intercept_ppm: number | null;
  r: number | null;
  temp_span_c: number | null;
  reason: string | null;
  provenance: Provenance;            // calculated
}
/** The oscillator profile fitted over the whole log (gps_time_pi/oscprofile.py). Modeled. */
export interface OscillatorProfileTerm { name: 'a' | 'b' | 'c' | 'd'; value: number; se: number; unit: string }
export interface OscillatorProfile {
  status: 'fitted' | 'insufficient';
  reason: string | null;
  provenance: Provenance;            // modeled
  model: 'linear' | 'quadratic' | 'linear+aging' | 'quadratic+aging' | null;
  terms: OscillatorProfileTerm[];    // a: ppm at temp_ref_c and t0; b: ppm/°C; c: ppm/°C²; d: ppm/day
  bins_used: number;
  outliers: number;
  residual_rms_ppm: number | null;
  r2: number | null;
  temp_ref_c: number | null;
  t0_utc: string | null;
  t0_utc_epoch: number | null;
  covers: { temp_min_c: number; temp_max_c: number; first_utc: string; last_utc: string; first_utc_epoch: number; last_utc_epoch: number; days: number } | null;
  candidates: { model: string; bic: number }[];
  note: string;
}
/** Holdover projections (gps_time_pi/oscprofile.py holdover; GPS-008). All modeled; checked against outages by the scorecard. */
export interface HoldoverProjection {
  name: 'free_running' | 'trained_skew' | 'profile' | 'scored';
  provenance: Provenance;            // modeled
  available: boolean;
  reason?: string;                   // when not available
  rate_ppm: number | null;           // the constant error rate assumed
  aging_ppm_per_day: number;         // a frequency ramp on top (profile only)
  times_s: (number | null)[];        // one per threshold; null: never reached under the model
  basis?: string;
  components_ppm?: { skew: number; residual_rms: number; temperature: number };
  temp_now_c?: number;
  temp_assumed_c?: [number, number];
  temp_source?: string;
  extrapolated?: boolean;
  caveat?: string | null;
  validated?: HoldoverModelRecord | null;   // how this model did against measured outages
  factor?: number;                   // scored: the rate multiplier (worst measured/predicted, ≥ 1)
  from?: string;                     // scored: the projection it scales
  outages?: number;                  // scored: outages behind the factor
}
/** One model's record over the scored outages (calculated). */
export interface HoldoverModelRecord { name: string; n: number; held: number; median_ratio: number; worst_ratio: number; provenance: Provenance }
/** One outage: predicted (modeled, at its start) against measured (observed, first good PPS after recovery). */
export interface HoldoverCheckEntry {
  event_id: string;
  start_utc: string;
  end_utc: string | null;
  measured_utc: string;
  measured_at: 'recovery' | 'reselected';
  time_since_start_s: Measured;
  measured_error_s: Measured;
  prediction_sample_utc: string | null;
  predictions: { name: string; rate_ppm: number; predicted_error_s: Measured; ratio: Measured; held: boolean | null }[];
  network_ntp: boolean;
  network_ntp_sources: string[];
  flags: string[];
  eligible: boolean;
  not_scored_because: string[] | null;
}
/** The running scorecard (gps_time_pi/holdover_check.py). */
export interface HoldoverScorecard {
  provenance: Provenance;            // calculated
  entries: number;
  eligible: number;
  network_ntp: number;
  score_min: number;
  models: HoldoverModelRecord[];
  recent: HoldoverCheckEntry[];
  note: string;
  problems: string[];
}
export interface OscillatorHoldover {
  provenance: Provenance;            // modeled
  thresholds_s: number[];
  projections: HoldoverProjection[];
  sample_utc: string | null;
  note: string;
  scorecard?: HoldoverScorecard;
}
export type ProfileBinding = 'match' | 'mismatch' | 'unverifiable';
export interface ProfileFileMeta {
  binding: ProfileBinding;
  file: string;
  bins: number;
  exported_utc: string | null;
  board: { serial_sha256: string | null; model: string | null };
  receiver: { driver: string | null; firmware: string | null } | null;
  software_version: string | null;
}
export interface OscillatorProfileFiles {
  imported: ProfileFileMeta | null;                                      // this board's file, in use
  reference: (ProfileFileMeta & { warning: string; profile: OscillatorProfile }) | null;   // reference only
  note: string;
}
/** GET /api/oscillator/profile: the export file. */
export interface OscillatorProfileExport {
  format: 'gps-time-oscillator-profile/1';
  exported_utc: string;
  board: { serial_sha256: string | null; model: string | null };
  receiver: { driver: string | null; firmware: string | null } | null;
  software_version: string | null;
  profile: OscillatorProfile;
  fit_bins: { columns: string[]; rows: [number, number, number][]; note: string };
  note: string;
}
/** POST /api/oscillator/profile. */
export type ProfileImportResult =
  | { ok: true; binding: ProfileBinding; bins: number; used: boolean; detail: string; simulated?: boolean }
  | { ok: false; error: string };

export interface Oscillator {
  available: boolean;
  reason: string | null;
  provenance: Provenance;            // observed
  sensor: string;
  frequency_note: string;
  bin_s: number;
  sample_interval_s: number;
  bins: OscillatorBin[];
  latest: { temp_c: Measured; freq_ppm: Measured; bin_start_utc: string } | null;
  fit: OscillatorFit;
  fit_note: string;
  profile: OscillatorProfile;
  holdover: OscillatorHoldover;
  profile_files: OscillatorProfileFiles;
  storage: { path: string; bytes: number; max_bytes: number; pending_bins: number; flush_interval_s: number; note: string };
  board: { serial_sha256: string | null; model: string | null };
  problems: string[];
}

// ─── GET /api/ntp-service ────────────────────────────────────────────────────

export interface NtpRate { received_per_s: Measured; dropped_per_s: Measured }
export interface NtpService {
  available: boolean;
  reason: string | null;
  provenance: Provenance;                       // observed: chrony's own counters
  state: 'SERVING' | 'SERVING_WITH_DROPS' | 'NO_REQUESTS' | 'UNKNOWN';
  state_basis?: string;
  state_provenance?: Provenance;
  as_of_utc: string | null;
  counters: Record<string, number> | null;      // every counter read from chronyc serverstats
  ntp: { received: Measured; dropped: Measured; not_dropped: Measured; drop_fraction: Measured } | null;
  rates: { last_minute: NtpRate; last_hour: NtpRate } | null;
  history: { t: number; received_per_min: number; dropped_per_min: number }[];
  history_info?: { interval_s: number; max_points: number; storage: string };
  counter_resets: number;                       // times chronyd restarted while the station was watching
  note?: string;
}

// ─── GET /api/references ─────────────────────────────────────────────────────

export interface ReferencePoint { t: number; offset_s: number; error_bound_s: number | null; delay_s: number | null }
export interface ReferenceServer {
  name: string;
  state: string;
  state_label: string;
  stratum: number;
  poll_s: number;
  reach: string;
  reachable: boolean;
  usable: boolean;                       // reachable, with a recent measurement
  lastrx_s: number | null;
  offset_s: number | null;               // + = the station's clock is ahead of the server; null unless usable
  error_bound_s: number | null;
  delay_s: number | null;                // null = UNKNOWN (no ntpdata from the helper)
  root_delay_s: number | null;
  assessment: 'agrees' | 'disagrees' | 'inconclusive' | 'not usable';
  provenance: Provenance;                // external
  history: ReferencePoint[];            // only for the server asked for (?history=), else the first with history
  history_points: number;
}
export interface ReferenceVerdict {
  code: 'AGREE' | 'DISAGREE' | 'ONE_REFERENCE' | 'NONE_REACHABLE' | 'NONE_CONFIGURED' | 'UNKNOWN';
  headline: string;
  detail: string;
  provenance: Provenance;                // calculated
  threshold_s: number;
  configured?: number;
  usable?: number;
  agreeing?: number;
  disagreeing?: number;
  inconclusive?: number;
}
export interface References {
  available: boolean;
  provenance: Provenance;
  as_of_utc: string | null;
  verdict: ReferenceVerdict;
  references: ReferenceServer[];
  excluded: { name: string; why: string }[];   // the station itself, and servers steering the clock
  delay_available: boolean;
  delay_note: string | null;
  sign: string;
  history: { interval_s: number; max_points: number; storage: string };
  demo?: { scenario: string; scenarios: string[]; note: string };
}

// ─── GET /api/timescales ─────────────────────────────────────────────────────

export interface LeapSeconds {
  provenance: Provenance;                    // external: IERS data as packaged by the OS
  source: 'file' | 'builtin';
  source_label: string;
  path: string | null;
  updated_utc: string | null;
  expires_utc: string | null;
  days_to_expiry: number | null;
  status: 'OK' | 'EXPIRES_SOON' | 'EXPIRED' | 'UNKNOWN';
  warning: string | null;
  warn_days: number;
  last: { utc: string; tai_utc_s: number } | null;
  next: { utc: string; tai_utc_s: number; kind: 'insert' | 'delete' | null; last_second_utc: string } | null;
  next_note: string | null;
  chrony_leap_status: Measured<string>;
  problems: string[];
}
export interface Ut1 {
  available: boolean;
  provenance: Provenance;
  path: string;
  ut1_utc_s: number | null;
  kind: string | null;
  file_date_utc: string | null;
  reason: string | null;
  note?: string;
}
export interface TimeScales {
  provenance: Provenance;
  utc: string;
  unix_s: number;
  tai_utc_s: Measured<number>;               // null value = before the table starts
  gps_utc_s: Measured<number>;
  tai: Measured<string> | null;
  gps: { time: Measured<string>; week: Measured<number>; week_mod_1024: Measured<number>; seconds_of_week: Measured<number> } | null;
  mjd: Measured<number>;
  jd: Measured<number>;
  leap_seconds: LeapSeconds;
  ut1: Ut1;
}

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
  bar: SunBarSegment[];
  notes: string[];
}

/** One stretch of the local day in one sky state (astro.solar_day). frac = share of the 24 h day. */
export interface SunBarSegment {
  state: number;   // 0 night, 1 astronomical, 2 nautical, 3 civil twilight, 4 day
  start: string;   // ISO, local offset
  frac: number;
}

/** Sunset to next sunrise (astro.night). Fractions are of the elapsed night (DST-safe). */
export type NightBar =
  | { available: true; defined: false; note?: string }
  | {
      available: true; defined: true;
      sunset: string; sunrise: string; span_s: number;
      sun_segments: { stage: number; f0: number; f1: number }[];   // 0 dark (sun < −18°), 1 astro, 2 nautical, 3 civil
      moon_up: { f0: number; f1: number }[];
      dark: { f0: number; f1: number; start: string; end: string }[];   // moonless astronomical darkness
      dark_total_s: number;
      midnight: { f: number; label: string } | null;
      astro_note: string | null;
      tz: string;
    }
  | Unavailable;

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
  night: NightBar;
  delta_yesterday: number | null;
  delta_tomorrow: number | null;
  neighbors: Record<'yesterday' | 'tomorrow', { sunrise?: string | null; sunset?: string | null; noon?: string | null; daylight_s?: number | null }>;
  sky: SkySnapshot | Unavailable | Record<string, never>;
  sky_when: string;
  position_provenance: string;
  position_age: string | null;
  location_display?: LocationMode;   // the privacy mode the values were computed under
}

export interface AlmanacQuery { date?: string; tz?: string; at?: string; /** /api/object's q, marked on the sky map */ target?: string }

/** astro.sky_snapshot: [alt°, az°] pairs; stars carry their magnitude. Only what is above −1°. */
export interface SkySnapshot {
  available: true;
  demo?: boolean;
  stars: [number, number, number][];
  lines: [number, number][][];
  bodies: Record<string, [number, number]>;
  target: [number, number] | null;
}

// ─── GET /api/object ─────────────────────────────────────────────────────────

export interface ObjectWindow { start: string; end: string; dur_s: number }
export interface ObjectReport {
  available: true;
  demo?: boolean;
  name: string;
  meta: string;
  emphasis: 'dark' | 'moonless' | 'both';
  at_label: string;
  now_alt: number;
  now_az: number;
  rise: string | null;
  transit: string | null;
  transit_alt: number | null;
  set: string | null;
  circumpolar: boolean;
  never_up: boolean;
  dark_windows: ObjectWindow[];
  moonless_windows: ObjectWindow[];
  min_alt_deg: number;
  tz: string;
  location_display?: LocationMode;
}
export type ObjectResult = ObjectReport | Unavailable | { error: 'unparsed' };

// ─── GET /api/ping ───────────────────────────────────────────────────────────

export interface Ping { server_receive_epoch_ms: number; server_send_epoch_ms: number }

// ─── GET /api/setting ────────────────────────────────────────────────────────

export type SettingResult =
  | { ok: true; location_display: LocationMode }
  | { ok: true; timezone: string | null }
  | { ok: true; reset_site: true }
  | { ok: true; modules_experimental: boolean; modules_enabled: string[] }
  | { ok: true; module: string; enabled: boolean; modules_enabled: string[] }
  | { ok: true; module: string; config: Record<string, unknown> }
  | { ok: true; sky_quality_share: boolean }
  | { ok: true; clip: ClipRequest & { id: string } }
  | { ok: true; deleted: string }
  | { ok: true; simulated: true; detail?: string }
  | { ok: true; feeder: string; enabled: boolean; detail?: string; simulated?: boolean }
  | { ok: true; feeder: string; mlat: boolean; restarted?: string | null; simulated?: boolean }
  | { ok: false };

// ─── GET /api/modules ────────────────────────────────────────────────────────
// Installed modules from their manifests (code is never imported by the web service),
// the experimental switch and each module's setting. Changed with POST /api/setting.

export type ModuleMaturity = 'experimental' | 'supported' | 'research';

export interface ModuleRow {
  name: string;
  installed: boolean;          // false: enabled in the config but not in the modules folder
  valid: boolean;              // the manifest passed its checks
  errors: string[];
  version: string | null;
  maturity: ModuleMaturity | null;
  types: string[];
  summary: string | null;
  permissions: { network: boolean; devices: string[]; storage: string } | null;
  enabled: boolean;            // the owner turned it on
  runs: boolean;               // switch on, enabled, valid and with a source entry: the supervisor is asked to run it
  host_runs?: boolean;         // false: no source entry (an analysis); the host never runs it, its CLI does
  state: string | null;        // observed from gps-time-modules; null = UNKNOWN (not reporting)
  reason: string | null;
  latest?: ModuleLatest | null; // the newest item it emitted; null when the supervisor isn't reporting
  config?: Record<string, unknown>;              // the owner's settings (module_config); {} = the manifest's defaults
  config_schema?: Record<string, ModuleConfigField>; // what the manifest declares under [config]
  readiness?: ReadinessCheck[] | null;           // what it needs that the station can observe (SDR modules); null = none known
}

export interface ModuleConfigField { type?: string; unit?: string; default?: unknown; description?: string }

/** One readiness check: ok true/false is observed by the station; null is UNKNOWN (not observable). */
export interface ReadinessCheck { check: string; ok: boolean | null; detail: string }

/** A module's newest observation or result, as the station passes it on: labeled scalar values only,
 *  never a position (gps_time_pi/modkit/settings.py latest_item). */
export interface ModuleLatest {
  kind: 'observation' | 'result';
  time_ns: number | null;
  age_s: number | null;
  items_kept: number;          // items the supervisor keeps in RAM for this module
  values: Record<string, { value: string | number | boolean | null; unit: string | null; provenance: Provenance; note?: string }>;
  left_out: number;            // values not shown: unlabeled, not a scalar, position-like, or over the limit
}

export interface ModulesState {
  experimental: boolean;
  modules: ModuleRow[];
  supervisor: { reporting: boolean; age_s: number | null; detail: string };
  note: string;
}

// ─── GET /api/sdr ────────────────────────────────────────────────────────────
// The optional SDR stack, read only (gps_time_pi/sdr.py; docs/deploy/sdr-stack.md).

export interface SdrUnit {
  unit: string;
  what: string;
  active: Measured<string>;
  sub: string | null;
  enabled: string | null;
  restarts: Measured<number>;
  cpu_s: Measured<number>;
  cpu_avg_pct: Measured<number>;
  memory_mib: Measured<number>;
}

export interface SdrDongle {
  port: string;
  serial: string | null;
  product: string | null;
  role: string | null;          // from the installer's serials; null = no role
  speed_mbps: Measured<number>;
  dvb_driver: Measured<boolean>;
}

export interface SdrFeed {
  band: '1090' | '978';
  path: string;
  present: boolean;
  age_s: Measured<number>;
  aircraft: Measured<number>;
  fresh: boolean;
}

/** The owner's dongle limit (at most 3 RTL-SDRs by serial on a Pi 4; scripts/dongle-roles.sh). */
export interface SdrLimit {
  model: Measured<string>;
  max: number | null;           // null: no limit for this board (or its model can't be read)
  assigned: Measured<number>;   // distinct serials given a role (the web SDR's included)
  plugged: Measured<number>;    // RTL-SDRs on USB; null value when sysfs can't be read
  over: boolean;
  rule: string;
}

export interface SdrStatus {
  installed: boolean | null;    // null: systemctl couldn't be read (UNKNOWN)
  units: SdrUnit[] | null;
  dongles: SdrDongle[] | null;
  limit?: SdrLimit;             // absent on a station before v1.6.0-rc.3
  feeds: SdrFeed[];
  note: string;
}

// ─── GET /api/websdr ─────────────────────────────────────────────────────────
// The optional web SDR, OpenWebRX+ behind a password gate (gps_time_pi/websdr.py;
// docs/deploy/websdr.md), and its usage log: CPU, temperature and PPS jitter while it runs.

export interface WebSdrBin {
  t: number; active: boolean;
  cpu_pct: number | null; cpu_max_pct: number | null; websdr_cpu_pct: number | null;
  temp_c: number | null; temp_max_c: number | null;
  pps_pulses: number; pps_jitter_ns: number | null; pps_max_abs_ns: number | null;
}

export interface WebSdrSummary {
  minutes: number;
  cpu_mean_pct: Measured<number>; cpu_max_pct: Measured<number>; websdr_cpu_mean_pct: Measured<number>;
  temp_mean_c: Measured<number>; temp_max_c: Measured<number>;
  pps_jitter_median_ns: Measured<number>; pps_jitter_max_ns: Measured<number>;
  pps_max_abs_ns: Measured<number>; pps_pulses: Measured<number>;
}

export interface WebSdrSession {
  start_utc: string; partial: boolean; truncated: boolean; bins: WebSdrBin[];
  before: WebSdrSummary | null; during: WebSdrSummary | null;
}

export interface WebSdrPastSession {
  format: string; start_utc: string; end_utc: string; duration_s: number; partial: boolean; truncated: boolean;
  before: WebSdrSummary | null; during: WebSdrSummary | null;
}

export interface WebSdrStatus {
  node_host?: string | null;      // the web SDR runs on the SDR node at this address (docs/deploy/sdr-node.md)
  installed: boolean | null;      // null: systemctl couldn't be read (UNKNOWN)
  active: Measured<string>;
  port: number | null; serial: string | null; max_hours: number | null;
  /** The installer's settings (configured): the gate's login (GTP_WEBSDR_AUTH) and HF profiles (GTP_WEBSDR_HF). */
  auth?: { enabled: boolean | null; remember_days: number | null };
  hf?: 'off' | 'direct' | 'native' | null;
  usage: {
    session: WebSdrSession | null; baseline: WebSdrSummary | null; recent: WebSdrPastSession[];
    file: { name: string; error: string | null }; note: string;
  };
  note: string;
}

// ─── GET /api/feeders ────────────────────────────────────────────────────────
// Opt-in ADS-B feeders and everything that shares the station's location (gps_time_pi/feeders.py;
// docs/deploy/feeders.md). Turned on with the admin token and a typed confirmation.

export interface FeederRow {
  name: string;
  service: string;               // e.g. "adsb.fi", "FlightAware"
  unit: string;
  on: boolean;                   // the owner's switch
  active: Measured<string>;      // the unit's ActiveState (observed)
  target: string | null;         // host:port for a Beast feeder
  confirm: string;               // what must be typed to turn it on
  shares: string;                // plain words
  mlat?: { on: boolean; allowed: boolean; confirm: string; refused: string | null };
}

export interface SharingRow { what: string; to: string; location: string; active: boolean; detail: string }

export interface FeedersStatus {
  installed: boolean;
  feeders: FeederRow[];
  location_display: LocationMode | null;
  note: string;
  sharing: { rows: SharingRow[]; exact_location_shared: boolean; location_display: LocationMode | null };
}

// ─── GET /api/time-quality ───────────────────────────────────────────────────
// Where this Pi's clock gets its time (gps_time_pi/timequality.py): its reference clock, or ntp on an SDR node.
export interface TimeQuality {
  role: 'station' | 'sdr-node';
  station: string | null;         // on a node: the station it follows
  sdr_node: string | null;        // on the station: the node it reads
  source: 'refclock' | 'ntp' | 'unknown';
  reference: string | null;
  stratum: number | null;
  max_error_s: Measured<number>;
  label: string;
}

// ─── GET /api/clips ──────────────────────────────────────────────────────────
// Capped clip recording (gps_time_pi/clips.py): audio and IQ as SigMF with the station's timing.
export type ClipKind = 'iq' | 'am' | 'nfm' | 'wfm';
export interface ClipRow {
  name: string; kind: string | null; freq_hz: number | null; start_utc: string | null; seconds: number | null; bytes: number;
  time_source: string | null; time_offset_bound_s: number | null; sample_time_uncertainty_s: number | null; signed: boolean;
  files: ('sigmf-meta' | 'sigmf-data' | 'wav')[];
}
export interface ClipsStatus {
  storage: { dir: string; kind: 'ram' | 'custom'; max_mb: number; used: Measured<number>; problem: string | null };
  pending: null | { id: string; kind: ClipKind; freq_hz: number; seconds: number };
  last: null | { ok: boolean; id?: string; clip?: string; error?: string; at: number };
  clips: ClipRow[];
  kinds: ClipKind[]; iq_rates: number[]; max_seconds: number; freq_range_hz: [number, number];
  note: string;
}
export interface ClipRequest { kind: ClipKind; freq_hz: number; seconds: number; rate?: number; gain_db?: number | null }

// ─── GET /api/airband ────────────────────────────────────────────────────────
// Airband bookmarks for the web SDR (gps_time_pi/airband.py): built-ins, and the FAA NASR set with
// the cycle it came from, flagged past 28 days. Refreshed by the admin action refresh_airband.

export interface AirbandBookmark {
  name: string; frequency_hz: number; use: string | null; facility?: string | null; distance_km?: number; source: 'built-in' | 'nasr';
}

export interface AirbandStatus {
  built_in: AirbandBookmark[];
  nasr: null | {
    cycle: string; fetched_utc: string | null; radius_km: number; site_precision: string; count: number;
    age_days: Measured<number>; stale: boolean; bookmarks: AirbandBookmark[];
  };
  current_cycle: string;
  refresh_allowed: boolean;
  refresh_note: string;
  last_refresh: null | { ok: boolean; at_utc: string; error?: string; cycle?: string; count?: number };
}

// ─── GET /api/sky-obstruction ────────────────────────────────────────────────
// The learned sky-obstruction map (gps_time_pi/skymap.py): cells of 10° azimuth × 5° elevation,
// each against the rest of its elevation band. Inferred; off in hidden mode.

export type SkyCellClass = 'clear' | 'attenuated' | 'blocked' | 'unknown';
export interface SkyCell {
  az0: number; el0: number; samples: number;
  tracked_pct: number | null; used_pct: number | null;
  cn0_mean: number | null; cn0_sd: number | null; band_median: number | null; delta_db: number | null;
  class: SkyCellClass;
}
export type SkySectorState = 'clear' | 'attenuated' | 'obstructed' | 'unknown';
export interface SkySector {
  sector: string; az_centre: number; state: SkySectorState; text: string; below_deg: number | null;
  cells_classified: number; cells: number; cn0_median: number | null; provenance: 'inferred';
}
export type SkyLossClass = 'EXPECTED' | 'NOT EXPLAINED' | 'UNKNOWN' | 'SET';
export interface SkyLoss {
  utc: string; gnss: string; sat: number | null; az: number; el: number; cn0_before: number;
  class: SkyLossClass; note: string; provenance: 'inferred';
}
export interface SkyWideDrop { utc: string; satellites: number; of: number; quadrants: number; note: string; provenance: 'inferred' }
export interface SkyObstruction {
  available: true; format: string; az_step: number; el_step: number;
  summary: { days: number; satellite_minutes: number; reports_sampled: number; cells_total: number;
    cells_with_data: number; cells_classified: number; clear_pct: number | null;
    state: 'learning' | 'learned'; untracked_reported: boolean };
  sectors: SkySector[];
  cells: SkyCell[];
  losses: { counts: Record<SkyLossClass, number>; recent: SkyLoss[]; since: string };
  sky_wide: { count: number; recent: SkyWideDrop[] };
  thresholds: { min_cell_samples: number; blocked_db: number; attenuated_db: number;
    blocked_tracked: number; attenuated_tracked: number; learned_days: number };
  file: { name: string; last_write_utc: string | null; unsaved: boolean; problems: string[] };
  note: string; provenance: 'inferred';
  location_display: LocationMode;
}
export type SkyObstructionResult = SkyObstruction | { available: false; reason: string; location_display: LocationMode };

// ─── GET /api/capability ─────────────────────────────────────────────────────
// The station's capability record (gps_time_pi/capability.py). Never an exact position.
export interface SkyQuality {
  state: 'learning' | 'learned'; days: number; clear_pct: number | null; cells_classified: number;
  sectors: { sector: string; state: SkySectorState; below_deg: number | null }[];
  provenance: 'inferred'; note: string;
}
export interface Capability {
  format: string; generated_utc: string; station_id: string | null; software_version: string;
  timing: { state: string | null; source: string | null; provenance: 'calculated' };
  gnss: { driver: string | null; firmware: string | null };
  sdr: { installed: boolean | null; receivers: { role: string }[] };
  location: { precision: string; lat: number | null; lon: number | null; note?: string };
  sky_quality_opt_in: boolean;
  sky_quality: SkyQuality | null;
  sky_quality_note: string | null;
  availability: string;
}

// ─── GET /api/admin ──────────────────────────────────────────────────────────

export type AdminAction = 'flush_logs' | 'restart_gpsd' | 'restart_chrony' | 'restart_web' | 'reboot'
  | 'websdr_start' | 'websdr_stop' | 'websdr_signout_all' | 'refresh_airband';
export interface AdminResult { ok: boolean; action: string; detail: string; simulated?: true }

// ─── GET /api/auth ───────────────────────────────────────────────────────────

export interface AuthState {
  demo: boolean;
  auth_required: boolean;     // false only in demo mode
  admin_configured: boolean;  // a token hash exists on the station
  authenticated: boolean;     // signed in (the cookie from POST /api/login) or a valid Bearer header; always true in demo
  session?: { expires_utc: string; remembered: boolean };   // the sign-in cookie, when that's how
}

export interface LoginResult { ok: boolean; remembered?: boolean; expires_utc?: string; simulated?: boolean; detail?: string }
