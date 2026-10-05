// Banner guards (CHG-PPS-HEALTH-DIAGNOSTICS "Main Status Banner", test 20):
// the UI must name the sync source and never claim GPS/PPS that chrony is not using.
import { describe, expect, it } from 'vitest';
import { bannerView, clockDiscipline, statusVariant } from './banner';
import { demoApi, DEMO_SCENARIOS } from '../api/demo';
import type { TimingChain } from '../api/types';

async function chain(scenario: string): Promise<TimingChain> {
  return demoApi().timingChain({ scenario });
}

/** A copy with status/selection overridden. */
function withStatus(c: TimingChain, status: Partial<TimingChain['status']>, selected?: TimingChain['chrony']['selected']): TimingChain {
  return { ...c, status: { ...c.status, ...status }, chrony: { ...c.chrony, selected: selected === undefined ? c.chrony.selected : selected } };
}

describe('bannerView', () => {
  it('shows UNKNOWN when there is no timing chain', () => {
    expect(bannerView(null, false)).toMatchObject({ variant: 'muted', title: 'TIMING STATUS UNKNOWN', outage: null });
    expect(bannerView(null, true)).toMatchObject({ variant: 'error', title: 'TIMING STATUS UNKNOWN · STATION UNREACHABLE' });
  });

  it('passes a correct GPS/PPS banner through', async () => {
    const v = bannerView(await chain('pps_selected'), false);
    expect(v.variant).toBe('good');
    expect(v.title).toBe('SYNCHRONIZED · GPS/PPS · STRATUM 1');
    expect(v.outage).toBeNull();
  });

  it('never shows GPS/PPS when chrony selected a non-PPS source (test 20)', async () => {
    const c = withStatus(await chain('pps_selected'), { code: 'GPS_PPS', banner: 'SYNCHRONIZED · GPS/PPS · STRATUM 1' },
      { name: '192.0.2.10', kind: 'network', stratum: 2, is_pps: false, is_nmea: false });
    const v = bannerView(c, false);
    expect(v.title).toBe('TIMING STATUS UNKNOWN · INCONSISTENT REPORT');
    expect(v.title).not.toMatch(/GPS\/PPS|STRATUM 1/);
    expect(v.variant).toBe('warn');
    expect(v.detail).toContain('192.0.2.10');
  });

  it('never shows a bare SYNCHRONIZED: appends the selected source', async () => {
    const c = withStatus(await chain('network_failover'), { code: 'NETWORK_FAILOVER', banner: 'SYNCHRONIZED' });
    expect(bannerView(c, false).title).toBe('SYNCHRONIZED · SOURCE 192.0.2.10');
  });

  it('says SOURCE UNKNOWN when nothing is selected', async () => {
    const c = withStatus(await chain('pps_selected'), { code: 'DEGRADED', banner: 'SYNCHRONIZED', headline: 'SYNCHRONIZED' }, null);
    expect(bannerView(c, false).title).toBe('SYNCHRONIZED · SOURCE UNKNOWN');
  });

  it('falls back to the headline, then UNKNOWN, when the banner is empty', async () => {
    const base = await chain('pps_selected');
    expect(bannerView(withStatus(base, { code: 'UNKNOWN', banner: '', headline: '' }), false).title).toBe('UNKNOWN');
  });

  it('reports the open outage with duration and start', async () => {
    const v = bannerView(await chain('network_failover'), false);
    expect(v.variant).toBe('warn');
    expect(v.title).toContain('NETWORK FAILOVER');
    expect(v.outage).toMatch(/^PPS unavailable for 2d 7h 14m \(since \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\)$/);
  });

  it('marks an outage whose true start is earlier', async () => {
    const c = await chain('network_failover');
    const ev = { ...c.events.open!, start_bound: 'service_start' };
    expect(bannerView({ ...c, events: { ...c.events, open: ev } }, false).outage).toMatch(/ or earlier\)$/);
  });

  it.each([...DEMO_SCENARIOS])('scenario %s: title names a source and is never bare', async (s) => {
    const c = await chain(s);
    const v = bannerView(c, false);
    expect(v.title).not.toBe('SYNCHRONIZED');
    expect(v.title).toContain('·');
    if (v.title.includes('GPS/PPS') && !v.title.includes('UNAVAILABLE')) expect(c.chrony.selected?.is_pps).toBe(true);
  });
});

describe('statusVariant', () => {
  it.each([
    ['GPS_PPS', 'good'], ['UNSYNCHRONIZED', 'error'], ['UNKNOWN', 'muted'], [undefined, 'muted'],
    ['NETWORK_FAILOVER', 'warn'], ['DEGRADED', 'warn'], ['HOLDOVER', 'warn'], ['ACQUIRING', 'warn'],
  ])('%s → %s', (code, v) => {
    expect(statusVariant(code as string | undefined)).toBe(v);
  });
});

describe('clockDiscipline (the big clock caption)', () => {
  it('says GPS/PPS only when the status is GPS/PPS and chrony selected the PPS refclock', async () => {
    expect(clockDiscipline(await chain('pps_selected'), false)).toEqual({ gps: true, label: 'GPS/PPS-DISCIPLINED STATION CLOCK' });
  });

  it('names network time as network time', async () => {
    const d = clockDiscipline(await chain('network_failover'), false);
    expect(d.gps).toBe(false);
    expect(d.label).toMatch(/^STATION CLOCK · /);
    expect(d.label).not.toContain('GPS/PPS-DISCIPLINED');
  });

  it('does not claim GPS on an inconsistent report (status GPS/PPS, non-PPS source selected)', async () => {
    const c = withStatus(await chain('pps_selected'), { code: 'GPS_PPS', banner: 'SYNCHRONIZED · GPS/PPS · STRATUM 1' },
      { name: '192.0.2.10', kind: 'network', stratum: 2, is_pps: false, is_nmea: false });
    expect(clockDiscipline(c, false)).toEqual({ gps: false, label: 'STATION CLOCK · TIMING STATUS UNKNOWN · INCONSISTENT REPORT' });
  });

  it('is unknown without a timing chain', () => {
    expect(clockDiscipline(null, false)).toEqual({ gps: false, label: 'STATION CLOCK · TIMING STATUS UNKNOWN' });
    expect(clockDiscipline(null, true).label).toBe('STATION CLOCK · TIMING STATUS UNKNOWN · STATION UNREACHABLE');
  });
});
