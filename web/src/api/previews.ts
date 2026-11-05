// ============================================================
// PREVIEWS — synthetic content for features with NO station endpoint yet.
// ============================================================
// Rendered only through <Planned> (src/components/planned.tsx), which shows
// them when the data source is demo and otherwise says the feature is not
// available from this station. Nothing here is ever shown as a measurement.
// When a feature gets a real endpoint, add it to StationApi and delete it here.

// Holdover characterization (needs: oscillator model + validated holdover runs)
export const holdover = {
  rawOscillatorDrift: 8.4e-9,       // Δf/f change per second (s⁻¹)
  rawErrorIn1SecAfterDays: 1.4,
  trainedDrift: 0.31e-9,
  trainedErrorIn1SecAfterDays: 37.3,
  trainedConfidenceHours: 48,
  trainedValidatedHours: 72,
};

// Long-window PPS statistics (needs: event history rollups beyond events.recent)
export const ppsStats = {
  availabilityPct: 99.71,
  currentLockStreak: '13d 0h 24m',
  longestLock: '31d 7h 12m',
  lossEvents30d: 5,
  totalHoldoverH: 0.72,
  avgOutageDurationS: 342,
  medianOutageDurationS: 72,
  longestOutageDuration: '23m 07s',
  mtbf: '6d 2h',
  mttRecoveryS: 47,
};

// Outage recovery error (needs: offset measured at PPS reacquisition)
export const ppsOutages = [
  { date: 'Sep 10', duration: '23m 07s', durationS: 1387, errorNsOnRecovery: 210 },
  { date: 'Sep 13', duration:  '2m 41s', durationS: 161,  errorNsOnRecovery: 31  },
  { date: 'Sep 15', duration:    '58s',  durationS: 58,   errorNsOnRecovery: 12  },
  { date: 'Sep 19', duration:  '1m 12s', durationS: 72,   errorNsOnRecovery: 18  },
  { date: 'Sep 22', duration:    '34s',  durationS: 34,   errorNsOnRecovery: 8   },
];

// Timing error budget (needs: calibration records)
export const errorBudget = [
  { stage: 'GPS Satellite reference',    nominalNs:  20,  corrNs: 0,    uncertNs:  15, calibrated: true },
  { stage: 'Antenna cable delay',        nominalNs:  14.8,corrNs: 14.8, uncertNs: 0.5, calibrated: true },
  { stage: 'Receiver internal delay',    nominalNs:  10,  corrNs: 10,   uncertNs: 2.0, calibrated: false },
  { stage: 'PPS output jitter',          nominalNs:   5,  corrNs: 0,    uncertNs: 5.0, calibrated: false },
  { stage: 'HAT/GPIO input',             nominalNs:   2,  corrNs: 0,    uncertNs: 1.0, calibrated: false },
  { stage: 'Kernel / LinuxPPS',          nominalNs:  50,  corrNs: 0,    uncertNs: 30,  calibrated: false },
  { stage: 'Chrony clock discipline',    nominalNs:  12,  corrNs: 0,    uncertNs:  8,  calibrated: false },
  { stage: 'System clock (application)', nominalNs: 100,  corrNs: 0,    uncertNs: 50,  calibrated: false },
];

// SDR devices (needs: SDR layer)
export const sdrDevices = [
  { id: 'RTL-0', name: 'RTL-SDR Blog V4', serial: '00000001', tuner: 'R820T2', service: 'ADS-B 1090', freqMHz: 1090,
    sampleRateMsps: 2.048, gain: 'AGC', antenna: 'FA 1090 MHz', tier: 2, tierLabel: 'Freq-calibrated', calibPpm: -1.8, state: 'active' },
  { id: 'RTL-1', name: 'RTL-SDR Blog V4', serial: '00000002', tuner: 'R820T2', service: 'UAT 978', freqMHz: 978,
    sampleRateMsps: 2.048, gain: 'AGC', antenna: 'UAT Antenna', tier: 2, tierLabel: 'Freq-calibrated', calibPpm: -2.1, state: 'active' },
  { id: 'RTL-2', name: 'RTL-SDR Blog V3', serial: '00000003', tuner: 'R860', service: 'WWV Monitor', freqMHz: 10,
    sampleRateMsps: 0.25, gain: 29.5, antenna: 'HF Long Wire', tier: 3, tierLabel: 'PPS/epoch-aligned', calibPpm: -1.2, state: 'active' },
];


// Offline data packs (needs: data-pack manifest)
export const dataPacks = [
  { name: 'Core',           version: '2024.09.1', size: '12 MB',  installed: '2024-09-01', validThru: '2025-09-01', state: 'current' },
  { name: 'Astronomy',      version: '2024.09.0', size: '88 MB',  installed: '2024-09-01', validThru: '2025-01-01', state: 'current' },
  { name: 'Geoid (EGM2008)',version: '2012.01.0', size: '698 MB', installed: '2024-08-15', validThru: '2030-01-01', state: 'current' },
  { name: 'Leap Seconds',   version: '2024.06.0', size: '4 KB',   installed: '2024-06-30', validThru: '2024-12-28', state: 'current' },
  { name: 'Space Weather',  version: '—',          size: '—',      installed: '—',           validThru: '—',          state: 'unavail', note: 'Requires network' },
];
