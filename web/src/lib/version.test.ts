import { describe, expect, it } from 'vitest';
import { UI_VERSION, versionLine } from './version';

describe('versionLine', () => {
  it('shows one version when UI and station match', () => {
    expect(versionLine('1.4.0-rc.1', '1.4.0-rc.1')).toBe('v1.4.0-rc.1');
    expect(versionLine('v1.4.0-rc.1', '1.4.0-rc.1')).toBe('v1.4.0-rc.1');
  });

  it('shows both when they differ', () => {
    expect(versionLine('1.4.0-rc.1-2-gabc1234', '1.4.0-rc.1'))
      .toBe('UI v1.4.0-rc.1-2-gabc1234 · station v1.4.0-rc.1');
  });

  it('says unknown instead of guessing', () => {
    expect(versionLine('unknown', '1.4.0-rc.1')).toBe('UI version unknown · station v1.4.0-rc.1');
    expect(versionLine('1.4.0-rc.1', 'unknown')).toBe('UI v1.4.0-rc.1 · station version unknown');
    expect(versionLine('1.4.0-rc.1', null)).toBe('UI v1.4.0-rc.1 · station version unknown');
    expect(versionLine('unknown', 'unknown')).toBe('UI version unknown · station version unknown');
  });

  it('shows only the UI version before /api answers', () => {
    expect(versionLine('1.4.0-rc.1', undefined)).toBe('UI v1.4.0-rc.1');
  });

  it('reads the build-time version', () => {
    expect(UI_VERSION).toBe('9.8.7');
  });
});
