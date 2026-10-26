import { describe, expect, it } from 'vitest';
import type { ModuleRow, ModulesState } from '../api/types';
import { applySetting, canToggle, permissionText, rowStatus, settingOutcome } from './modules';
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
    const m = (await api.modules()).modules[0];
    expect([m.enabled, m.runs, m.state]).toEqual([true, true, null]);
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
