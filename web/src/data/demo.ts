// ============================================================
// DEMO DATA — All values are synthetic for demonstration only
// ============================================================

export const DEMO = true;
export const STATION_NAME = 'ATLAS-01';
export const STATION_LAT = 37.422004;
export const STATION_LON = -122.084056;
export const STATION_ALT_ELLIP = 28.4; // meters, ellipsoidal
export const STATION_ALT_ORTHO = -5.1; // meters, orthometric
export const STATION_GEOID_N = 33.5; // geoid undulation

// Current timing state
export const timing = {
  offsetNs: 12.3,
  offsetUncertaintyNs: 4.1,
  rms24hNs: 18.7,
  fracFreqOffset: -1.24e-9, // dimensionless
  fracFreqOffsetPpm: -0.00124,
  lightDistM: 3.69, // meters (12.3 ns × 0.3 m/ns)
  refSource: 'GPS/PPS',
  ppsState: 'LOCKED' as 'LOCKED'|'HOLDOVER'|'NETWORK'|'UNSYNC',
  stratum: 1,
  lockDurationH: 312.4, // hours continuous PPS lock
  ntp: {
    clients: 7,
    requestRate: 23, // req/min
  }
};

// Holdover estimates
export const holdover = {
  rawOscillatorDriftPpb: 8.4,      // ppb/s
  rawErrorIn1SecAfterDays: 1.4,     // days
  trainedDriftPpb: 0.31,
  trainedErrorIn1SecAfterDays: 37.3,
  trainedConfidenceHours: 48,
  trainedValidatedHours: 72,
};

// GNSS satellites (demo)
export const satellites = [
  { sys:'GPS',  svid:'G01', az:42,  el:67, cn0:47, state:'used',    sig:'L1CA' },
  { sys:'GPS',  svid:'G07', az:118, el:33, cn0:39, state:'used',    sig:'L1CA' },
  { sys:'GPS',  svid:'G11', az:215, el:45, cn0:43, state:'used',    sig:'L1CA' },
  { sys:'GPS',  svid:'G17', az:290, el:22, cn0:35, state:'tracked', sig:'L1CA' },
  { sys:'GPS',  svid:'G20', az:163, el:58, cn0:45, state:'used',    sig:'L1CA' },
  { sys:'GPS',  svid:'G28', az:332, el:12, cn0:28, state:'tracked', sig:'L1CA' },
  { sys:'GLONASS', svid:'R04', az:78, el:41, cn0:41, state:'used',  sig:'G1'  },
  { sys:'GLONASS', svid:'R13', az:240,el:36, cn0:38, state:'used',  sig:'G1'  },
  { sys:'GALILEO', svid:'E03', az:55, el:29, cn0:36, state:'used',  sig:'E1'  },
  { sys:'GALILEO', svid:'E11', az:185,el:52, cn0:44, state:'used',  sig:'E1'  },
  { sys:'GALILEO', svid:'E19', az:310,el:19, cn0:30, state:'tracked',sig:'E1' },
  { sys:'BEIDOU', svid:'C06', az:145,el:61, cn0:46, state:'used',  sig:'B1'  },
];

// Offset time series (1 hour, 60 points)
const now = Date.now();
export function generateOffsetSeries(points: number, rangeMs: number, baseNs = 12, noiseSigma = 8) {
  return Array.from({ length: points }, (_, i) => {
    const t = now - rangeMs + (i / points) * rangeMs;
    // Simulate realistic Δt
    const drift = Math.sin(i * 0.15) * 6;
    const noise = (Math.random() - 0.5) * noiseSigma;
    const anomaly = (i === 22 || i === 23) ? 180 : 0; // brief holdover spike
    return {
      t: new Date(t).toISOString(),
      ts: t,
      dt: baseNs + drift + noise + anomaly,
    };
  });
}

export const offset1h  = generateOffsetSeries(60,  3600_000, 12, 5);
export const offset24h = generateOffsetSeries(288, 86400_000, 12, 12);
export const offset7d  = generateOffsetSeries(168, 7*86400_000, 12, 20);

// PPS outage events
export const ppsOutages = [
  { date: 'Sep 10', duration: '23m 07s', durationS: 1387, errorNsOnRecovery: 210 },
  { date: 'Sep 13', duration:  '2m 41s', durationS: 161,  errorNsOnRecovery: 31  },
  { date: 'Sep 15', duration:    '58s',  durationS: 58,   errorNsOnRecovery: 12  },
  { date: 'Sep 19', duration:  '1m 12s', durationS: 72,   errorNsOnRecovery: 18  },
  { date: 'Sep 22', duration:    '34s',  durationS: 34,   errorNsOnRecovery: 8   },
];

// PPS stats
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

// NTP clients
export const ntpClients = [
  { ip: '192.168.1.12', firstSeen: '2024-08-01', lastPoll: '2s ago',  count: 182341, interval: '64s',  state: 'active' },
  { ip: '192.168.1.25', firstSeen: '2024-09-01', lastPoll: '18s ago', count: 44821,  interval: '128s', state: 'active' },
  { ip: '10.0.0.5',     firstSeen: '2024-09-10', lastPoll: '2m ago',  count: 9341,   interval: '256s', state: 'recent' },
  { ip: '10.0.0.8',     firstSeen: '2024-09-15', lastPoll: '7m ago',  count: 4102,   interval: '256s', state: 'recent' },
  { ip: '192.168.2.44', firstSeen: '2024-09-20', lastPoll: '1h ago',  count: 891,    interval: '1024s',state: 'stale'  },
  { ip: '192.168.2.51', firstSeen: '2024-09-22', lastPoll: '4h ago',  count: 112,    interval: '1024s',state: 'stale'  },
  { ip: '10.0.1.3',     firstSeen: '2024-09-27', lastPoll: '9m ago',  count: 43,     interval: '256s', state: 'recent' },
];

// Sun data
export const sunData = {
  yesterday: { rise:'06:47:12', noon:'12:48:31', set:'18:49:43', duration:'12h 02m 31s' },
  today:     { rise:'06:48:04', noon:'12:48:19', set:'18:48:24', duration:'12h 00m 20s', change:'-2m 11.3s' },
  tomorrow:  { rise:'06:48:57', noon:'12:48:07', set:'18:47:05', duration:'11h 58m 08s', change:'-2m 12.1s' },
  solarElevation: 38.4,
  solarAzimuth: 187.2,
  apparentSolarTime: '12:33:14',
  equationOfTimeMin: -9.8,
};

// Moon data
export const moonData = {
  phase: 'Waxing Gibbous',
  illumination: 0.71,
  age: 10.3,
  rise: '14:22',
  transit: '19:51',
  set: '01:33',
};

// SDR devices
export const sdrDevices = [
  {
    id: 'RTL-0',
    name: 'RTL-SDR Blog V4',
    serial: '00000001',
    tuner: 'R820T2',
    service: 'ADS-B 1090',
    freqMHz: 1090,
    sampleRateMsps: 2.048,
    gain: 'AGC',
    antenna: 'FA 1090 MHz',
    tier: 2,
    tierLabel: 'Freq-calibrated',
    calibPpm: -1.8,
    state: 'active',
  },
  {
    id: 'RTL-1',
    name: 'RTL-SDR Blog V4',
    serial: '00000002',
    tuner: 'R820T2',
    service: 'UAT 978',
    freqMHz: 978,
    sampleRateMsps: 2.048,
    gain: 'AGC',
    antenna: 'UAT Antenna',
    tier: 2,
    tierLabel: 'Freq-calibrated',
    calibPpm: -2.1,
    state: 'active',
  },
  {
    id: 'RTL-2',
    name: 'RTL-SDR Blog V3',
    serial: '00000003',
    tuner: 'R860',
    service: 'WWV Monitor',
    freqMHz: 10,
    sampleRateMsps: 0.25,
    gain: 29.5,
    antenna: 'HF Long Wire',
    tier: 3,
    tierLabel: 'PPS/epoch-aligned',
    calibPpm: -1.2,
    state: 'active',
  },
];

// ADS-B stats
export const adsbStats = {
  msgsPerSec: 142,
  aircraftCount: 23,
  maxRangeKm: 412,
  mlatPeers: 4,
  mlatPositions: 6,
};

// Data packs
export const dataPacks = [
  { name: 'Core',           version: '2024.09.1', size: '12 MB',  installed: '2024-09-01', validThru: '2025-09-01', state: 'current' },
  { name: 'Astronomy',      version: '2024.09.0', size: '88 MB',  installed: '2024-09-01', validThru: '2025-01-01', state: 'current' },
  { name: 'Geoid (EGM2008)',version: '2012.01.0', size: '698 MB', installed: '2024-08-15', validThru: '2030-01-01', state: 'current' },
  { name: 'Leap Seconds',   version: '2024.06.0', size: '4 KB',   installed: '2024-06-30', validThru: '2024-12-28', state: 'current' },
  { name: 'Space Weather',  version: '—',          size: '—',      installed: '—',           validThru: '—',          state: 'unavail', note: 'Requires network' },
];

// Error budget
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
