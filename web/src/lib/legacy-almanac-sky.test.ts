// The legacy almanac sky map (gps_time_pi/templates/almanac.html) isn't a module: its projection
// and its compass labels are read from the template and checked against each other.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(fileURLToPath(new URL('../../../gps_time_pi/templates/almanac.html', import.meta.url)), 'utf8');

describe('legacy sky map: compass labels match the projection', () => {
  const m = src.match(/function xy\(alt, az\)\{\s*const r = (.+?);\s*return \[(.+?)\];\s*\}/s);
  const xy = new Function('alt', 'az', 'R', 'cx', 'cy', `const r = ${m![1]}; return [${m![2]}];`) as
    (alt: number, az: number, R: number, cx: number, cy: number) => [number, number];
  const label = (letter: string) => Number(src.match(new RegExp(`<text x="(\\d+)" y="\\$\\{cy\\+4\\}"[^>]*>${letter}</text>`))![1]);

  it('east-azimuth objects are drawn on the side labeled E', () => {
    const [x] = xy(0, 90, 185, 200, 200);
    expect(x).toBeLessThan(200);
    expect(label('E')).toBeLessThan(200);
  });
  it('west-azimuth objects are drawn on the side labeled W', () => {
    const [x] = xy(0, 270, 185, 200, 200);
    expect(x).toBeGreaterThan(200);
    expect(label('W')).toBeGreaterThan(200);
  });
  it('north is up', () => {
    expect(xy(0, 0, 185, 200, 200)[1]).toBeLessThan(200);
  });
});
