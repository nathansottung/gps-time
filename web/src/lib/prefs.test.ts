import { describe, expect, it } from 'vitest';
import { loadModules, loadTheme, sanitizeModules, saveModules, saveTheme, toggled, visiblePage } from './prefs';

function memStore() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => { m.set(k, v); }, m };
}
const bad = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };

describe('theme', () => {
  it('dark until night is chosen; remembered', () => {
    const s = memStore();
    expect(loadTheme(s)).toBe('dark');
    saveTheme('night', s);
    expect(loadTheme(s)).toBe('night');
  });
  it('shares the legacy key; the dropped light theme reads as dark', () => {
    const s = memStore();
    s.setItem('gtp-theme', 'light');
    expect(loadTheme(s)).toBe('dark');
    s.setItem('gtp-theme', 'night');
    expect(loadTheme(s)).toBe('night');
  });
  it('?theme= wins; nonsense is ignored', () => {
    const s = memStore();
    expect(loadTheme(s, '?theme=night')).toBe('night');
    saveTheme('night', s);
    expect(loadTheme(s, '?theme=dark')).toBe('dark');
    expect(loadTheme(s, '?theme=light')).toBe('night');
  });
  it('blocked storage: dark, and no throw', () => {
    expect(loadTheme(bad)).toBe('dark');
    expect(() => saveTheme('night', bad)).not.toThrow();
  });
});

describe('modules', () => {
  it('everything shown by default; choices remembered', () => {
    const s = memStore();
    expect(loadModules(s)).toEqual({ hiddenPages: [], hiddenCards: [] });
    saveModules({ hiddenPages: ['aviation', 'radio'], hiddenCards: ['solar'] }, s);
    expect(loadModules(s)).toEqual({ hiddenPages: ['aviation', 'radio'], hiddenCards: ['solar'] });
  });
  it('Overview, Configure and Administration can never be hidden; unknown ids and junk are dropped', () => {
    expect(sanitizeModules({ hiddenPages: ['overview', 'configure', 'admin', 'aviation', 'aviation', 7], hiddenCards: ['timing', 'moon'] }))
      .toEqual({ hiddenPages: ['aviation'], hiddenCards: ['moon'] });
    expect(sanitizeModules(null)).toEqual({ hiddenPages: [], hiddenCards: [] });
    const s = memStore();
    s.setItem('gtp-modules', '{not json');
    expect(loadModules(s)).toEqual({ hiddenPages: [], hiddenCards: [] });
    expect(loadModules(bad)).toEqual({ hiddenPages: [], hiddenCards: [] });
  });
  it('toggle, and a hidden page falls back to the Overview', () => {
    expect(toggled(['a'], 'b')).toEqual(['a', 'b']);
    expect(toggled(['a', 'b'], 'a')).toEqual(['b']);
    expect(visiblePage('aviation', { hiddenPages: ['aviation'], hiddenCards: [] })).toBe('overview');
    expect(visiblePage('gnss', { hiddenPages: ['aviation'], hiddenCards: [] })).toBe('gnss');
  });
});
