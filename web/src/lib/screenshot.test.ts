import { describe, expect, it } from 'vitest';
import { isScreenshotShortcut, loadScreenshotMode, maskText, saveScreenshotMode } from './screenshot';

function memStore() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => { m.set(k, v); } };
}

describe('screenshot mode: remembered per browser', () => {
  it('off until chosen, then remembered', () => {
    const s = memStore();
    expect(loadScreenshotMode(s)).toBe(false);
    saveScreenshotMode(true, s);
    expect(loadScreenshotMode(s)).toBe(true);
    saveScreenshotMode(false, s);
    expect(loadScreenshotMode(s)).toBe(false);
  });

  it('no storage or a throwing one: off, and saving does not throw', () => {
    expect(loadScreenshotMode(null)).toBe(false);
    const bad = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };
    expect(loadScreenshotMode(bad)).toBe(false);
    expect(() => saveScreenshotMode(true, bad)).not.toThrow();
  });
});

describe('screenshot mode: keyboard shortcut', () => {
  const k = { code: 'KeyS', altKey: true, shiftKey: true, ctrlKey: false, metaKey: false, repeat: false };
  it('Alt+Shift+S only', () => {
    expect(isScreenshotShortcut(k)).toBe(true);
    expect(isScreenshotShortcut({ ...k, shiftKey: false })).toBe(false);
    expect(isScreenshotShortcut({ ...k, altKey: false })).toBe(false);
    expect(isScreenshotShortcut({ ...k, ctrlKey: true })).toBe(false);
    expect(isScreenshotShortcut({ ...k, metaKey: true })).toBe(false);
    expect(isScreenshotShortcut({ ...k, code: 'KeyD' })).toBe(false);
  });
  it('a held key does not flicker it', () => {
    expect(isScreenshotShortcut({ ...k, repeat: true })).toBe(false);
  });
});

describe('screenshot mode: mask', () => {
  it('keeps the shape, drops every digit and letter', () => {
    expect(maskText('38.9217°')).toBe('00.0000°');
    expect(maskText('38.9217° N')).toBe('00.0000° x');
    expect(maskText('−77.0669°')).toBe('−00.0000°');
    expect(maskText('192.168.1.23')).toBe('000.000.0.00');
    expect(maskText('fe80::1a2b')).toBe('xx00::0x0x');
    expect(maskText('gps-time.local')).toBe('xxx-xxxx.xxxxx');
  });
  it('nothing of the value survives', () => {
    expect(maskText('38.9217°')).not.toMatch(/[1-9]/);
  });
});
