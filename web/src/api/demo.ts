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

import type { StationApi } from './client';
import type {
  Almanac, CoreStatus, DashboardConfig, DashboardLayout, History, LocationMode, Measured, Satellite,
  Survey, SystemDiagnostics, TimingChain, TimingEvent, TimingStage,
} from './types';

const SITE = { lat: 38.9217, lon: -77.0669, alt_msl: 92.0, alt_hae: 59.0 };

const m = <T,>(value: T, unit: string | null, provenance: Measured['provenance'], note?: string): Measured<T> =>
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
  let layout: DashboardLayout = defaultLayout();
  const delay = <T,>(v: T) => new Promise<T>(res => setTimeout(() => res(v), 60));

  function displayed() {
    if (locationMode === 'hidden') return { mode: locationMode, lat: null, lon: null };
    if (locationMode === 'rounded') {
      return { mode: locationMode, lat: Math.round(SITE.lat * 10) / 10, lon: Math.round(SITE.lon * 10) / 10,
               alt_msl: Math.round(SITE.alt_msl / 10) * 10 };
    }
    return { mode: locationMode, ...SITE };
  }

  return {
    source: 'demo',
    core: () => delay({ ...core(displayed()), ...(locationMode === 'hidden' ? { sidereal: null } : {}) }),
    timingChain: () => delay(timingChain()),
    history: () => delay(history()),
    survey: () => delay(survey()),
    system: () => delay(system()),
    // Mirrors the server: sun/moon/sky times reveal the position, so hidden mode computes none.
    almanac: (q) => delay(locationMode === 'hidden'
      ? { available: false as const, reason: "Location is hidden by the station's privacy setting. Sun, moon and sky times would reveal the station's position, so they are not computed.", location_display: 'hidden' as const }
      : { ...almanac(q?.tz), location_display: locationMode }),
    ping: () => {
      const t = Date.now();
      return delay({ server_receive_epoch_ms: t + 1.2, server_send_epoch_ms: t + 1.3 });
    },
    diagnostics: () => delay(
      'GPS TIME PI DIAGNOSTIC SNAPSHOT (DEMO — synthetic data, not a measurement)\n' +
      `Generated: ${iso(Date.now())}\n\nSTATUS: SYNCHRONIZED · GPS/PPS · STRATUM 1\nPPS state: SELECTED\n`),
    dashboard: () => delay({ ...layout, _meta: { writable: true, demo: true, path: null, known_widgets: KNOWN_WIDGETS } } as DashboardConfig),
    saveDashboard: (l) => { layout = l; return delay({ ok: true as const, dashboard: l }); },
    resetDashboard: () => { layout = defaultLayout(); return delay({ ok: true as const, dashboard: layout }); },
    setLocationDisplay: (mode) => { locationMode = mode; return delay({ ok: true as const, location_display: mode }); },
    resetSite: () => delay({ ok: true as const, reset_site: true as const }),
    admin: (action) => delay({ ok: false, action, detail: 'demo adapter: no action performed' }),
  };
}

// ─── payload builders ────────────────────────────────────────────────────────

function core(location: CoreStatus['location']): CoreStatus {
  const now = Date.now();
  const sys = 12.3e-9 + noise(Math.floor(now / 4000)) * 6e-9;
  return {
    demo: true,
    epoch_ms: now,
    utc: new Date(now).toISOString().replace('T', ' ').replace('Z', ' UTC'),
    state: ['SYNCHRONIZED', 'SYNCHRONIZED · GPS/PPS · STRATUM 1 — PPS refclock GPS selected by chrony.'],
    quality: {
      system_time_s: sys, last_offset_s: 1.18e-8, rms_offset_s: 1.87e-8, root_delay_s: 1e-9,
      root_dispersion_s: 4.1e-9, frequency: '1.240 ppm slow', frequency_ppm: -1.24,
      residual_freq: '-0.003 ppm', skew: '0.018 ppm', update_interval: '16.0 seconds',
      leap: 'Normal', stratum: '1', reference: 'GPS', ref_time: new Date(now).toUTCString(),
    },
    fmt: { system_pair: '12 ns fast ± 4 ns', rms: '19 ns', root_dispersion: '4 ns', root_delay: '1 ns' },
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
    astro_available: true,
    cpu_temp_c: 44.2,
    versions: { app: 'demo', chrony: 'chrony 4.x (sample)', gpsd: '3.x (sample)',
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

const STAGES: [string, string, TimingStage['status'], string][] = [
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

// Classifications/boundaries/confidence are copied from timing_chain.classify(); never invent causes.
function closedOutage(startMs: number, durationS: number, cls: string, boundary: string, confidence: string | null): TimingEvent {
  return {
    schema: 'gps-time.event/1', id: `pps-outage-${Math.floor(startMs / 1000)}`, type: 'PPS_OUTAGE',
    start_epoch: startMs / 1000, start_utc: iso(startMs), end_utc: iso(startMs + durationS * 1000),
    duration_s: durationS, open: false, severity: 'critical', classification: cls, initial_classification: cls,
    confidence, boundary, classification_provenance: 'inferred',
    evidence: {}, recovery: { pps_reselected: true }, notes: ['Demo event — synthetic.'],
  };
}

function timingChain(): TimingChain {
  const now = Date.now();
  const day = 86400000;
  return {
    schema: 'gps-time.timing-chain/1',
    generated_utc: iso(now),
    status: { code: 'GPS_PPS', headline: 'SYNCHRONIZED', banner: 'SYNCHRONIZED · GPS/PPS · STRATUM 1',
              detail: 'PPS refclock GPS selected by chrony.', source: { name: 'GPS', kind: 'refclock', stratum: '1' },
              gnss_healthy: true, provenance: 'calculated' },
    pps_state: m('SELECTED', null, 'calculated'),
    pps: {
      device: m('/dev/pps0', null, 'observed'), device_present: m(true, null, 'observed'),
      pulse_health: 'HEALTHY', pulse_health_provenance: 'calculated',
      measurement_layer: 'Linux kernel PPS timestamps (CLOCK_REALTIME)', note: null,
      last_event_utc: m(iso(now - (now % 1000)), null, 'observed'),
      age_s: m((now % 1000) / 1000, 's', 'calculated'), rate_hz: m(1.0, 'Hz', 'calculated'),
      missed_pulses: m(0, 'count', 'calculated'), consecutive_pulses: m(21, 'count', 'calculated'),
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
      pps_status: 'SELECTED', nmea_status: 'OK', pps: null, nmea: null,
      selected: { name: 'GPS', kind: 'refclock', stratum: 0, is_pps: true, is_nmea: false },
      any_selected: true,
      tracking: { leap: 'Normal', stratum: '1', reference: 'GPS',
                  system_time_s: m(12.3e-9, 's', 'observed', "chrony's remaining correction, not an independent measurement"),
                  root_delay_s: m(1e-9, 's', 'observed'), root_dispersion_s: m(4.1e-9, 's', 'observed'),
                  frequency: '1.240 ppm slow' },
    },
    classification: null,
    stages: STAGES.map(([id, label, status, summary]) => ({ id, label, status, summary, evidence: {} })),
    events: {
      open: null,
      recent: [
        closedOutage(now - 2.1 * day, 34, 'PPS PATH ANOMALY', 'receiver PPS output / GPIO / kernel PPS interface', 'moderate'),
        closedOutage(now - 5.4 * day, 72, 'GNSS RECEPTION ANOMALY', 'GNSS reception / receiver solution', 'low'),
        closedOutage(now - 9.0 * day, 1387, 'PPS AND GNSS TELEMETRY UNAVAILABLE', 'unknown', 'low'),
      ],
    },
    boot: { phase: 'RUN', boot_utc: iso(now - 7 * day), since_boot_s: m(7 * 86400, 's', 'calculated'),
            pps_selected_this_boot: true },
    raw: { tracking: 'Reference ID    : 47505300 (GPS)\nStratum         : 1\n(demo)', sources: '(demo)', sourcestats: '(demo)' },
    demo: { scenario: 'pps_selected', description: 'Normal: PPS selected by chrony (client-side demo adapter)',
            scenarios: ['pps_selected'], note: 'synthetic data — not a measurement' },
  };
}

function history(): History {
  // 7 days at 10-minute spacing, with one brief excursion.
  const now = Date.now() / 1000;
  const n = 7 * 144;
  const points = Array.from({ length: n }, (_, i) => {
    const t = now - (n - i) * 600;
    const spike = i === n - 300 ? 180e-9 : 0;
    return { t, offset_s: 12e-9 + Math.sin(i * 0.15) * 6e-9 + noise(i) * 10e-9 + spike, err_s: 4e-9 + Math.abs(noise(i + 7)) * 4e-9 };
  });
  return { available: true, points, note: 'demo adapter sample data' };
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
    cpu_mhz: 1500, core_volts: null, throttled: null, power: null,
    power_note: 'Sample diagnostics from the demo adapter.',
    ramlog: { path: '/run/chrony-log/tracking.log', in_ram: true, size_kb: 84.2, flushed_age_s: 723 },
  };
}

function almanac(tz = 'UTC'): Almanac {
  // Fixed sample times for the demo site, expressed as UTC instants (EDT = UTC−4).
  const today = new Date();
  const ymd = (off: number) => {
    const d = new Date(today.getTime() + off * 86400000);
    return d.toISOString().slice(0, 10);
  };
  const at = (off: number, hhmmss: string) => `${ymd(off)}T${hhmmss}-04:00`;
  return {
    available: true, demo: true,
    sun: { available: true, date: ymd(0), tz, events: { sunrise: at(0, '06:48:04'), sunset: at(0, '18:48:24') },
           noon: at(0, '12:48:19'), daylight_s: 43220, bar: [], notes: [] },
    moon: { available: true, phase: 'Waxing gibbous', illum: 71, rise: at(0, '14:22:00'), set: at(1, '01:33:00'),
            transit: at(0, '19:51:00'), transit_alt: 48.0, age_days: 10.3 },
    night: { available: true, defined: false },
    delta_yesterday: -131.3, delta_tomorrow: -132.1,
    neighbors: {
      yesterday: { sunrise: at(-1, '06:47:12'), sunset: at(-1, '18:49:43'), daylight_s: 43351 },
      tomorrow:  { sunrise: at(1, '06:48:57'), sunset: at(1, '18:47:05'), daylight_s: 43088 },
    },
    sky: {}, sky_when: `${ymd(0)} 22:00 ${tz}`, position_provenance: 'demo', position_age: null,
  };
}

const KNOWN_WIDGETS = ['adsb', 'distributed', 'gnss', 'network', 'ntp_clients', 'satellites', 'sdr', 'sources',
                       'sun', 'time', 'timing_quality', 'transits'];

function defaultLayout(): DashboardLayout {
  return {
    schema_version: 1, title: 'GPS Time (demo)',
    pages: [{ id: 'overview', title: 'Overview', widgets: [
      { id: 'time', visible: true, size: 'wide' }, { id: 'timing_quality', visible: true, size: 'normal' },
      { id: 'sun', visible: true, size: 'normal' }, { id: 'gnss', visible: true, size: 'normal' },
    ] }],
  };
}
