import { describe, expect, it } from 'vitest';
import { checkRequest, estimateBytes, lastLine, storageLine, timeLabel } from './clips';
import type { ClipsStatus } from '../api/types';

const st = (over: Partial<ClipsStatus> = {}): ClipsStatus => ({
  storage: { dir: '/run/gps-time-clips', kind: 'ram', max_mb: 64, used: { value: 2e6, unit: 'bytes', provenance: 'observed' }, problem: null },
  pending: null, last: null, clips: [], kinds: ['iq', 'am', 'nfm', 'wfm'], iq_rates: [1_024_000, 2_048_000, 2_400_000],
  max_seconds: 60, freq_range_hz: [24_000_000, 1_766_000_000], note: '', ...over,
});

describe('clips', () => {
  it('checks a request as the station does', () => {
    expect(checkRequest(st(), 'am', '119.1', '20', 1_024_000)).toEqual({ req: { kind: 'am', freq_hz: 119_100_000, seconds: 20 }, problem: null });
    expect(checkRequest(st(), 'am', '10', '20', 1_024_000).problem).toContain('Frequency');
    expect(checkRequest(st(), 'am', '119.1', '61', 1_024_000).problem).toContain('Length');
    expect(checkRequest(st(), 'iq', '1090', '60', 2_400_000).problem).toContain('cap');   // 288 MB > 64 MB
  });
  it('estimates sizes', () => {
    expect(estimateBytes({ kind: 'iq', freq_hz: 1, seconds: 1, rate: 1_024_000 })).toBe(2_048_000 + 8192);
  });
  it('says where clips are and never hides a storage problem', () => {
    expect(storageLine(st()).text).toContain('in RAM');
    expect(storageLine(st({ storage: { ...st().storage, problem: "/mnt/usb/clips doesn't exist" } })).variant).toBe('error');
  });
  it('labels a clip with the timing it carries', () => {
    const c = { name: 'x', kind: 'am', freq_hz: 1, start_utc: null, seconds: 1, bytes: 1, time_source: 'ntp', time_offset_bound_s: null,
                sample_time_uncertainty_s: 0.546, signed: true, files: [] as never[] };
    expect(timeLabel(c)).toBe('ntp, ±0.55 s (USB buffering)');
  });
  it('shows a recording in progress and a failure', () => {
    expect(lastLine(st({ pending: { id: 'a', kind: 'am', freq_hz: 119_100_000, seconds: 5 } }))!.text).toContain('Recording am');
    expect(lastLine(st({ last: { ok: false, error: 'rtl_tcp busy', at: 1 } }))!.variant).toBe('error');
  });
});
