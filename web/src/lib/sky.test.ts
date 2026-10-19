import { describe, expect, it } from 'vitest';
import { atParam, isSky, objectRows, skyLayout, starRadius } from './sky';
import type { ObjectReport, SkySnapshot } from '../api/types';

const SKY: SkySnapshot = {
  available: true,
  stars: [[90, 0, 0], [45, 90, 5], [-0.5, 180, 1]],
  lines: [[[30, 0], [40, 10], [-5, 20], [20, 30], [25, 40]]],
  bodies: { Moon: [10, 270], Venus: [-1, 100] },
  target: [-3, 45],
};

describe('sky map layout', () => {
  const L = skyLayout(SKY, 100, 100, 90);
  it('zenith at the centre, east to the right (same projection as the other /app/ sky plots)', () => {
    expect(L.stars[0]).toMatchObject({ x: 100, y: 100 });
    expect(L.stars[1].x).toBeCloseTo(145);
    expect(L.stars[1].y).toBeCloseTo(100);
  });
  it('drops what is below the horizon', () => {
    expect(L.stars).toHaveLength(2);
    expect(L.bodies.map(b => b.name)).toEqual(['Moon']);
  });
  it('splits a constellation line where it dips below the horizon instead of drawing across it', () => {
    expect(L.lines).toHaveLength(2);
    expect(L.lines.every(l => l.split(' ').length === 2)).toBe(true);
  });
  it('a target below the horizon is said, not hidden', () => {
    expect(L.target).toBe('below');
    expect(skyLayout({ ...SKY, target: null }, 100, 100, 90).target).toBeNull();
  });
  it('star size follows magnitude', () => {
    expect(starRadius(0)).toBe(3);
    expect(starRadius(6)).toBe(0.6);
  });
  it('recognises a sky snapshot; the demo/empty {} and unavailable are not', () => {
    expect(isSky(SKY)).toBe(true);
    expect(isSky({})).toBe(false);
    expect(isSky({ available: false, reason: 'x' })).toBe(false);
  });
});

describe('at=', () => {
  it('a valid HH:MM when not now, else now', () => {
    expect(atParam(false, '22:00')).toBe('22:00');
    expect(atParam(true, '22:00')).toBe('now');
    expect(atParam(false, '25:00')).toBe('now');
    expect(atParam(false, '')).toBe('now');
  });
});

const OBJ: ObjectReport = {
  available: true, name: 'M31 — Andromeda Galaxy', meta: 'galaxy, mag 3.4, in And', emphasis: 'moonless', at_label: '22:00',
  now_alt: 67.6, now_az: 74.6, rise: '2026-10-19T15:10:00-04:00', transit: '2026-10-19T23:55:00-04:00', transit_alt: 87.5,
  set: '2026-10-20T08:40:00-04:00', circumpolar: false, never_up: false,
  dark_windows: [{ start: '2026-10-19T20:53-04:00', end: '2026-10-20T05:18-04:00', dur_s: 30300 }],
  moonless_windows: [], min_alt_deg: 15, tz: 'America/New_York',
};

describe('object card', () => {
  const TZ = 'America/New_York';
  it('rows in order, the moonless window first for deep-sky objects', () => {
    const rows = objectRows(OBJ, '2026-10-19', TZ);
    expect(rows.map(r => r[0])).toEqual(['Object', 'At 22:00', 'Rise', 'Meridian transit', 'Set', 'Moonless viewing window', 'Dark viewing window']);
    expect(rows[4][1]).toBe('08:40 · 20 Oct');
    expect(rows[5][1]).toBe('none on this date');
    expect(rows[6][1]).toBe('20:53–05:18 · 20 Oct');
  });
  it('circumpolar and never-up objects say so', () => {
    expect(objectRows({ ...OBJ, circumpolar: true, rise: null, set: null }, '2026-10-19', TZ).map(r => r[1])).toContain('Circumpolar: always up');
    const never = objectRows({ ...OBJ, never_up: true, rise: null, set: null, transit: null }, '2026-10-19', TZ);
    expect(never.map(r => r[0])).not.toContain('Meridian transit');
    expect(never.map(r => r[1])).toContain('Never rises from this latitude');
  });
  it('a target below the horizon now is flagged', () => {
    expect(objectRows({ ...OBJ, now_alt: -12 }, '2026-10-19', TZ)[1][2]).toBe('below the horizon');
  });
});
