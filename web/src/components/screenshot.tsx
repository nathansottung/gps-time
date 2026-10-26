import { useEffect, useSyncExternalStore, type ReactNode } from 'react';
import { SCREENSHOT_SHORTCUT, isScreenshotShortcut, loadScreenshotMode, maskText, saveScreenshotMode } from '../lib/screenshot';

// One switch for the whole page (lib/screenshot.ts): every <Sensitive> follows it.
let on = loadScreenshotMode();
const listeners = new Set<() => void>();
function setScreenshotMode(v: boolean) {
  on = v;
  saveScreenshotMode(v);
  listeners.forEach(l => l());
}
function subscribe(l: () => void) { listeners.add(l); return () => { listeners.delete(l); }; }

export function useScreenshotMode(): [boolean, (v: boolean) => void] {
  return [useSyncExternalStore(subscribe, () => on), setScreenshotMode];
}

/** A value hidden in screenshot mode: a blurred mask of the same shape, never the value itself. */
export function Sensitive({ children }: { children: string | number }) {
  const [hidden] = useScreenshotMode();
  const text = String(children);
  if (!hidden) return <>{text}</>;
  return <span className="sensitive" aria-label="hidden in screenshot mode" title="Hidden in screenshot mode (display only)">{maskText(text)}</span>;
}

/** Header toggle, with the Alt+Shift+S shortcut. */
export function ScreenshotToggle(): ReactNode {
  const [hidden, set] = useScreenshotMode();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!isScreenshotShortcut(e)) return;
      e.preventDefault();
      setScreenshotMode(!on);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  return (
    <button onClick={() => set(!hidden)} aria-pressed={hidden}
      aria-label={`Screenshot mode ${hidden ? 'on' : 'off'} (display only)`}
      title={`Screenshot mode (${SCREENSHOT_SHORTCUT}): hides coordinates, heights, NTP client addresses and the hostname on this screen. Display only: the station, its API and exports are unchanged; Location privacy (Administration) is the station's own setting. Remembered in this browser.`}
      className="flex items-center gap-1.5 px-1.5 py-[3px] text-[9px] mono rounded-[2px] whitespace-nowrap"
      style={hidden
        ? { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }
        : { border:'1px solid var(--border)', color:'var(--t3)' }}>
      <span className="uppercase tracking-[0.08em]">Screenshot {hidden ? 'on' : 'off'}</span>
      <span style={{ color: hidden ? 'var(--accent)' : 'var(--t3)' }}>display only</span>
    </button>
  );
}
