import { describe, expect, it } from 'vitest';
import type { OscillatorBin } from '../api/types';
import { dayTicks, fitLine, fmtBytes, fmtSlope, oscPoints, scatterPoints, spanDays, fmtTerm, profileAt, profileCurve, bindingFor, demoImport, exportFilename, fmtHoldTime, fmtThreshold, holdoverRows, holdoverTimes, importOutcome } from './oscillator';
import { demoApi } from '../api/demo';

const bin = (t: string, temp: number | null, freq: number | null, pps = 10): OscillatorBin => ({
  t, samples: 10, pps_samples: pps, temp_mean_c: temp, temp_min_c: temp, temp_max_c: temp,
  freq_mean_ppm: freq, freq_min_ppm: freq, freq_max_ppm: freq, skew_mean_ppm: 0.008, residual_mean_ppm: 0,
});

describe('oscillator helpers', () => {
  const bins = [bin('2026-10-19T10:00:00+00:00', 50, 10.3), bin('2026-10-19T10:10:00+00:00', 52, 9.8, 4),
                bin('2026-10-19T10:20:00+00:00', null, 10.0)];

  it('points keep missing values as null and mark partial-PPS bins', () => {
    const p = oscPoints(bins);
    expect(p.map(x => x.pps)).toEqual([true, false, true]);
    expect(p[2].temp).toBeNull();
    expect(oscPoints(undefined)).toEqual([]);
  });

  it('scatter uses complete points, optionally PPS-only', () => {
    const p = oscPoints(bins);
    expect(scatterPoints(p, false)).toEqual([{ x: 50, y: 10.3 }, { x: 52, y: 9.8 }]);
    expect(scatterPoints(p, true)).toEqual([{ x: 50, y: 10.3 }]);
  });

  it('fit line only with a fit', () => {
    const fit = { bins_used: 40, slope_ppm_per_c: -0.25, intercept_ppm: 22.8, r: -0.99, temp_span_c: 6, reason: null, provenance: 'calculated' as const };
    expect(fitLine(fit, [{ x: 50 }, { x: 54 }])).toEqual([{ x: 50, y: 10.3 }, { x: 54, y: 9.3 }]);
    expect(fitLine({ ...fit, slope_ppm_per_c: null }, [{ x: 50 }, { x: 54 }])).toEqual([]);
    expect(fitLine(fit, [{ x: 50 }])).toEqual([]);
  });

  it('labels', () => {
    expect(fmtSlope(-0.25)).toBe('−0.250 ppm/°C');
    expect(fmtSlope(0.0123)).toBe('+0.012 ppm/°C');
    expect(fmtSlope(null)).toBeNull();
    expect([500, 24727, 4194304].map(fmtBytes)).toEqual(['500 B', '24 kB', '4.0 MB']);
    expect(spanDays(oscPoints(bins))).toBeCloseTo(20 / 1440, 6);
    expect(spanDays([])).toBeNull();
  });

  it('demo adapter: observed bins and a calculated slope', async () => {
    const r = await demoApi().oscillator();
    expect(r.available).toBe(true);
    expect(r.provenance).toBe('observed');
    expect(r.fit.provenance).toBe('calculated');
    expect(r.fit.slope_ppm_per_c).toBeCloseTo(-0.3, 1);
    expect(r.bins.length).toBeGreaterThan(100);
  });
});

describe('oscillator profile', () => {
  const base = {
    status: 'fitted' as const, reason: null, provenance: 'modeled' as const, model: 'quadratic+aging' as const,
    terms: [{ name: 'a' as const, value: 10, se: 0.001, unit: 'ppm' }, { name: 'b' as const, value: -0.3, se: 0.0001, unit: 'ppm/°C' },
            { name: 'c' as const, value: 0.002, se: 0.0001, unit: 'ppm/°C²' }, { name: 'd' as const, value: 0.01, se: 0.001, unit: 'ppm/day' }],
    bins_used: 500, outliers: 0, residual_rms_ppm: 0.001, r2: 0.999, temp_ref_c: 50, t0_utc: '', t0_utc_epoch: 0,
    covers: { temp_min_c: 44, temp_max_c: 56, first_utc: '', last_utc: '', first_utc_epoch: 0, last_utc_epoch: 2 * 86400, days: 2 },
    candidates: [], note: '',
  };
  it('evaluates at the end of the span', () => {
    expect(profileAt(base, 50)).toBeCloseTo(10 + 0.02, 6);
    expect(profileAt(base, 52)).toBeCloseTo(10 - 0.6 + 0.008 + 0.02, 6);
    expect(profileAt({ ...base, status: 'insufficient' }, 50)).toBeNull();
  });
  it('draws only over the covered temperatures', () => {
    const c = profileCurve(base, 4);
    expect(c.map(p => p.x)).toEqual([44, 47, 50, 53, 56]);
    expect(profileCurve(undefined)).toEqual([]);
  });
  it('shows terms as Δf/f with ppm in brackets', () => {
    expect(fmtTerm(base.terms[1])).toEqual({ label: 'Temperature coefficient', text: '−3 × 10⁻⁷ ± 1 × 10⁻¹⁰ per °C (−0.3000 ppm/°C)' });
    expect(fmtTerm(base.terms[3]).text).toContain('per day');
  });
});

describe('holdover projections', () => {
  it('matches the review numbers (GPS-008)', () => {
    const t = holdoverTimes([1e-6, 1e-3, 1], 2.14);
    expect(t[0]).toBeCloseTo(0.467, 3);
    expect((t[2] as number) / 86400).toBeCloseTo(5.41, 2);
    const trained = holdoverTimes([1e-6, 1e-3], 0.018);
    expect(trained[0]).toBeCloseTo(55.6, 1);
    expect((trained[1] as number) / 3600).toBeCloseTo(15.4, 1);
    expect(holdoverTimes([1], 0)).toEqual([null]);
  });
  it('aging makes it sooner, and solves the quadratic', () => {
    const [t] = holdoverTimes([1], 0.25, 0.05);
    const r = 0.25e-6, a = 0.05e-6 / 86400;
    expect(t as number).toBeLessThan(1 / r);
    expect(r * (t as number) + a * (t as number) ** 2 / 2).toBeCloseTo(1, 9);
  });
  it('formats durations and thresholds', () => {
    expect(fmtHoldTime(0.467)).toBe('0.47 s');
    expect(fmtHoldTime(55.6)).toBe('56 s');
    expect(fmtHoldTime(1500)).toBe('25 min');
    expect(fmtHoldTime(15.4 * 3600)).toBe('15 h');
    expect(fmtHoldTime(5.41 * 86400)).toBe('5.4 d');
    expect(fmtHoldTime(4 * 365.25 * 86400)).toBe('4.0 yr');
    expect(fmtHoldTime(null)).toBe('not reached');
    expect([1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1].map(fmtThreshold))
      .toEqual(['±1 µs', '±10 µs', '±100 µs', '±1 ms', '±10 ms', '±100 ms', '±1 s']);
  });
  it('rows show a dash for an unavailable projection, never a number', () => {
    const h = {
      provenance: 'modeled' as const, thresholds_s: [1e-6], sample_utc: null, note: '',
      projections: [
        { name: 'free_running' as const, provenance: 'modeled' as const, available: true, rate_ppm: 2.14, aging_ppm_per_day: 0, times_s: [0.467] },
        { name: 'profile' as const, provenance: 'modeled' as const, available: false, reason: 'no fit', rate_ppm: null, aging_ppm_per_day: 0, times_s: [null] },
      ],
    };
    expect(holdoverRows(h)).toEqual([{ threshold: '±1 µs', cells: [{ name: 'free_running', text: '0.47 s' }, { name: 'profile', text: '—' }] }]);
    expect(holdoverRows(undefined)).toEqual([]);
  });
});

describe('profile file', () => {
  const doc = { format: 'gps-time-oscillator-profile/1', board: { serial_sha256: 'a1b2c3d4e5f60718' },
                fit_bins: { rows: [[1793000000, 45, 10]] } };
  it('binds by serial hash', () => {
    expect(bindingFor('a1b2c3d4e5f60718', 'a1b2c3d4e5f60718')).toBe('match');
    expect(bindingFor('0f0e0d0c0b0a0908', 'a1b2c3d4e5f60718')).toBe('mismatch');
    expect(bindingFor(null, 'a1b2c3d4e5f60718')).toBe('unverifiable');
    expect(bindingFor('a1b2c3d4e5f60718', null)).toBe('unverifiable');
    expect(bindingFor('demo', 'demo')).toBe('unverifiable');
  });
  it('demo import mirrors the station and saves nothing', () => {
    const same = demoImport(doc, 'a1b2c3d4e5f60718');
    expect(same).toMatchObject({ ok: true, binding: 'match', used: true, simulated: true, bins: 1 });
    expect(demoImport(doc, '0f0e0d0c0b0a0908')).toMatchObject({ ok: true, binding: 'mismatch', used: false });
    expect(demoImport({ format: 'x' }, null).ok).toBe(false);
    expect(demoImport({ ...doc, fit_bins: { rows: [[1, 2]] } }, null).ok).toBe(false);
    expect(importOutcome(same).text).toContain('nothing was saved');
    expect(importOutcome({ ok: false, error: 'admin token required' })).toEqual({ ok: false, text: 'Not imported: admin token required.' });
  });
  it('names the download by date', () => {
    expect(exportFilename({ exported_utc: '2026-10-26T18:00:00+00:00' })).toBe('oscillator-profile-2026-10-26.json');
    expect(exportFilename({})).toBe('oscillator-profile.json');
  });
});

describe('demo adapter', () => {
  it('a demo export imports as the same board, simulated', async () => {
    const api = demoApi();
    const doc = await api.oscillatorExport();
    expect(doc.fit_bins.rows.length).toBeGreaterThan(0);
    expect(JSON.stringify(doc)).not.toMatch(/"lat"|"lon"/);
    expect(await api.oscillatorImport(doc)).toMatchObject({ ok: true, binding: 'match', simulated: true });
    const o = await api.oscillator();
    expect(o.holdover.projections.map(p => p.name)).toEqual(['free_running', 'trained_skew', 'profile']);
    expect(o.holdover.projections.every(p => p.provenance === 'modeled')).toBe(true);
  });
});

describe('dayTicks', () => {
  it('one tick per local midnight inside the span, never a repeated date', () => {
    const t0 = new Date(2026, 9, 24, 15, 0).getTime(), t1 = new Date(2026, 9, 27, 3, 0).getTime();
    const ticks = dayTicks(t0, t1);
    expect(ticks.map(t => new Date(t).getDate())).toEqual([25, 26, 27]);
    expect(ticks.every(t => new Date(t).getHours() === 0)).toBe(true);
    const long = dayTicks(new Date(2026, 9, 1).getTime(), new Date(2026, 9, 30).getTime());
    expect(long.length).toBeLessThanOrEqual(7);
    expect(new Set(long.map(t => new Date(t).toDateString())).size).toBe(long.length);
    expect(dayTicks(5, 5)).toEqual([]);
  });
});
