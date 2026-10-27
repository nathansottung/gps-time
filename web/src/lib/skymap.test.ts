import { describe, expect, it } from 'vitest';
import type { SkyCell } from '../api/types';
import { demoApi } from '../api/demo';
import { demoSkyObstruction } from '../api/demoSky';
import { CN0_HI, CN0_LO, cellPath, cellShade, cellTitle, lossRows, lossTotals, lossVariant, sectorVariant, summaryLine } from './skymap';

const cell = (o: Partial<SkyCell> = {}): SkyCell => ({
  az0: 270, el0: 20, samples: 60, tracked_pct: 40, used_pct: 30, cn0_mean: 31.2, cn0_sd: 2, band_median: 42.1,
  delta_db: -10.9, class: 'blocked', ...o,
});

describe('sky obstruction map', () => {
  it('shades by the station class, or by C/N₀ on a fixed scale', () => {
    expect(cellShade(cell(), 'class').fill).toBe('var(--err-text)');
    expect(cellShade(cell({ class: 'clear' }), 'class').fill).toBe('var(--good-text)');
    expect(cellShade(cell({ class: 'unknown' }), 'class').opacity).toBeLessThan(0.2);
    const lo = cellShade(cell({ cn0_mean: CN0_LO - 5 }), 'cn0'), hi = cellShade(cell({ cn0_mean: CN0_HI + 5 }), 'cn0');
    expect(lo.opacity).toBe(0.08);
    expect(hi.opacity).toBe(0.7);
    expect(cellShade(cell({ cn0_mean: null }), 'cn0').fill).toBe('var(--t4)');
  });

  it('draws each cell as one annular sector and describes it', () => {
    expect(cellPath(cell(), 10, 5, 100, 100, 80)).toMatch(/^M.* A.* L.* A.* Z$/);
    expect(cellTitle(cell(), 10, 5)).toBe('270–280° az, 20–25° el: Blocked · 60 satellite-minutes · mean C/N₀ 31.2 dB-Hz (-10.9 dB against its elevation band) · tracked 40 %');
    expect(cellTitle(cell({ cn0_mean: null, tracked_pct: null, class: 'unknown' }), 10, 5)).toBe('270–280° az, 20–25° el: Not enough data · 60 satellite-minutes');
  });

  it('an expected loss is never a warning; one the map does not explain is', () => {
    expect(lossVariant('EXPECTED')).toBe('muted');
    expect(lossVariant('NOT EXPLAINED')).toBe('warn');
    expect(sectorVariant('obstructed')).toBe('error');
    expect(sectorVariant('unknown')).toBe('muted');
  });

  it('summary and loss rows from the station answer', () => {
    const m = demoSkyObstruction('exact', Date.parse('2026-10-27T12:00:00Z'));
    expect(summaryLine(m).text).toMatch(/^Learned over 12 days: \d+ % of classified cells clear$/);
    expect(summaryLine({ ...m, summary: { ...m.summary, state: 'learning', days: 1 } }).text).toMatch(/^Learning: 1 day so far \(2 needed\)/);
    expect(summaryLine({ ...m, summary: { ...m.summary, cells_with_data: 0 } }).text).toBe('Learning: no satellites recorded yet');
    expect(lossRows(m)[0]).toEqual({ when: '11:20:00 UTC', sat: 'GPS 9', dir: '301° / 3°', cls: 'SET', note: 'below 5°: the satellite set' });
    expect(lossTotals(m)).toBe('5 since service start: 3 expected, 1 not explained, 1 set, 0 unknown');
  });

  it('the demo hides the map in hidden mode and keeps the sky quality opt-in', async () => {
    const api = demoApi();
    const on = await api.skyObstruction();
    expect(on.available).toBe(true);
    expect((await api.capability()).sky_quality).toBeNull();
    await api.setSkyQualityShare(true);
    expect((await api.capability()).sky_quality?.sectors.find(s => s.sector === 'W')?.state).toBe('obstructed');
    expect(await api.diagnostics()).toMatch(/sky quality \(inferred\): learned/);
    await api.setLocationDisplay('hidden');
    expect((await api.skyObstruction()).available).toBe(false);
    expect((await api.capability()).sky_quality).toBeNull();
    expect(await api.diagnostics()).toMatch(/not included \(location privacy is hidden\)/);
    expect(JSON.stringify(await api.capability())).not.toMatch(/38\.92|77\.06/);
  });
});
