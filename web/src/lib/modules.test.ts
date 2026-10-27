import { describe, expect, it } from 'vitest';
import type { ModuleRow, ModulesState } from '../api/types';
import { applySetting, canToggle, configProblem, configText, fmtModuleValue, outputHeading, outputLines, parseConfig, permissionText, readinessLines, rowStatus, schemaRows, settingOutcome } from './modules';
import { demoApi } from '../api/demo';

const row = (o: Partial<ModuleRow> = {}): ModuleRow => ({
  name: 'm', installed: true, valid: true, errors: [], version: '0.1.0', maturity: 'research', types: ['source'],
  summary: null, permissions: { network: false, devices: [], storage: 'none' }, enabled: false, runs: false,
  state: null, reason: null, ...o,
});
const state = (o: Partial<ModulesState> = {}): ModulesState => ({
  experimental: true, modules: [], supervisor: { reporting: true, age_s: 2, detail: '' }, note: '', ...o,
});

describe('rowStatus', () => {
  it('never infers a running state', () => {
    expect(rowStatus(row({ enabled: true }), state({ supervisor: { reporting: false, age_s: null, detail: '' } })).label)
      .toBe('ENABLED · state UNKNOWN');
    expect(rowStatus(row({ enabled: true, state: null }), state()).label).toBe('ENABLED · state UNKNOWN');
  });
  it('shows the switch as the reason a module is off', () => {
    expect(rowStatus(row({ enabled: true }), state({ experimental: false })).label).toBe('OFF (switch off)');
    // an analysis-only module: the host never runs it, so it is never shown as running or UNKNOWN
    expect(rowStatus(row({ enabled: true, host_runs: false, state: null }), state()).label).toMatch(/NOT RUN BY THE HOST/);
    expect(rowStatus(row(), state()).label).toBe('OFF');
  });
  it('maps reported states', () => {
    expect(rowStatus(row({ enabled: true, state: 'running' }), state()).variant).toBe('good');
    expect(rowStatus(row({ enabled: true, state: 'killed' }), state()).variant).toBe('error');
    expect(rowStatus(row({ enabled: true, state: 'starting' }), state()).variant).toBe('warn');
    expect(rowStatus(row({ valid: false }), state()).label).toBe('INVALID MANIFEST');
    expect(rowStatus(row({ installed: false, valid: false, enabled: true }), state()).label).toBe('NOT INSTALLED');
  });
});

describe('canToggle', () => {
  it('needs the token, the switch and a valid module to turn one on', () => {
    expect(canToggle(row(), state(), false)).toBe(false);
    expect(canToggle(row(), state({ experimental: false }), true)).toBe(false);
    expect(canToggle(row({ valid: false }), state(), true)).toBe(false);
    expect(canToggle(row(), state(), true)).toBe(true);
  });
  it('always allows turning one off (with the token)', () => {
    expect(canToggle(row({ enabled: true, valid: false }), state({ experimental: false }), true)).toBe(true);
    expect(canToggle(row({ enabled: true }), state(), false)).toBe(false);
  });
});

describe('applySetting (the station rules, for the demo)', () => {
  const valid = new Set(['m']);
  it('switching on or off leaves every module off', () => {
    const s = { experimental: false, enabled: ['m'] };
    applySetting(s, valid, { modules_experimental: true });
    expect(s).toEqual({ experimental: true, enabled: [] });
    applySetting(s, valid, { module: 'm', enabled: true });
    applySetting(s, valid, { modules_experimental: false });
    applySetting(s, valid, { modules_experimental: true });
    expect(s.enabled).toEqual([]);
  });
  it('refuses to enable with the switch off or an unknown module', () => {
    expect(() => applySetting({ experimental: false, enabled: [] }, valid, { module: 'm', enabled: true })).toThrow(/turn them on first/);
    expect(() => applySetting({ experimental: true, enabled: [] }, valid, { module: 'x', enabled: true })).toThrow(/no valid module/);
  });
});

describe('demo adapter', () => {
  it('follows the same rules', async () => {
    const api = demoApi();
    expect((await api.modules()).experimental).toBe(false);
    await expect(api.setModule('sdr-pps-marker', true)).rejects.toThrow();
    await api.setModulesExperimental(true);
    expect((await api.modules()).modules.every(r => !r.enabled)).toBe(true);
    await api.setModule('sdr-pps-marker', true);
    const st = await api.modules();
    const m = st.modules[0];
    // the demo shows a canned sample of the module's synthetic demo, and says so
    expect([m.enabled, m.runs, m.state]).toEqual([true, true, 'finished']);
    expect(st.supervisor.detail).toMatch(/canned sample/);
    expect(m.latest?.values.scenario.note).toMatch(/synthetic/);
    await api.setModulesExperimental(false);
    const off = (await api.modules());
    expect([off.supervisor.reporting, off.modules[0].latest]).toEqual([false, null]);
  });
});

describe('labels', () => {
  it('permissions and outcomes', () => {
    expect(permissionText(row())).toBe('no network · no devices · storage none');
    expect(permissionText(row({ permissions: null }))).toBe('UNKNOWN');
    expect(settingOutcome('x', null, { message: 'm', status: null }).variant).toBe('warn');
    expect(settingOutcome('x', null, { message: 'm', status: 409 }).text).toContain('refused');
    expect(settingOutcome('x', { ok: true, module: 'm', enabled: true, modules_enabled: ['m'] }).variant).toBe('good');
  });
});

describe('latest output', () => {
  it('formats values without inventing any', () => {
    expect(fmtModuleValue(null, 'ppm')).toEqual({ value: null, unit: 'ppm' });
    expect(fmtModuleValue(true, null)).toEqual({ value: 'yes', unit: '' });
    expect(fmtModuleValue('OK', null)).toEqual({ value: 'OK', unit: '' });
    expect(fmtModuleValue(7, null)).toEqual({ value: '7', unit: '' });
    expect(fmtModuleValue(-3, 'dB')).toEqual({ value: '−3', unit: 'dB' });
    expect(fmtModuleValue(1.5363421906110658e-6, 's')).toEqual({ value: '1.5', unit: 'µs' });
    expect(fmtModuleValue(-2.5e-8, 's')).toEqual({ value: '−25.0', unit: 'ns' });
    expect(fmtModuleValue(0.03621951560894843, 'ppm')).toEqual({ value: '0.0362195', unit: 'ppm' });
    expect(fmtModuleValue(1.2e-5, 'ppm').value).toBe('1.2 × 10⁻⁵');
    expect(fmtModuleValue(521e6 + 0.5, 'Hz').value).toBe('5.21 × 10⁸');
    expect(fmtModuleValue(Number.NaN, 'x').value).toBeNull();
  });
  it('lines keep labels and notes; the heading says what is left out', () => {
    const lt = { kind: 'observation' as const, time_ns: 1, age_s: 75, items_kept: 20, left_out: 2,
      values: { markers: { value: 9, unit: null, provenance: 'observed' as const },
                state: { value: 'OK', unit: null, provenance: 'calculated' as const, note: 'n' } } };
    expect(outputLines(lt)).toEqual([
      { name: 'markers', value: '9', unit: '', provenance: 'observed' },
      { name: 'state', value: 'OK', unit: '', provenance: 'calculated', note: 'n' }]);
    expect(outputHeading(lt)).toBe('Latest observation 1m 15s ago · 20 kept in RAM · 2 values not shown (unlabeled, not a single value, a position, or over the limit)');
    expect(outputHeading({ ...lt, age_s: null, left_out: 0 })).toBe('Latest observation time UNKNOWN · 20 kept in RAM');
  });
});

describe('readiness', () => {
  it('shows MISSING for false and UNKNOWN for null, never OK by default', () => {
    expect(readinessLines(null)).toEqual([]);
    expect(readinessLines([{ check: 'a', ok: true, detail: 'x' }, { check: 'b', ok: false, detail: 'y' },
      { check: 'c', ok: null, detail: 'z' }]).map(l => [l.mark, l.variant]))
      .toEqual([['OK', 'good'], ['MISSING', 'warn'], ['UNKNOWN', 'muted']]);
  });
});

describe('module settings', () => {
  const schema = { fs_nominal: { type: 'float', unit: 'Hz' }, station_id: { type: 'string', default: 'gps-time-station' },
    min_nac_p: { type: 'int', default: 8 }, rtl_tcp: { type: 'table', default: {} } };

  it('starts from what the station has', () => {
    expect(configText(undefined)).toBe('{}');
    expect(configText({ fs_nominal: 2400000 })).toBe('{\n  "fs_nominal": 2400000\n}');
  });

  it('lists the manifest keys with their defaults', () => {
    expect(schemaRows(schema).map(r => [r.name, r.type, r.dflt])).toEqual([
      ['fs_nominal', 'float, Hz', 'none: must be set'], ['station_id', 'string', '"gps-time-station"'],
      ['min_nac_p', 'int', '8'], ['rtl_tcp', 'table', '{}']]);
  });

  it('applies the station rules before sending', () => {
    expect(parseConfig('', schema)).toEqual({ ok: true, value: {} });
    expect(parseConfig('{"fs_nominal": 2400000, "rtl_tcp": {"plan": []}}', schema).ok).toBe(true);
    const err = (text: string) => { const r = parseConfig(text, schema); return r.ok ? null : r.error; };
    expect(err('{nope')).toMatch(/not valid JSON/);
    expect(err('[]')).toMatch(/JSON object/);
    expect(err('{"x": 1}')).toMatch(/no setting x/);
    expect(err('{"fs_nominal": "fast"}')).toMatch(/fs_nominal must be a float/);
    expect(err('{"min_nac_p": 8.5}')).toMatch(/min_nac_p must be a int/);
    expect(err('{"rtl_tcp": []}')).toMatch(/rtl_tcp must be a table/);
    expect(err('{"rtl_tcp": {"plan": [{"lat": 38.9217}]}}')).toMatch(/rtl_tcp.plan.0.lat: positions are not set here/);
    expect(configProblem({ station_id: 'x'.repeat(301) }, schema)).toMatch(/at most 300/);
  });

  it('the demo adapter keeps them per tab and checks them the same way', async () => {
    const api = demoApi();
    const before = (await api.modules()).modules.find(r => r.name === 'sdr-pps-marker')!;
    expect(before.readiness?.find(c => c.check === 'live capture configured')?.ok).toBe(false);
    await expect(api.setModuleConfig('sdr-pps-marker', { lat: 1 })).rejects.toThrow(/no setting lat/);
    await api.setModuleConfig('sdr-pps-marker', { fs_nominal: 2400000, rtl_tcp: { plan: [{ center_hz: 88800000, dwell_s: 10 }] } });
    const after = (await api.modules()).modules.find(r => r.name === 'sdr-pps-marker')!;
    expect(after.config).toEqual({ fs_nominal: 2400000, rtl_tcp: { plan: [{ center_hz: 88800000, dwell_s: 10 }] } });
    expect(after.readiness?.find(c => c.check === 'live capture configured')?.ok).toBe(true);
    expect(after.enabled).toBe(false);                       // settings never turn a module on
    await api.setModuleConfig('sdr-pps-marker', null);
    expect((await api.modules()).modules[0].config).toEqual({});
    expect((await api.modules()).modules.map(r => r.name)).toEqual(['sdr-pps-marker', 'reference-adsb']);
  });
});
