// Demo answers for /api/sky-obstruction and /api/capability, in the station's shapes
// (gps_time_pi/demo.py sky_map, capability.py). Synthetic: a western obstruction below
// about 30° (240–310°) and a weaker band to the south-east. Always under the demo banner.
import type { Capability, LocationMode, SkyCell, SkyCellClass, SkyLoss, SkyObstruction, SkySector } from './types';

const AZ = 10, EL = 5;

function cells(): SkyCell[] {
  const out: SkyCell[] = [];
  for (let ai = 0; ai < 36; ai++) {
    const az = ai * AZ + 5;
    for (let ei = 1; ei < 18; ei++) {
      const el = ei * EL + 2.5;
      if (el > 62 && (az > 320 || az < 40)) continue;           // the orbits' northern hole
      const band = 30 + 16 * Math.sin(el * Math.PI / 180);
      let cn0 = band + (((ai * 7 + ei * 13) % 5) - 2) * 0.6, tracked = 97, cls: SkyCellClass = 'clear';
      if (az >= 240 && az <= 310 && el < 30) { cn0 -= 11; tracked = 35; cls = 'blocked'; }
      else if (az >= 120 && az <= 150 && el >= 10 && el < 20) { cn0 -= 5; tracked = 75; cls = 'attenuated'; }
      const r = (x: number) => Math.round(x * 10) / 10;
      out.push({ az0: ai * AZ, el0: ei * EL, samples: Math.round((120 + (ai * 37 + ei * 11) % 90) * tracked / 100),
        tracked_pct: tracked, used_pct: Math.round(tracked * 0.8), cn0_mean: r(cn0), cn0_sd: 2, band_median: r(band),
        delta_db: r(cn0 - band), class: cls });
    }
  }
  return out;
}

const SECTORS: [string, SkySector['state'], string, number | null][] = [
  ['N', 'clear', 'Mostly clear', null], ['NE', 'clear', 'Mostly clear', null], ['E', 'clear', 'Mostly clear', null],
  ['SE', 'attenuated', 'Intermittent attenuation 10–20°', null], ['S', 'clear', 'Mostly clear', null],
  ['SW', 'attenuated', 'Intermittent attenuation 5–30°', null], ['W', 'obstructed', 'Expected obstruction below ~30°', 30],
  ['NW', 'attenuated', 'Intermittent attenuation 5–30°', null],
];

function losses(now: number): SkyLoss[] {
  const rows: [string, number, number, number, SkyLoss['class'], string][] = [
    ['GPS', 9, 301, 3, 'SET', 'below 5°: the satellite set'],
    ['GLONASS', 3, 95, 41, 'NOT EXPLAINED', 'this direction is normally clear here; the map does not explain the loss'],
    ['GPS', 30, 133, 14, 'EXPECTED', 'expected environmental loss: this direction is normally attenuated here'],
    ['Galileo', 7, 251, 22, 'EXPECTED', 'expected environmental loss: this direction is normally blocked here'],
    ['GPS', 14, 272, 18, 'EXPECTED', 'expected environmental loss: this direction is normally blocked here'],
  ];
  return rows.map(([gnss, sat, az, el, cls, note], i) => ({
    utc: new Date(now - 40 * 60_000 * (i + 1)).toISOString().replace(/\.\d+Z$/, 'Z'), gnss, sat, az, el,
    cn0_before: 24, class: cls, note, provenance: 'inferred' as const }));
}

export function demoSkyObstruction(mode: LocationMode, now = Date.now()): SkyObstruction {
  const c = cells();
  const known = c.filter(x => x.class !== 'unknown');
  return {
    available: true, format: 'gps-time-sky-obstruction/1', az_step: AZ, el_step: EL,
    summary: { days: 12, satellite_minutes: c.reduce((a, x) => a + x.samples, 0), reports_sampled: 12 * 1440,
      cells_total: 648, cells_with_data: c.length, cells_classified: known.length,
      clear_pct: Math.round(100 * known.filter(x => x.class === 'clear').length / known.length),
      state: 'learned', untracked_reported: true },
    sectors: SECTORS.map(([sector, state, text, below], i) => ({ sector, az_centre: i * 45, state, text, below_deg: below,
      cells_classified: 70, cells: 70, cn0_median: state === 'obstructed' ? 32.5 : 41.2, provenance: 'inferred' as const })),
    cells: c,
    losses: { counts: { EXPECTED: 3, 'NOT EXPLAINED': 1, UNKNOWN: 0, SET: 1 }, recent: losses(now), since: 'service start' },
    sky_wide: { count: 0, recent: [] },
    thresholds: { min_cell_samples: 20, blocked_db: 8, attenuated_db: 4, blocked_tracked: 0.5, attenuated_tracked: 0.8, learned_days: 2 },
    file: { name: 'sky-obstruction.json', last_write_utc: new Date(now - 20 * 60_000).toISOString().replace(/\.\d+Z$/, 'Z'),
      unsaved: true, problems: [] },
    note: "Learned from this station's own satellites: each direction is compared with the rest of its elevation band. "
      + 'It is an RF horizon, not a physical survey of the sky, and it never says what blocks a signal.',
    provenance: 'inferred', location_display: mode,
  };
}

export function demoCapability(mode: LocationMode, share: boolean, version: string): Capability {
  const sky = demoSkyObstruction(mode);
  const quality = mode !== 'hidden' && share ? {
    state: sky.summary.state, days: sky.summary.days, clear_pct: sky.summary.clear_pct,
    cells_classified: sky.summary.cells_classified,
    sectors: sky.sectors.map(s => ({ sector: s.sector, state: s.state, below_deg: s.below_deg })),
    provenance: 'inferred' as const,
    note: "From the learned sky-obstruction map: an RF horizon relative to this station's own sky.",
  } : null;
  return {
    format: 'gps-time-capability/1', generated_utc: new Date().toISOString().replace(/\.\d+Z$/, 'Z'),
    station_id: null, software_version: version,
    timing: { state: 'GPS_PPS', source: 'PPS', provenance: 'calculated' },
    gnss: { driver: 'u-blox', firmware: 'MAX-M8Q sample' },
    sdr: { installed: true, receivers: [{ role: '1090 MHz' }] },
    location: mode === 'rounded' ? { precision: 'rounded (0.1°, about 11 km)', lat: 38.9, lon: -77.1 }
      : { precision: mode, lat: null, lon: null, note: mode === 'hidden' ? 'hidden by the privacy setting'
        : 'exact positions are never published in the capability record; choose rounded to share one' },
    sky_quality_opt_in: share,
    sky_quality: quality,
    sky_quality_note: quality ? null : mode === 'hidden' ? 'location privacy is hidden'
      : 'off (opt-in: POST /api/setting {"sky_quality_share": true})',
    availability: 'owner only',
  };
}

/** The diagnostics export's sky-quality lines (gps_time_pi/skymap.py diagnostic_lines). */
export function demoSkyLines(c: Capability): string {
  const q = c.sky_quality;
  if (!q) return `sky quality: not included (${c.sky_quality_note})\n`;
  return `sky quality (inferred): ${q.state}, ${q.days} days, clear ${q.clear_pct ?? 'UNKNOWN'} % of classified cells\n`
    + q.sectors.map(s => `  ${s.sector.padEnd(2)} ${s.state}${s.below_deg ? ` below ~${s.below_deg}°` : ''}`).join('\n') + '\n';
}
