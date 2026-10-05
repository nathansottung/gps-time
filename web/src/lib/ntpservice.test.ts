import { describe, expect, it } from 'vitest';
import type { Measured, NmeaCalibration } from '../api/types';
import { fmtCount, fmtPerMin, fmtShare, nmeaCompare, requestSeries, serviceLabel, serviceVariant } from './ntpservice';
import { demoApi } from '../api/demo';

const q = (value: number | null, provenance: Measured['provenance'] = 'observed'): Measured => ({ value, unit: 's', provenance });

describe('NTP service labels', () => {
  it('states', () => {
    expect(['SERVING', 'SERVING_WITH_DROPS', 'NO_REQUESTS', 'UNKNOWN', undefined].map(s => serviceVariant(s as never)))
      .toEqual(['good', 'warn', 'info', 'muted', 'muted']);
    expect(serviceLabel('SERVING_WITH_DROPS')).toBe('SERVING · SOME DROPPED');
    expect(serviceLabel(undefined)).toBe('UNKNOWN');
  });

  it('rates per minute', () => {
    expect(fmtPerMin(0.2533333)).toBe('15.2 /min');
    expect(fmtPerMin(0.0002777)).toBe('0.02 /min');
    expect(fmtPerMin(3)).toBe('180 /min');
    expect(fmtPerMin(0)).toBe('0.00 /min');
    expect(fmtPerMin(null)).toBeNull();
  });

  it('shares keep small values visible', () => {
    expect(fmtShare(39 / 50115)).toBe('0.078%');
    expect(fmtShare(0.005)).toBe('0.50%');
    expect(fmtShare(0.25)).toBe('25.0%');
    expect(fmtShare(0)).toBe('0%');
    expect(fmtShare(null)).toBeNull();
  });

  it('counts and series', () => {
    expect(fmtCount(50115)).toBe('50,115');
    expect(fmtCount(null)).toBeNull();
    expect(requestSeries([{ t: 100, received_per_min: 12, dropped_per_min: 0 }])[0]).toMatchObject({ ts: 100000, dt: 12 });
    expect(requestSeries(undefined)).toEqual([]);
  });

  it('demo adapter serves the station shape', async () => {
    const s = await demoApi().ntpService();
    expect(s.available).toBe(true);
    expect(s.ntp!.received.provenance).toBe('observed');
    expect(s.ntp!.not_dropped.provenance).toBe('calculated');
    expect(s.ntp!.not_dropped.value).toBe(s.ntp!.received.value! - s.ntp!.dropped.value!);
    expect(s.history.length).toBeGreaterThan(10);
  });
});

describe('nmeaCompare', () => {
  const measured: NmeaCalibration = {
    available: true, reason: null, configured_offset_s: q(0.1), residual_s: q(0.035),
    suggested_offset_s: q(0.135, 'calculated'), change_worthwhile: true, advice: '…',
  };

  it('both values, with the difference', () => {
    expect(nmeaCompare(measured)).toEqual({ configured: '0.100 s', suggested: '0.135 s', difference: '+35 ms', suggestedReason: null, same: false });
  });

  it('a negative difference and no difference', () => {
    expect(nmeaCompare({ ...measured, suggested_offset_s: q(0.082, 'calculated') }).difference).toBe('−18 ms');
    const same = nmeaCompare({ ...measured, suggested_offset_s: q(0.1, 'calculated') });
    expect([same.difference, same.same]).toEqual(['+0 ms', true]);
  });

  it('not measurable: the configured value stays, the suggestion is unknown with the reason', () => {
    const c = nmeaCompare({ available: false, reason: 'PPS must be the selected source', configured_offset_s: q(0.1) });
    expect(c.configured).toBe('0.100 s');
    expect(c.suggested).toBeNull();
    expect(c.difference).toBeNull();
    expect(c.suggestedReason).toBe('PPS must be the selected source');
  });

  it('nothing configured or nothing reported', () => {
    const none = nmeaCompare({ available: false, reason: 'no NMEA/serial refclock in chrony.conf' });
    expect([none.configured, none.suggested]).toEqual([null, null]);
    expect(nmeaCompare(undefined).suggestedReason).toBe('not reported by this station version');
  });

  it('never shows a suggestion the station did not calculate', () => {
    // available is false, so a stray suggested value must not be shown
    const c = nmeaCompare({ available: false, reason: 'too few NMEA samples so far', configured_offset_s: q(0.1), suggested_offset_s: q(0.2, 'calculated') });
    expect(c.suggested).toBeNull();
  });
});
