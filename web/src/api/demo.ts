// ============================================================
// DEMO ADAPTER — synthetic data only, never a measurement.
// ============================================================
// Implements StationApi with payloads in the same shapes as gps_time_pi/server.py,
// so the UI can be developed with no station, no Python and no network
// (`?source=demo`, or VITE_GTP_SOURCE=demo). Every payload that has a place for
// it carries demo: true, and the app shows the demo banner whenever this
// adapter is active.
//
// Demo site: US Naval Observatory (public landmark; the project's standard
// example location). H = 92 m MSL, N ≈ −33 m, so h ≈ 59 m.

import { UI_VERSION } from '../lib/version';
import type { StationApi } from './client';
import { tokenStore } from './auth';
import { scaleValues } from '../lib/timescales';
import { applySetting } from '../lib/modules';
import type {
  Almanac, CoreStatus, ObjectReport, SkySnapshot, DisplayZone, EvidenceIndex, History, LocationMode, Measured, ModuleRow, NtpService, Oscillator, OscillatorBin, References, ReferenceServer, Satellite,
  SatelliteNow, SatelliteReport, ShadowReport, ShadowShell, ShadowState,
  Stability, StabilityPoint, Survey, SystemDiagnostics, TimeScales, TimingChain, TimingEvent, TimingStage,
} from './types';

const SITE = { lat: 38.9217, lon: -77.0669, alt_msl: 92.0, alt_hae: 59.0 };

const m = <T,>(value: T | null, unit: string | null, provenance: Measured['provenance'], note?: string): Measured<T> =>
  note ? { value, unit, provenance, note } : { value, unit, provenance };

const SATS: Satellite[] = [
  { id: 1,  gnss: 'GPS',     az: 42,  el: 67, snr: 47, used: true },
  { id: 7,  gnss: 'GPS',     az: 118, el: 33, snr: 39, used: true },
  { id: 11, gnss: 'GPS',     az: 215, el: 45, snr: 43, used: true },
  { id: 17, gnss: 'GPS',     az: 290, el: 22, snr: 35, used: false },
  { id: 20, gnss: 'GPS',     az: 163, el: 58, snr: 45, used: true },
  { id: 28, gnss: 'GPS',     az: 332, el: 12, snr: 28, used: false },
  { id: 4,  gnss: 'GLONASS', az: 78,  el: 41, snr: 41, used: true },
  { id: 13, gnss: 'GLONASS', az: 240, el: 36, snr: 38, used: true },
  { id: 3,  gnss: 'Galileo', az: 55,  el: 29, snr: 36, used: true },
  { id: 11, gnss: 'Galileo', az: 185, el: 52, snr: 44, used: true },
  { id: 19, gnss: 'Galileo', az: 310, el: 19, snr: 30, used: false },
  { id: 6,  gnss: 'BeiDou',  az: 145, el: 61, snr: 46, used: true },
];

/** Deterministic pseudo-noise so charts don't jump on every poll. */
function noise(i: number) {
  const x = Math.sin(i * 12.9898) * 43758.5453;
  return x - Math.floor(x) - 0.5;
}

function iso(ms: number) { return new Date(ms).toISOString().replace(/\.\d{3}Z$/, '+00:00'); }

export function demoApi(): StationApi {
  let locationMode: LocationMode = 'exact';
  let tzOverride: string | null = null;
  const mods = { experimental: false, enabled: [] as string[] };   // the station's rules: lib/modules.ts
  const delay = <T,>(v: T) => new Promise<T>(res => setTimeout(() => res(v), 60));

  function displayed() {
    if (locationMode === 'hidden') return { mode: locationMode, lat: null, lon: null };
    if (locationMode === 'rounded') {
      return { mode: locationMode, lat: Math.round(SITE.lat * 10) / 10, lon: Math.round(SITE.lon * 10) / 10,
               alt_msl: Math.round(SITE.alt_msl / 10) * 10 };
    }
    return { mode: locationMode, ...SITE };
  }

  // Mirrors gps_time_pi/localtime.py: override first; never from the position in hidden mode.
  function zone(): DisplayZone {
    if (tzOverride) return { tz: tzOverride, source: 'override', provenance: null, basis: null, note: 'set by the operator' };
    if (locationMode === 'hidden') {
      return { tz: null, source: null, provenance: null, basis: null, note: 'location is hidden: the zone is not derived from the position' };
    }
    return { tz: 'America/New_York', source: 'position', provenance: 'calculated', basis: locationMode,
             note: "from the station's position and bundled zone boundaries (simplified near borders)" };
  }

  return {
    source: 'demo',
    core: () => {
      // Mirrors the server's privacy rules: hidden drops sidereal time and satellite az/el.
      const c = { ...core(displayed()), timezone: zone() };
      if (locationMode !== 'hidden') return delay(c);
      return delay({ ...c, sidereal: null, gps: { ...c.gps, sats: c.gps.sats.map(s => ({ ...s, az: null, el: null })) } });
    },
    timingChain: (o) => delay(timingChain(o?.scenario)),
    history: () => delay(history()),
    stability: () => delay(stability()),
    timescales: () => delay(timescales()),
    references: (o) => delay(references(o?.scenario, o?.history)),
    ntpService: () => delay(ntpService()),
    oscillator: () => delay(oscillator()),
    evidence: () => delay(evidenceIndex()),
    // Mirrors the server: shadow geometry and passes depend on the position, so hidden mode computes none.
    shadow: (o) => delay(locationMode === 'hidden' ? { available: false as const, reason: SKY_HIDDEN, location_display: 'hidden' as const }
      : { ...shadow(o?.shell ?? 550, o?.az, o?.alt), location_display: locationMode }),
    satellites: () => delay(locationMode === 'hidden' ? { available: false as const, reason: SKY_HIDDEN, location_display: 'hidden' as const }
      : { ...satellites(), location_display: locationMode }),
    survey: () => delay(survey()),
    system: () => delay(system()),
    // Mirrors the server: sun/moon/sky times reveal the position, so hidden mode computes none.
    almanac: (q) => delay(locationMode === 'hidden'
      ? { available: false as const, reason: "Location is hidden by the station's privacy setting. Sun, moon and sky times would reveal the station's position, so they are not computed.", location_display: 'hidden' as const }
      : { ...almanac(q?.tz, q?.date, q?.target), location_display: locationMode }),
    object: (q, o) => delay(!q.trim() ? { error: 'unparsed' as const }
      : locationMode === 'hidden' ? { available: false as const, reason: "Location is hidden by the station's privacy setting.", location_display: locationMode }
      : demoObject(q, o?.date)),
    ping: () => {
      const t = Date.now();
      return delay({ server_receive_epoch_ms: t + 1.2, server_send_epoch_ms: t + 1.3 });
    },
    diagnostics: (o) => {
      const c = timingChain(o?.scenario);
      return delay(
        'GPS TIME PI DIAGNOSTIC SNAPSHOT (DEMO — synthetic data, not a measurement)\n' +
        `Generated: ${c.generated_utc}\n\nSTATUS: ${c.status.banner}\n  ${c.status.detail}\n` +
        `PPS state: ${c.pps_state.value}\nSelected source: ${c.chrony.selected?.name ?? 'none'}\n`);
    },
    setLocationDisplay: (mode) => { locationMode = mode; return delay({ ok: true as const, location_display: mode }); },
    setTimezone: (tz) => { tzOverride = tz || null; return delay({ ok: true as const, timezone: tzOverride }); },
    resetSite: () => delay({ ok: true as const, reset_site: true as const }),
    modules: () => delay({
      experimental: mods.experimental,
      modules: DEMO_MODULES.map(r => ({ ...r, enabled: mods.enabled.includes(r.name),
        runs: mods.experimental && mods.enabled.includes(r.name) && r.valid })),
      supervisor: { reporting: false, age_s: null, detail: 'demo: no module supervisor runs here' },
      note: 'Demo: settings are kept in this tab only; no module runs.',
    }),
    setModulesExperimental: (on) => delay(applySetting(mods, DEMO_VALID, { modules_experimental: on })),
    setModule: (name, enabled) => { try { return delay(applySetting(mods, DEMO_VALID, { module: name, enabled })); }
                                    catch (e) { return Promise.reject(e); } },
    admin: (action) => delay({ ok: true, action, simulated: true as const, detail: `demo adapter: ${action} was not executed` }),
    auth: () => delay({ demo: true, auth_required: false, admin_configured: false, authenticated: true }),
    token: tokenStore(null),
  };
}

// ─── payload builders ────────────────────────────────────────────────────────

/** The repository's one module, as its manifest describes it (modules/sdr-pps-marker/module.toml). */
const DEMO_MODULES: ModuleRow[] = [{
  name: 'sdr-pps-marker', installed: true, valid: true, errors: [], version: '0.1.0', maturity: 'research',
  types: ['source'], summary: 'PPS time markers in SDR sample streams: detector, sub-sample interpolation and sample-to-UTC time model',
  permissions: { network: false, devices: [], storage: 'none' }, enabled: false, runs: false, state: null, reason: null,
}];
const DEMO_VALID: ReadonlySet<string> = new Set(DEMO_MODULES.filter(r => r.valid).map(r => r.name));

function core(location: CoreStatus['location']): CoreStatus {
  const now = Date.now();
  const sys = 12.3e-9 + noise(Math.floor(now / 4000)) * 6e-9;
  return {
    demo: true,
    epoch_ms: now,
    utc: new Date(now).toISOString().replace('T', ' ').replace('Z', ' UTC'),
    quality: {
      system_time_s: sys, last_offset_s: 1.18e-8, rms_offset_s: 1.87e-8, root_delay_s: 1e-9, max_error_bound_s: Math.abs(sys) + 4.1e-9 + 0.5e-9,
      root_dispersion_s: 4.1e-9, frequency: '1.240 ppm slow', frequency_ppm: -1.24,
      residual_freq: '-0.003 ppm', skew: '0.018 ppm', update_interval: '16.0 seconds',
      leap: 'Normal', stratum: '1', reference: 'GPS', ref_time: new Date(now).toUTCString(),
    },
    sources: [
      { mode: '#', state: '*', state_label: 'selected', name: 'GPS', stratum: 0, poll: 4, reach: '377', lastrx: '13', sample: '+12ns[ +14ns] +/- 30ns' },
      { mode: '#', state: '-', state_label: 'not combined', name: 'NMEA', stratum: 0, poll: 4, reach: '377', lastrx: '14', sample: '+35ms[ +35ms] +/- 100ms' },
      { mode: '^', state: '-', state_label: 'not combined', name: '192.0.2.10', stratum: 2, poll: 6, reach: '377', lastrx: '40', sample: '-210us[-208us] +/- 12ms' },
    ],
    sourcestats: 'Sample source statistics (demo adapter).',
    clients: [
      { host: '192.0.2.21', ntp_packets: 182341, dropped: '0', last: '2' },
      { host: '192.0.2.25', ntp_packets: 44821,  dropped: '0', last: '18' },
      { host: '198.51.100.5', ntp_packets: 9341, dropped: '0', last: '120' },
      { host: '198.51.100.8', ntp_packets: 4102, dropped: '0', last: '420' },
    ],
    gps: {
      fix: '3D', sats: SATS, used: SATS.filter(s => s.used).length, visible: SATS.length,
      tdop: 0.72, hdop: 0.83, last_fix: '3D', last_fix_time: new Date(now - 1000).toISOString(),
      stale: false, data_age_s: 1.0, sky_stale: false, sky_age_s: 1.0,
    },
    location,
    survey: { n: 18432, n_fresh: 16020, n_legacy: 2412, ingest_rule: 'fresh-epoch-v1', se_horiz_m: 0.18, se_alt_m: 0.44,
              sd_lat_m: 2.1, sd_lon_m: 2.8, sd_alt_m: 4.2, updated: new Date(now).toISOString() },
    position_provenance: 'demo',
    sidereal: siderealDemo(now),
    astro_available: true, astro_reason: null,
    cpu_temp_c: 44.2,
    versions: { app: UI_VERSION, chrony: 'chrony 4.x (sample)', gpsd: '3.x (sample)',
                receiver: { driver: 'u-blox', firmware: 'sample', path: '/dev/ttyAMA0' }, python: 'demo adapter' },
  };
}

function siderealDemo(now: number) {
  // Local mean sidereal time at the demo longitude (calculated; fine for a demo readout).
  const d = now / 86400000 + 2440587.5 - 2451545.0;
  const gmst = (18.697374558 + 24.06570982441908 * d) % 24;
  const lst = ((gmst + SITE.lon / 15) % 24 + 24) % 24;
  const h = Math.floor(lst), mi = Math.floor((lst - h) * 60), s = Math.floor(((lst - h) * 60 - mi) * 60);
  return [h, mi, s].map(x => String(x).padStart(2, '0')).join(':');
}

type StageRow = [string, string, TimingStage['status'], string];

// Two scenarios mirroring gps_time_pi/demo.py (same codes, banners and
// classifications; never invent causes). pps_selected is the default.
export const DEMO_SCENARIOS = ['pps_selected', 'network_failover'] as const;

const STAGES_OK: StageRow[] = [
  ['receiver_comms', 'GNSS receiver communication', 'OK', 'gpsd reports from the receiver'],
  ['satellite_reception', 'Satellite reception', 'OK', '9 used, best C/N0 47 dB-Hz'],
  ['nav_time_solution', 'Navigation/time solution', 'OK', '3D fix'],
  ['receiver_pps_output', 'Receiver PPS output', 'NOT_OBSERVABLE', 'not directly observable by software; a HAT LED is not measured'],
  ['pps_device', 'PPS device', 'OK', '/dev/pps0 present'],
  ['kernel_events', 'Kernel PPS events', 'OK', '1 Hz, no missed pulses'],
  ['nmea_refclock', 'NMEA refclock', 'OK', 'reachable'],
  ['chrony_pps_visible', 'chrony sees PPS', 'OK', 'refclock GPS reach 377'],
  ['chrony_pps_accepted', 'chrony accepts PPS', 'OK', 'samples accepted'],
  ['chrony_pps_selected', 'chrony selects PPS', 'OK', 'selected (*)'],
  ['system_sync', 'System clock synchronized', 'OK', 'stratum 1'],
  ['fallback_source', 'Fallback source', 'NOT_APPLICABLE', 'PPS selected'],
  ['failover_duration', 'Failover duration', 'INFO', 'no failover in progress'],
];

const STAGES_FAILOVER: StageRow[] = STAGES_OK.map(([id, label, st, sum]): StageRow => {
  switch (id) {
    case 'kernel_events': return [id, label, 'FAILED', 'no PPS events for > 3 s'];
    case 'chrony_pps_visible': return [id, label, 'OK', 'refclock GPS present, reach 0'];
    case 'chrony_pps_accepted': return [id, label, 'FAILED', 'no samples'];
    case 'chrony_pps_selected': return [id, label, 'FAILED', 'not selected (?)'];
    case 'system_sync': return [id, label, 'OK', 'synchronized to a network source, stratum 3'];
    case 'fallback_source': return [id, label, 'OK', '192.0.2.10 (network) selected'];
    case 'failover_duration': return [id, label, 'INFO', 'failover in progress'];
    default: return [id, label, st, sum];
  }
});

// Classifications/boundaries/confidence are copied from timing_chain.classify(); never invent causes.
function closedOutage(startMs: number, durationS: number, cls: string, boundary: string, confidence: string | null,
                      maxAbs: number, toAccept: number, toSelect: number): TimingEvent {
  return {
    schema: 'gps-time.event/1', id: `pps-outage-${Math.floor(startMs / 1000)}`, type: 'PPS_OUTAGE',
    start_epoch: startMs / 1000, start_utc: iso(startMs), end_utc: iso(startMs + durationS * 1000),
    duration_s: durationS, open: false, severity: 'critical', classification: cls, initial_classification: cls,
    confidence, boundary, classification_provenance: 'inferred',
    evidence: { fallback_sources: ['192.0.2.10'], max_abs_system_time_s: maxAbs, satellites_used_range: [8, 11] },
    recovery: {
      recovered_utc: iso(startMs + durationS * 1000),
      duration_s: m(durationS, 's', 'calculated'),
      time_to_accept_s: m(toAccept, 's', 'calculated'),
      time_to_select_s: m(toSelect, 's', 'calculated'),
      fallback_sources: ['192.0.2.10'],
      max_abs_system_time_s: m(maxAbs, 's', 'observed', "largest chrony remaining-correction seen; chrony estimate, not an independent error measurement"),
    },
    notes: ['Demo event — synthetic.'],
  };
}

function timingChain(scenario: string = 'pps_selected'): TimingChain {
  const now = Date.now();
  const day = 86400000;
  const failover = scenario === 'network_failover';
  const openStart = now - (2 * day + 7 * 3600000 + 14 * 60000);
  const ppsRef = (sym: string, meaning: string, reach: string, ok: boolean) => ({
    name: 'GPS', mode: 'local reference clock',
    state_symbol: m(sym, null, 'observed'), state_meaning: meaning,
    reach: m(reach, 'octal', 'observed'), reach_successes_of_8: m(ok ? 8 : 0, 'count', 'calculated'),
    last_rx_s: m(ok ? 13 : null, 's', 'observed'), poll_log2_s: 4,
    offset_s: m(ok ? 1.84e-7 : null, 's', 'observed', "chrony's adjusted offset of the last sample"),
    error_bound_s: m(ok ? 2.03e-7 : null, 's', 'observed'),
    frequency_ppm: m(ok ? 0.0 : null, 'ppm', 'calculated'), skew_ppm: m(ok ? 0.012 : null, 'ppm', 'calculated'),
    std_dev_s: m(ok ? 1.64e-7 : null, 's', 'calculated'),
  });
  const recent = [
    closedOutage(now - 9.0 * day, 1387, 'PPS AND GNSS TELEMETRY UNAVAILABLE', 'unknown', 'low', 2.1e-4, 21.0, 63.0),
    closedOutage(now - 5.4 * day, 72, 'GNSS RECEPTION ANOMALY', 'GNSS reception / receiver solution', 'low', 3.4e-6, 8.0, 34.0),
    closedOutage(now - 2.1 * day - (failover ? 3 * day : 0), 34, 'PPS PATH ANOMALY', 'receiver PPS output / GPIO / kernel PPS interface', 'moderate', 1.1e-6, 6.0, 31.0),
  ].reverse();
  const openEvent: TimingEvent | null = failover ? {
    schema: 'gps-time.event/1', id: `pps-outage-${Math.floor(openStart / 1000)}`, type: 'PPS_OUTAGE',
    start_epoch: openStart / 1000, start_utc: iso(openStart), end_utc: null,
    duration_s: Math.round((now - openStart) / 1000), open: true, severity: 'critical',
    classification: 'PPS PATH ANOMALY', initial_classification: 'PPS PATH ANOMALY', confidence: 'moderate',
    boundary: 'receiver PPS output / GPIO / kernel PPS interface', classification_provenance: 'inferred',
    evidence: { fallback_sources: ['192.0.2.10'], max_abs_system_time_s: 4.2e-4, satellites_used_range: [8, 13], gnss_unhealthy_seen: false },
    recovery: null,
    notes: ['GNSS reception and navigation remained healthy while kernel PPS events stopped.',
            'Evidence does not establish which component in that path failed.', 'Demo event — synthetic.'],
  } : null;

  return {
    schema: 'gps-time.timing-chain/1',
    generated_utc: iso(now),
    status: failover
      ? { code: 'NETWORK_FAILOVER', headline: 'SYNCHRONIZED', banner: 'SYNCHRONIZED · NETWORK FAILOVER · GPS/PPS UNAVAILABLE',
          detail: 'chrony is using network source 192.0.2.10; PPS refclock GPS is not selected.',
          source: { name: '192.0.2.10', kind: 'network', stratum: '3' }, gnss_healthy: true, provenance: 'calculated' }
      : { code: 'GPS_PPS', headline: 'SYNCHRONIZED', banner: 'SYNCHRONIZED · GPS/PPS · STRATUM 1',
          detail: 'PPS refclock GPS selected by chrony.', source: { name: 'GPS', kind: 'refclock', stratum: '1' },
          gnss_healthy: true, provenance: 'calculated' },
    pps_state: m(failover ? 'LOST' : 'SELECTED', null, 'calculated'),
    pps: {
      device: m('/dev/pps0', null, 'observed'), device_present: m(true, null, 'observed'),
      metadata: { name: 'pps@12.-1', path: '/sys/class/pps/pps0' },
      thresholds_s: { degraded_after: 1.5, lost_after: 3.0 },
      pulse_health: failover ? 'LOST' : 'HEALTHY', pulse_health_provenance: 'calculated',
      measurement_layer: 'Linux kernel PPS timestamps (CLOCK_REALTIME); not the receiver or electrical PPS edge',
      note: null,
      last_event_utc: m(failover ? iso(openStart) : iso(now - (now % 1000)), null, 'observed'),
      last_sequence: m(failover ? 4021 : 100030, null, 'observed'),
      age_s: m(failover ? (now - openStart) / 1000 : (now % 1000) / 1000, 's', 'calculated'),
      last_interval_s: m(failover ? null : 1.0, 's', 'calculated'),
      rate_hz: m(failover ? null : 1.0, 'Hz', 'calculated'),
      consecutive_pulses: m(failover ? 0 : 21, 'count', 'calculated'),
      missed_pulses: m(failover ? null : 0, 'count', 'calculated'),
      unread_pulses: m(failover ? null : 0, 'count', 'calculated'),
      poller: { polls: 86400, late_polls: 0, max_poll_gap_s: 1.02, late_after_s: 1.5, note: "the station's own reads of the kernel PPS; a late poll delays observation, not the clock" },
      sequence_resets: 0,
      interval_stats: failover ? null
        : m({ count: 20, mean: 1.0000002, min: 0.9999981, max: 1.0000019, stdev: 9.4e-7 }, 's', 'calculated',
            'Linux kernel PPS timestamps (CLOCK_REALTIME); not receiver or electrical jitter'),
      boot_config: { gpio: 18, assert_edge: 'rising', source: 'demo' },
    },
    gnss: {
      receiver_comms: 'OK', satellite_reception: 'OK', nav_time_solution: 'OK', healthy: true,
      fix: m('3D', null, 'observed'), satellites_visible: m(SATS.length, 'count', 'observed'),
      satellites_used: m(SATS.filter(s => s.used).length, 'count', 'observed'),
      best_cn0: m(47, 'dB-Hz', 'observed'), median_cn0_used: m(43, 'dB-Hz', 'calculated'),
      tdop: m(0.72, null, 'observed'), data_age_s: m(0.8, 's', 'calculated'),
    },
    chrony: {
      available: { tracking: true, sources: true, sourcestats: true },
      refclocks: { pps: 'GPS', nmea: 'NMEA', identified_from: 'chrony.conf', pps_lock: 'NMEA' },
      pps_status: failover ? 'VISIBLE_NO_SAMPLES' : 'SELECTED', nmea_status: 'OK',
      pps: failover
        ? ppsRef('?', "connectivity lost or samples fail chrony's tests (also shown until enough samples exist)", '0', false)
        : ppsRef('*', 'current best source, used to discipline the clock', '377', true),
      nmea: null,
      // Mirrors timing_chain.nmea_calibration: measurable only while PPS is selected.
      nmea_calibration: failover
        ? { available: false, reason: 'PPS must be the selected source: only then is the system clock a good enough reference to measure the NMEA delay against',
            configured_offset_s: m(0.1, 's', 'observed') }
        : { available: true, reason: null, configured_offset_s: m(0.1, 's', 'observed'), residual_s: m(0.035, 's', 'observed'),
            std_dev_s: m(0.001271, 's', 'observed'), samples: m(32, 'count', 'observed'), span_s: m(496, 's', 'observed'),
            suggested_offset_s: m(0.135, 's', 'calculated'), change_worthwhile: true,
            advice: 'Change `offset 0.1` to `offset 0.135` on the NMEA refclock line in chrony.conf and restart chrony. Then check this again after a few minutes: the residual should be near zero. If it has roughly doubled instead, the sign is the other way round on this system: use `offset 0.065`.' },
      selected: failover
        ? { name: '192.0.2.10', kind: 'network', stratum: 2, is_pps: false, is_nmea: false }
        : { name: 'GPS', kind: 'refclock', stratum: 0, is_pps: true, is_nmea: false },
      any_selected: true,
      tracking: { leap: 'Normal', stratum: failover ? '3' : '1', reference: failover ? '192.0.2.10' : 'GPS',
                  system_time_s: m(failover ? 3.1e-4 : 12.3e-9, 's', 'observed', "chrony's remaining correction, not an independent measurement"),
                  root_delay_s: m(failover ? 0.024 : 1e-9, 's', 'observed'),
                  root_dispersion_s: m(failover ? 0.0013 : 4.1e-9, 's', 'observed'),
                  frequency: '1.240 ppm slow' },
    },
    classification: failover
      ? { classification: 'PPS PATH ANOMALY', confidence: 'moderate', boundary: 'receiver PPS output / GPIO / kernel PPS interface',
          notes: ['GNSS reception and navigation remained healthy while kernel PPS events stopped.',
                  'Evidence does not establish which component in that path failed.'] }
      : null,
    stages: (failover ? STAGES_FAILOVER : STAGES_OK).map(([id, label, status, summary]) => ({ id, label, status, summary, evidence: {} })),
    events: { open: openEvent, recent },
    boot: { phase: 'RUN', boot_utc: iso(now - 7 * day), since_boot_s: m(7 * 86400, 's', 'calculated'),
            pps_selected_this_boot: true },
    raw: {
      tracking: failover
        ? 'Reference ID    : C000020A (192.0.2.10)\nStratum         : 3\nSystem time     : 0.000310000 seconds fast of NTP time\n(demo)'
        : 'Reference ID    : 47505300 (GPS)\nStratum         : 1\nSystem time     : 0.000000012 seconds fast of NTP time\n(demo)',
      sources: failover
        ? 'MS Name/IP address         Stratum Poll Reach LastRx Last sample\n#? GPS                           0   4     0     -     +0ns[   +0ns] +/-    0ns\n^* 192.0.2.10                    2   6   377    40   -310us[ -308us] +/-   12ms\n(demo)'
        : 'MS Name/IP address         Stratum Poll Reach LastRx Last sample\n#* GPS                           0   4   377    13   +184ns[ +190ns] +/-  203ns\n^- 192.0.2.10                    2   6   377    40   -210us[ -208us] +/-   12ms\n(demo)',
      sourcestats: '(demo)',
    },
    demo: { scenario: failover ? 'network_failover' : 'pps_selected',
            description: failover ? 'PPS lost; chrony fell back to a network source (client-side demo adapter)'
                                  : 'Normal: PPS selected by chrony (client-side demo adapter)',
            scenarios: [...DEMO_SCENARIOS], note: 'synthetic data — not a measurement' },
  };
}

function history(): History {
  // 7 days at 10-minute spacing, with one brief excursion.
  const now = Date.now() / 1000;
  const n = 7 * 144;
  const points = Array.from({ length: n }, (_, i) => {
    const t = now - (n - i) * 600;
    const spike = i === n - 300 ? 180e-9 : 0;
    const sd = 4e-9 + Math.abs(noise(i + 7)) * 4e-9 + Math.abs(spike) / 3;
    return { t, offset_s: 12e-9 + Math.sin(i * 0.15) * 6e-9 + noise(i) * 10e-9 + spike, offset_sd_s: sd,
             remaining_correction_s: noise(i + 3) * 5e-9, root_delay_s: 1e-9, root_dispersion_s: 6e-6 + sd, max_error_s: 2.4e-5 + sd * 3,
             freq_ppm: 10.3, skew_ppm: 0.009, leap: 'N', n_combined: 1, stratum: 1, source: 'PPS' };
  });
  return { available: true, points, note: 'demo adapter sample data' };
}

function stability(): Stability {
  // White phase noise of 250 ns: ADEV = √3·σ/τ, MDEV falls as τ^-1.5; a small
  // floor stands in for slow wander. Not a measurement.
  const sigma = 250e-9;
  const mk = (tau: number, series: 'seconds' | 'minutes', n: number): StabilityPoint => {
    const m = tau / (series === 'seconds' ? 1 : 60);
    const adev = Math.hypot(Math.sqrt(3) * sigma / tau, 4e-12);
    const mdev = Math.hypot(Math.sqrt(3) * sigma / tau ** 1.5, 1.5e-12);
    const edf = Math.max(8, (n - 2 * m) / 2);
    const spread = 1 / Math.sqrt(2 * edf);
    return { tau_s: tau, series, adev, adev_terms: n - 2 * m,
             adev_low: adev * (1 - spread), adev_high: adev * (1 + spread), edf,
             noise: 'white PM', noise_assumed: n / m < 30,
             mdev, mdev_terms: n - 3 * m + 1, tdev_s: tau * mdev / Math.sqrt(3) };
  };
  const points = [
    ...[1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000].map(t => mk(t, 'seconds', 14400)),
    ...[3600, 7200, 18000, 36000, 86400].map(t => mk(t, 'minutes', 7200)),
  ];
  const key = (tau: number, label: string) => ({ tau_s: tau, label, point: points.find(p => p.tau_s === tau) ?? null, reason: null });
  return {
    available: true, reason: null, provenance: 'calculated',
    measurement_layer: "System clock against kernel PPS timestamps: the Linux/chrony view of PPS, including interrupt latency and chrony's loop. Not the receiver's electrical PPS and not the oscillator alone.",
    method: 'Overlapping Allan deviation, modified Allan deviation and time deviation (NIST SP 1065). Input: the fractional second of each kernel PPS timestamp. Up to 2000 s from 1 s samples; from 1 h from minute summaries (last sample of each minute for ADEV, minute mean for MDEV and TDEV).',
    confidence: { level: 0.683, applies_to: 'adev', noise_provenance: 'inferred',
                  method: 'Chi-squared interval; degrees of freedom from the power-law noise type identified by lag-1 autocorrelation (SP 1065 sections 5.4.1 and 5.5.6). No interval is calculated for MDEV or TDEV.' },
    storage: 'RAM only; lost when the service restarts',
    since_utc: new Date(Date.now() - 5 * 86400e3).toISOString(),
    history_resets: 0,
    series: {
      seconds: { tau0_s: 1, samples: 14400, gaps: 0, span_s: 14400, capacity_s: 14400, pps_selected_fraction: 1 },
      minutes: { tau0_s: 60, samples: 7200, gaps: 0, span_s: 432000, capacity_s: 1209600, pps_selected_fraction: 1 },
    },
    points,
    key_points: [key(1, '1 s'), key(10, '10 s'), key(100, '100 s'), key(1000, '1000 s'), key(86400, '1 day')],
    notes: ['sample data'],
  };
}

const SKY_HIDDEN = "Location is hidden by the station's privacy setting. The Earth-shadow geometry and satellite passes depend on the station's position, so they are not computed.";

function shadow(shellKm: number, az?: number, alt?: number): ShadowReport {
  // A fixed evening scene, not a calculation: Sun 27° down in the WNW. For each
  // shell the shadow edge is a simple curve that is lowest toward the Sun.
  const sunAz = 290, sunAlt = -26.9;
  const edge = (km: number, a: number) => {
    const toward = Math.cos((a - sunAz) * Math.PI / 180);          // 1 toward the Sun, -1 away
    return Math.max(-5, (km - 420) / 16 * (0.25 + 0.75 * Math.max(0, toward)) - 8 * (1 - toward));
  };
  const stateAt = (km: number, a: number, h: number): ShadowState => {
    const e = edge(km, a);
    return h < e - 1 ? 'SUNLIT' : h <= e + 1 ? 'PENUMBRA' : 'UMBRA';
  };
  const alts = Array.from({ length: 46 }, (_, i) => i * 2), azs = Array.from({ length: 72 }, (_, i) => i * 5);
  const rows = alts.map(h => azs.map(a => stateAt(shellKm, a, h)[0]).join(''));
  const sectorNames = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const shell = (km: number): ShadowShell => {
    let lit = 0, all = 0, maxAlt: number | null = null;
    const sectors: string[] = [];
    for (let h = 10; h <= 90; h += 5) for (let a = 0; a < 360; a += 10) {
      const w = Math.cos(h * Math.PI / 180) || 1e-9;
      all += w;
      if (stateAt(km, a, h) !== 'UMBRA') {
        lit += w; maxAlt = Math.max(maxAlt ?? 0, h);
        const s = sectorNames[Math.floor(((a + 22.5) % 360) / 45)];
        if (!sectors.includes(s)) sectors.push(s);
      }
    }
    sectors.sort((x, y) => sectorNames.indexOf(x) - sectorNames.indexOf(y));
    return { altitude_km: km, zenith: stateAt(km, 0, 90), sunlit_sky_fraction: Math.round(lit / all * 1000) / 1000,
             sunlit_max_altitude_deg: maxAlt, sunlit_sectors: sectors,
             summary: maxAlt === null ? "In Earth's shadow everywhere above 10°."
               : `In Earth's shadow above ${maxAlt}° altitude; sunlit positions remain possible lower in the ${sectors.join(', ')}.` };
  };
  const kms = [...new Set([200, 350, 400, 550, 1000, 1200, 2000, shellKm])].sort((a, b) => a - b);
  const shells = kms.map(shell);
  const s550 = shells.find(s => s.altitude_km === 550)!;
  return {
    available: true, reason: null, provenance: 'modeled',
    model: 'Conical umbra and penumbra of a spherical, airless Earth with the Sun as a disc of finite size. Geometric: the atmosphere blurs and shifts the real shadow edge by some tens of km of height, and angles are not corrected for refraction.',
    meaning: 'Says whether a satellite at that height would be in sunlight. It does not say that a satellite is there, or that a sunlit one is bright enough to see.',
    as_of_utc: iso(Date.now()),
    sun: { altitude_deg: sunAlt, azimuth_deg: sunAz, depression_deg: -sunAlt, distance_au: 0.99963,
           antisolar: { azimuth_deg: (sunAz + 180) % 360, altitude_deg: -sunAlt }, note: 'geometric altitude, no refraction; analytic solar position, about 0.01°' },
    darkness: { stage: 'night', astronomical_darkness: true },
    cone: { umbra_half_angle_deg: 0.2642, penumbra_half_angle_deg: 0.2691, umbra_length_km: 1381900, axis: "from the Earth's centre toward the anti-solar point" },
    zenith: { umbra_top_km: 762.8, penumbra_top_km: 796.7, ground_state: 'UMBRA', beyond_limit: false, search_limit_km: 50000,
              note: 'Height at which the line straight up leaves the shadow. One number for the zenith only: the boundary is lower toward the Sun and higher away from it.' },
    shells,
    map: { shell_km: shellKm, alt_step_deg: 2, az_step_deg: 5, alts_deg: alts, azs_deg: azs, rows },
    query: az === undefined || alt === undefined ? null
      : { azimuth_deg: az, altitude_deg: alt, shell_km: shellKm, state: stateAt(shellKm, az, alt),
          sunlit_fraction: stateAt(shellKm, az, alt) === 'SUNLIT' ? 1 : stateAt(shellKm, az, alt) === 'UMBRA' ? 0 : 0.5,
          range_km: Math.round(shellKm / Math.max(0.2, Math.sin(alt * Math.PI / 180))), note: 'sunlit fraction inside the penumbra is a linear estimate' },
    messages: [
      `Most satellites at ~550 km LEO should be in Earth's shadow above ${s550.sunlit_max_altitude_deg ?? 10}° altitude; sunlit ones remain possible in the ${s550.sunlit_sectors.join(', ')}.`,
      "These are geometric predictions from the shadow model, not sightings: they don't say that a satellite is there or that it is bright enough to record.",
    ],
  };
}

function satellites(): SatelliteReport {
  // Written by hand, like gps_time_pi/demo.py: no orbital elements are needed in demo mode.
  const now = Date.now();
  const at = (min: number, sec = 0) => iso(now + (min * 60 + sec) * 1000);
  const pt = (min: number, sec: number, azimuth_deg: number, altitude_deg: number, range_km: number, state: ShadowState) =>
    ({ utc: at(min, sec), azimuth_deg, altitude_deg, range_km, state });
  const epoch = iso(now - 31 * 3600e3);
  const iss: SatelliteNow = {
    norad: 25544, name: 'ISS (ZARYA)', group: 'stations', epoch_utc: epoch, age_days: 1.29, stale: false, age_note: null,
    available: true, reason: null, provenance: 'modeled', azimuth_deg: 212.4, altitude_deg: -31.6, above_horizon: false,
    range_km: 7480.2, height_km: 418, angular_speed_deg_s: 0.051, state: 'SUNLIT', sunlit_fraction: 1, could_be_seen: false,
  };
  const css: SatelliteNow = { ...iss, norad: 48274, name: 'CSS (TIANHE)', azimuth_deg: 78.9, altitude_deg: -12.3, range_km: 4310.5,
                              height_km: 384, angular_speed_deg_s: 0.118, state: 'UMBRA', sunlit_fraction: 0 };
  return {
    available: true, reason: null, provenance: 'external',
    meaning: "Predictions from orbital elements. 'Could be seen' means above 10°, not in the Earth's umbra, and the Sun at least 6° below the horizon. It says nothing about brightness, cloud or obstructions.",
    as_of_utc: iso(now),
    cache: { dir: '(sample cache)', satellites: 2,
             groups: [{ group: 'stations', file: 'stations.tle', count: 2, rejected: 0, source: '(sample data)', fetched_utc: iso(now - 9 * 3600e3),
                        newest_epoch_utc: epoch, oldest_epoch_utc: epoch }],
             newest_epoch_utc: epoch, newest_age_days: 1.29, oldest_age_days: 1.29, stale_after_days: 14, problems: [], provenance: 'external' },
    featured: [iss, css], satellite: iss, matches: [], window_hours: 24,
    passes: [
      { rise: pt(42, 10, 318.2, 0, 2368.4, 'SUNLIT'), culmination: pt(47, 6, 41.7, 48.3, 548.9, 'SUNLIT'), set: pt(52, 0, 124.6, 0, 2371.0, 'UMBRA'),
        in_progress: false, duration_s: 590,
        shadow_changes: [
          { utc: at(48, 39), kind: 'penumbra entry', from: 'SUNLIT', to: 'PENUMBRA', azimuth_deg: 96.1, altitude_deg: 31.4 },
          { utc: at(48, 51), kind: 'umbra entry', from: 'PENUMBRA', to: 'UMBRA', azimuth_deg: 99.8, altitude_deg: 28.9 }],
        visible: { start_utc: at(44, 14), end_utc: at(48, 50), duration_s: 276, max_altitude_deg: 48.3, max_azimuth_deg: 41.7 },
        sun_altitude_deg: -16.3, provenance: 'predicted' },
      { rise: pt(139, 2, 291.5, 0, 2370.1, 'SUNLIT'), culmination: pt(143, 8, 232.0, 10.9, 1489.3, 'UMBRA'), set: pt(147, 15, 173.4, 0, 2369.7, 'UMBRA'),
        in_progress: false, duration_s: 493,
        shadow_changes: [
          { utc: at(140, 27), kind: 'penumbra entry', from: 'SUNLIT', to: 'PENUMBRA', azimuth_deg: 281.0, altitude_deg: 3.9 },
          { utc: at(140, 39), kind: 'umbra entry', from: 'PENUMBRA', to: 'UMBRA', azimuth_deg: 279.2, altitude_deg: 4.6 }],
        visible: null, sun_altitude_deg: -33.3, provenance: 'predicted' },
    ],
    demo: { note: 'synthetic data — not a prediction' },
  };
}

function evidenceIndex(): EvidenceIndex {
  const now = Date.now(), start = now - 3 * 3600e3;
  return {
    available: true, dir: '(sample data)', total_bytes: 48213, max_bytes: 20971520, max_files: 200, removed_for_space: 0, problems: [],
    note: 'Written 5 minutes after an outage opens and again 5 minutes after it closes; the oldest files are removed when the cap is reached.',
    files: [{ id: `pps-outage-${Math.floor(start / 1000)}`, phase: 'closed', written_utc: iso(start + 3663e3), start_utc: iso(start),
              end_utc: iso(start + 3363e3), duration_s: 3363, classification: 'GNSS RECEPTION ANOMALY', bytes: 48213,
              tracking_lines: 141, timeline_points: 397 }],
  };
}

function oscillator(): Oscillator {
  // Mirrors gps_time_pi/demo.py: two days, the SoC warming by day, a crystal at -0.3 ppm per degree C.
  const now = Date.now(), start = now - 2 * 86400e3;
  const bins: OscillatorBin[] = Array.from({ length: 288 }, (_, i) => {
    const t = start + i * 600e3;
    const temp = 50 + 6 * Math.sin(2 * Math.PI * (i / 144 - 0.3)) + 0.3 * Math.sin(i / 2);
    const freq = 10.9 - 0.3 * (temp - 50);
    return { t: iso(t), samples: 10, pps_samples: 10, temp_mean_c: temp, temp_min_c: temp - 0.2, temp_max_c: temp + 0.2,
             freq_mean_ppm: freq, freq_min_ppm: freq - 0.003, freq_max_ppm: freq + 0.003, skew_mean_ppm: 0.008, residual_mean_ppm: 0 };
  });
  const last = bins[bins.length - 1];
  return {
    available: true, reason: null, provenance: 'observed',
    sensor: 'SoC temperature sensor (/sys/class/thermal), not the crystal: the two follow each other only roughly, and with a lag.',
    frequency_note: "chrony's Frequency: how fast the uncorrected system clock runs; + = fast. Bins with PPS not selected throughout are kept but not used for the fit.",
    bin_s: 600, sample_interval_s: 60, bins,
    latest: { temp_c: m(last.temp_mean_c, '°C', 'observed'), freq_ppm: m(last.freq_mean_ppm, 'ppm', 'observed'), bin_start_utc: last.t },
    fit: { bins_used: 288, slope_ppm_per_c: -0.3, intercept_ppm: 25.9, r: -1.0, temp_span_c: 12.5, reason: null, provenance: 'calculated' },
    fit_note: 'A straight line through frequency against temperature over the logged bins. It is not the oscillator profile and not a holdover prediction.',
    // The profile the station would fit to these bins (the server demo fits it for real).
    profile: {
      status: 'fitted', reason: null, provenance: 'modeled', model: 'linear',
      terms: [{ name: 'a', value: 10.9, se: 0.0002, unit: 'ppm' }, { name: 'b', value: -0.3, se: 0.00004, unit: 'ppm/°C' }],
      bins_used: 288, outliers: 0, residual_rms_ppm: 0.0012, r2: 0.9999, temp_ref_c: 50, t0_utc: bins[0].t,
      t0_utc_epoch: Date.parse(bins[0].t) / 1000,
      covers: { temp_min_c: 43.7, temp_max_c: 56.3, first_utc: bins[0].t, last_utc: last.t,
                first_utc_epoch: Date.parse(bins[0].t) / 1000, last_utc_epoch: Date.parse(last.t) / 1000, days: 1.993 },
      candidates: [{ model: 'linear', bic: -3880.1 }, { model: 'quadratic', bic: -3874.6 }],
      note: "A statistical model of how chrony's frequency estimate moved with the SoC sensor's temperature (and with time) while GPS kept the clock right, fitted over the whole log. It describes this board's sensor and crystal together, only within the temperature range and time span it covers. It is not a holdover guarantee.",
    },
    storage: { path: '(sample data)', bytes: 24727, max_bytes: 4194304, pending_bins: 3, flush_interval_s: 3600,
               note: '10-minute bins appended once an hour and on a clean stop; oldest quarter dropped past the cap' },
    board: { serial_sha256: 'demo', model: 'demo board' },
    problems: ['sample data'],
  };
}

function ntpService(): NtpService {
  // Mirrors gps_time_pi/demo.py: about 14 requests a minute, a few dropped, two hours of history.
  const now = Date.now() / 1000;
  let rx = 48210, drop = 37;
  const totals: [number, number, number][] = [];
  for (let i = 0; i <= 120; i++) {
    rx += 12 + Math.floor(4 * (1 + Math.sin(i / 7)));
    drop += i % 45 === 44 ? 1 : 0;
    totals.push([now - (120 - i) * 60, rx, drop]);
  }
  const history = totals.slice(1).map(([t, r, d], i) => ({ t, received_per_min: r - totals[i][1], dropped_per_min: d - totals[i][2] }));
  const hourAgo = totals[60], minAgo = totals[119], last = totals[120];
  const rate = (a: [number, number, number]) => ({
    received_per_s: m((last[1] - a[1]) / (last[0] - a[0]), '1/s', 'calculated'),
    dropped_per_s: m((last[2] - a[2]) / (last[0] - a[0]), '1/s', 'calculated'),
  });
  return {
    available: true, reason: null, provenance: 'observed',
    state: 'SERVING_WITH_DROPS', state_basis: 'over the last hour', state_provenance: 'calculated',
    as_of_utc: new Date().toISOString().slice(0, 19) + '+00:00',
    counters: { ntp_received: rx, ntp_dropped: drop, cmd_received: 412, cmd_dropped: 0, client_log_dropped: 0, ntp_interleaved: 96 },
    ntp: {
      received: m(rx, 'packets', 'observed', 'NTP packets received, since chronyd started'),
      dropped: m(drop, 'packets', 'observed', 'NTP packets chrony dropped under its rate limit'),
      not_dropped: m(rx - drop, 'packets', 'calculated', 'received − dropped; chrony does not count the replies it sent'),
      drop_fraction: m(drop / rx, null, 'calculated'),
    },
    rates: { last_minute: rate(minAgo), last_hour: rate(hourAgo) },
    history,
    history_info: { interval_s: 60, max_points: 1440, storage: 'RAM only; lost when the service restarts' },
    counter_resets: 0,
    note: "Counters are chrony's and restart from zero when chronyd restarts. Sample data.",
  };
}

function references(scenario: string = 'agree', historyFor?: string): References {
  // Mirrors gps_time_pi/demo.py: three noselect servers, 15 h of history.
  const now = Date.now() / 1000;
  const shift = scenario === 'disagree' ? 0.180 : 0;
  const reachable = scenario !== 'unreachable';
  const threshold = 0.05;
  const servers: [string, number, number, number, number][] = [
    ['192.0.2.10', 1, 0.0021, 0.018, 0.031], ['192.0.2.20', 1, -0.0034, 0.022, 0.038], ['198.51.100.7', 2, 0.0009, 0.015, 0.024],
  ];
  const refs: ReferenceServer[] = (scenario === 'none' ? [] : servers).map(([name, stratum, off, err, del], k) => {
    const at = (i: number) => off + shift + 0.0006 * Math.sin(i / 9 + k);
    const offset = at(180);
    return {
      name, state: '?', state_label: 'not selectable', stratum, poll_s: 256, reach: reachable ? '377' : '0',
      reachable, usable: reachable, lastrx_s: reachable ? 30 : null,
      offset_s: reachable ? offset : null, error_bound_s: reachable ? err : null,
      delay_s: reachable ? del : null, root_delay_s: reachable ? 0.0004 : null,
      assessment: !reachable ? 'not usable' : Math.abs(offset) <= threshold ? 'agrees' : 'disagrees',
      provenance: 'external',
      history: reachable && name === (historyFor ?? servers[0][0]) ? Array.from({ length: 181 }, (_, i) => ({ t: now - (180 - i) * 300 - 30, offset_s: at(i), error_bound_s: err, delay_s: del })) : [],
      history_points: reachable ? 181 : 0,
    };
  });
  const usable = refs.filter(r => r.usable).length;
  const disagreeing = refs.filter(r => r.assessment === 'disagrees').length;
  const counts = { configured: refs.length, usable, agreeing: usable - disagreeing, disagreeing, inconclusive: 0 };
  const base = { provenance: 'calculated' as const, threshold_s: threshold };
  const verdict: References['verdict'] =
    !refs.length ? { ...base, code: 'NONE_CONFIGURED', headline: 'NO INDEPENDENT REFERENCES',
                     detail: 'chrony is not polling any server that is not steering the clock, so there is nothing to compare with.' }
    : !usable ? { ...base, ...counts, code: 'NONE_REACHABLE', headline: 'NO EXTERNAL REFERENCES REACHABLE',
                  detail: `None of the ${refs.length} independent server(s) has answered recently. The station works without them; there is no comparison to report.` }
    : disagreeing * 2 > usable ? { ...base, ...counts, code: 'DISAGREE', headline: 'STATION DISAGREES WITH MOST INDEPENDENT REFERENCES',
                  detail: `The station's clock differs from ${disagreeing} of ${usable} independent references by more than 50 ms. This is a disagreement between clocks; it does not say which clock is wrong or why.` }
    : { ...base, ...counts, code: 'AGREE', headline: 'STATION AGREES WITH INDEPENDENT REFERENCES',
        detail: `${usable - disagreeing} of ${usable} independent references are within 50 ms of the station.` };
  return {
    available: true, provenance: 'external', as_of_utc: new Date().toISOString().slice(0, 19) + '+00:00',
    verdict, references: refs, excluded: [], delay_available: true, delay_note: null,
    sign: "offset_s is chrony's figure for the last measurement: positive means the station's clock is ahead of that server.",
    history: { interval_s: 60, max_points: 1440, storage: 'RAM only; lost when the service restarts' },
    demo: { scenario, scenarios: ['agree', 'disagree', 'unreachable', 'none'], note: 'synthetic data — not a measurement' },
  };
}

function timescales(): TimeScales {
  // The real calculation on this browser's clock, with a sample leap-second
  // table (valid for another 200 days) and no cached IERS file.
  const now = new Date();
  const v = scaleValues(now, 37);
  const iso = (ms: number) => new Date(ms).toISOString().slice(0, 19) + '+00:00';
  const calc = <T,>(value: T, unit: string | null = null) => m(value, unit, 'calculated');
  return {
    provenance: 'calculated',
    utc: iso(now.getTime()), unix_s: v.unix,
    tai_utc_s: calc(37, 's'), gps_utc_s: calc(18, 's'),
    tai: calc(v.tai!),
    gps: { time: calc(v.gps!), week: calc(v.gpsWeek!), week_mod_1024: calc(v.gpsWeekMod1024!), seconds_of_week: calc(v.gpsSecondsOfWeek!, 's') },
    mjd: calc(Number(v.mjd), 'd'), jd: calc(Number(v.jd), 'd'),
    leap_seconds: {
      provenance: 'external', source: 'file', source_label: 'IERS leap-second list from the operating system',
      path: '(sample leap-second list)',
      updated_utc: iso(now.getTime() - 120 * 86400e3), expires_utc: iso(now.getTime() + 200 * 86400e3),
      days_to_expiry: 200, status: 'OK', warning: null, warn_days: 60,
      last: { utc: '2017-01-01T00:00:00+00:00', tai_utc_s: 37 }, next: null,
      next_note: `None scheduled in the table, which is valid until ${iso(now.getTime() + 200 * 86400e3).slice(0, 10)}.`,
      chrony_leap_status: m('Normal', null, 'observed', 'chrony tracking: Leap status'),
      problems: [],
    },
    ut1: { available: false, provenance: 'external', path: '(none in demo)', ut1_utc_s: null, kind: null, file_date_utc: null,
           reason: 'No cached IERS file on the station. UT1 − UTC needs IERS data from the Internet, which the station does not fetch.' },
  };
}

function survey(): Survey {
  const now = Math.floor(Date.now() / 1000);
  return {
    available: true,
    history: Array.from({ length: 48 }, (_, i) => {
      const n = 400 * (i + 1);
      return [now - (48 - i) * 3600, n, 2.6 / Math.sqrt(n / 4), 5.0 / Math.sqrt(n / 4)];
    }),
    fixes: Array.from({ length: 60 }, (_, i) => [noise(i) * 4, noise(i + 100) * 5]),
    stats: { n: 18432, n_fresh: 16020, n_legacy: 2412, ingest_rule: 'fresh-epoch-v1', se_horiz_m: 0.18, se_alt_m: 0.44,
             sd_lat_m: 2.1, sd_lon_m: 2.8, sd_alt_m: 4.2 },
    ingest: { accepted_this_session: 60, rejected_this_session: { no_tpv: 0, no_3d_fix: 2, invalid: 0, repeat_epoch: 14, older_epoch: 0, rate_limited: 0 },
              last_reason: null, collector_running: true },
    persistence: { loaded_from: 'demo', corrupt_moved_to: null, last_write_utc: null, last_write_error: null },
    note: null,
  };
}

function system(): SystemDiagnostics {
  return {
    model: 'Demo adapter (no hardware)', kernel: 'demo', uptime_s: 7 * 86400 + 4000, load: [0.14, 0.12, 0.09],
    mem: { total_mb: 4096, available_mb: 3284, used_pct: 20 }, disk: { total_gb: 64, free_gb: 49.8, used_pct: 22 },
    cpu_mhz: 1500, core_volts: null, power: null,
    // sample: under-voltage and throttling latched since boot, nothing now (get_throttled=0x50000)
    throttled: { raw: '0x50000', any_now: false, any_ever: true, flags: [
      { label: 'Under-voltage now', active: false, now: true },
      { label: 'Frequency capped now', active: false, now: true },
      { label: 'Throttled now', active: false, now: true },
      { label: 'Soft temp limit now', active: false, now: true },
      { label: 'Under-voltage occurred since boot', active: true, now: false },
      { label: 'Frequency capped since boot', active: false, now: false },
      { label: 'Throttled since boot', active: true, now: false },
      { label: 'Soft temp limit since boot', active: false, now: false },
    ] },
    power_note: 'Sample diagnostics from the demo adapter.',
    ramlog: { path: '/run/chrony-log/tracking.log', in_ram: true, size_kb: 84.2, flushed_age_s: 723 },
  };
}

function almanac(tz = 'UTC', date?: string, target?: string): Almanac {
  // Fixed sample times for the demo site on the requested date (default today), as UTC−4 instants.
  const day = date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : new Date().toISOString().slice(0, 10);
  const base = Date.parse(`${day}T00:00:00-04:00`);
  const ymd = (off: number) => new Date(base + 12 * 3600e3 + off * 86400e3).toISOString().slice(0, 10);
  const at = (off: number, hhmmss: string) => `${ymd(off)}T${hhmmss}-04:00`;
  const ms = (iso: string) => Date.parse(iso);
  const ev = { astro_dawn: at(0, '05:21:10'), naut_dawn: at(0, '05:51:40'), civil_dawn: at(0, '06:21:02'), sunrise: at(0, '06:48:04'),
               sunset: at(0, '18:48:24'), civil_dusk: at(0, '19:15:30'), naut_dusk: at(0, '19:44:58'), astro_dusk: at(0, '20:15:20') };
  const order: [number, string][] = [[0, at(0, '00:00:00')], [1, ev.astro_dawn], [2, ev.naut_dawn], [3, ev.civil_dawn], [4, ev.sunrise],
                                     [3, ev.sunset], [2, ev.civil_dusk], [1, ev.naut_dusk], [0, ev.astro_dusk], [-1, at(1, '00:00:00')]];
  const bar = order.slice(0, -1).map(([state, t0], i) => ({ state, start: t0, frac: (ms(order[i + 1][1]) - ms(t0)) / 86400e3 }));
  const n0 = ms(ev.sunset), n1 = ms(at(1, '06:49:00')), span = (n1 - n0) / 1000;
  const f = (iso: string) => (ms(iso) - n0) / (n1 - n0);
  const moonset = at(1, '01:33:00'), darkEnd = at(1, '05:22:00');
  return {
    available: true, demo: true,
    sun: { available: true, date: day, tz, events: ev, noon: at(0, '12:48:19'), daylight_s: 43220, bar, notes: [] },
    moon: { available: true, phase: 'Waxing gibbous', illum: 71, rise: at(0, '14:22:00'), set: moonset,
            transit: at(0, '19:51:00'), transit_alt: 48.0, age_days: 10.3, up_s: (ms(moonset) - ms(at(0, '14:22:00'))) / 1000 },
    night: {
      available: true, defined: true, sunset: ev.sunset, sunrise: at(1, '06:49:00'), span_s: span,
      sun_segments: [{ stage: 3, f0: 0, f1: f(ev.civil_dusk) }, { stage: 2, f0: f(ev.civil_dusk), f1: f(ev.naut_dusk) },
                     { stage: 1, f0: f(ev.naut_dusk), f1: f(ev.astro_dusk) }, { stage: 0, f0: f(ev.astro_dusk), f1: f(darkEnd) },
                     { stage: 1, f0: f(darkEnd), f1: f(at(1, '05:52:00')) }, { stage: 2, f0: f(at(1, '05:52:00')), f1: f(at(1, '06:22:00')) },
                     { stage: 3, f0: f(at(1, '06:22:00')), f1: 1 }],
      moon_up: [{ f0: 0, f1: f(moonset) }],
      dark: [{ f0: f(moonset), f1: f(darkEnd), start: moonset.slice(0, 16) + '-04:00', end: darkEnd.slice(0, 16) + '-04:00' }],
      dark_total_s: (ms(darkEnd) - ms(moonset)) / 1000,
      midnight: { f: f(at(1, '00:00:00')), label: `midnight · ${ymd(1).slice(8)}` }, astro_note: null, tz,
    },
    delta_yesterday: -131.3, delta_tomorrow: -132.1,
    neighbors: {
      yesterday: { sunrise: at(-1, '06:47:12'), sunset: at(-1, '18:49:43'), noon: at(-1, '12:48:33'), daylight_s: 43351 },
      tomorrow:  { sunrise: at(1, '06:48:57'), sunset: at(1, '18:47:05'), noon: at(1, '12:48:05'), daylight_s: 43088 },
    },
    sky: demoSky(target), sky_when: `${day} 22:00 ${tz}`, position_provenance: 'demo', position_age: null,
  };
}

// A small fixed sky for the client-side demo: a few bright stars (alt, az, mag), one
// asterism, two bodies, and the looked-up target at a fixed point. Shapes only.
function demoSky(target?: string): SkySnapshot {
  return {
    available: true, demo: true,
    stars: [[62, 300, 0.0], [48, 75, 1.3], [35, 230, 0.8], [70, 20, 2.1], [25, 120, 1.6], [55, 160, 2.4], [15, 330, 3.0], [40, 10, 3.5]],
    lines: [[[70, 20], [62, 300], [48, 75], [70, 20]]],
    bodies: { Moon: [22, 210], Jupiter: [30, 95] },
    target: target?.trim() ? [44, 60] : null,
  };
}

function demoObject(q: string, date?: string): ObjectReport {
  const day = date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : new Date().toISOString().slice(0, 10);
  const at = (off: number, hm: string) => `${new Date(Date.parse(`${day}T12:00:00Z`) + off * 86400e3).toISOString().slice(0, 10)}T${hm}-04:00`;
  return {
    available: true, demo: true, name: q.trim(), meta: 'demo object', emphasis: 'moonless', at_label: '22:00',
    now_alt: 44, now_az: 60, rise: at(0, '17:40'), transit: at(0, '23:55'), transit_alt: 72.3, set: at(1, '06:10'),
    circumpolar: false, never_up: false,
    dark_windows: [{ start: at(0, '20:15'), end: at(1, '05:21'), dur_s: 32760 }],
    moonless_windows: [{ start: at(1, '01:33'), end: at(1, '05:21'), dur_s: 13680 }],
    min_alt_deg: 15, tz: 'America/New_York',
  };
}

