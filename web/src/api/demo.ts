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
import type {
  Almanac, CoreStatus, DashboardConfig, DashboardLayout, DisplayZone, History, LocationMode, Measured, Satellite,
  Stability, StabilityPoint, Survey, SystemDiagnostics, TimingChain, TimingEvent, TimingStage,
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
    diagnostics: (o) => {
      const c = timingChain(o?.scenario);
      return delay(
        'GPS TIME PI DIAGNOSTIC SNAPSHOT (DEMO — synthetic data, not a measurement)\n' +
        `Generated: ${c.generated_utc}\n\nSTATUS: ${c.status.banner}\n  ${c.status.detail}\n` +
        `PPS state: ${c.pps_state.value}\nSelected source: ${c.chrony.selected?.name ?? 'none'}\n`);
    },
    dashboard: () => delay({ ...layout, _meta: { writable: true, auth_required: false, demo: true, path: null, known_widgets: KNOWN_WIDGETS } } as DashboardConfig),
    saveDashboard: (l) => { layout = l; return delay({ ok: true as const, dashboard: l }); },
    resetDashboard: () => { layout = defaultLayout(); return delay({ ok: true as const, dashboard: layout }); },
    setLocationDisplay: (mode) => { locationMode = mode; return delay({ ok: true as const, location_display: mode }); },
    setTimezone: (tz) => { tzOverride = tz || null; return delay({ ok: true as const, timezone: tzOverride }); },
    resetSite: () => delay({ ok: true as const, reset_site: true as const }),
    admin: (action) => delay({ ok: true, action, simulated: true as const, detail: `demo adapter: ${action} was not executed` }),
    auth: () => delay({ demo: true, auth_required: false, admin_configured: false, authenticated: true }),
    token: tokenStore(null),
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
    return { t, offset_s: 12e-9 + Math.sin(i * 0.15) * 6e-9 + noise(i) * 10e-9 + spike, err_s: 4e-9 + Math.abs(noise(i + 7)) * 4e-9 };
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
      yesterday: { sunrise: at(-1, '06:47:12'), sunset: at(-1, '18:49:43'), noon: at(-1, '12:48:33'), daylight_s: 43351 },
      tomorrow:  { sunrise: at(1, '06:48:57'), sunset: at(1, '18:47:05'), noon: at(1, '12:48:05'), daylight_s: 43088 },
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
