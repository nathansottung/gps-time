// Screenshot mode: hides the station's coordinates, heights, NTP client addresses and hostname
// on this screen only. Display only: the station, the API and exports are unchanged (location
// privacy is the station-side control). Remembered per browser.

const KEY = 'gtp-screenshot-mode';
type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

function store(storage?: StorageLike | null): StorageLike | null {
  if (storage !== undefined) return storage;
  try { return typeof localStorage !== 'undefined' ? localStorage : null; } catch { return null; }
}

export function loadScreenshotMode(storage?: StorageLike | null): boolean {
  try { return store(storage)?.getItem(KEY) === 'on'; } catch { return false; }
}

export function saveScreenshotMode(on: boolean, storage?: StorageLike | null): void {
  try { store(storage)?.setItem(KEY, on ? 'on' : 'off'); } catch { /* storage unavailable: the choice lasts for this page */ }
}

/** Alt+Shift+S. `code` rather than `key`, so it works where Alt changes the character (macOS). */
export const SCREENSHOT_SHORTCUT = 'Alt+Shift+S';
export function isScreenshotShortcut(e: Pick<KeyboardEvent, 'code' | 'altKey' | 'shiftKey' | 'ctrlKey' | 'metaKey' | 'repeat'>): boolean {
  return e.code === 'KeyS' && e.altKey && e.shiftKey && !e.ctrlKey && !e.metaKey && !e.repeat;
}

/**
 * What is drawn in place of a hidden value: digits become 0 and letters x, punctuation and
 * spacing stay, so the layout doesn't move. The real value is never rendered (blurring real
 * digits can be undone), and the mask is blurred on top.
 */
export function maskText(s: string): string {
  return s.replace(/[0-9]/g, '0').replace(/\p{L}/gu, 'x');
}
