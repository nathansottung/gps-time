import { describe, expect, it } from 'vitest';
import { throttleRows, underVoltage } from './throttle';

// The station's decoding of get_throttled=0x50005 (bits 0, 2, 16, 18).
const T = {
  raw: '0x50005', any_now: true, any_ever: true,
  flags: [
    { label: 'Under-voltage now', active: true, now: true }, { label: 'Frequency capped now', active: false, now: true },
    { label: 'Throttled now', active: true, now: true }, { label: 'Soft temp limit now', active: false, now: true },
    { label: 'Under-voltage occurred since boot', active: true, now: false }, { label: 'Frequency capped since boot', active: false, now: false },
    { label: 'Throttled since boot', active: true, now: false }, { label: 'Soft temp limit since boot', active: false, now: false },
  ],
};

describe('throttle flags', () => {
  it('one row per condition, now and since boot, in the station’s order', () => {
    expect(throttleRows(T)).toEqual([
      { condition: 'Under-voltage', now: true, sinceBoot: true },
      { condition: 'Frequency capped', now: false, sinceBoot: false },
      { condition: 'Throttled', now: true, sinceBoot: true },
      { condition: 'Soft temp limit', now: false, sinceBoot: false },
    ]);
  });
  it('no vcgencmd: UNKNOWN (null), not "all clear"', () => {
    expect(throttleRows(null)).toBeNull();
    expect(underVoltage(null)).toBeNull();
  });
  it('under-voltage now, or only earlier since boot', () => {
    expect(underVoltage(throttleRows(T))).toEqual({ now: true, ever: true });
    const past = { ...T, flags: T.flags.map(f => ({ ...f, active: !f.now && f.label.startsWith('Under') })) };
    expect(underVoltage(throttleRows(past))).toEqual({ now: false, ever: true });
  });
});
