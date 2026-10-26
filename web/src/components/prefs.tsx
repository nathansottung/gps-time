import { useEffect, useSyncExternalStore } from 'react';
import { loadModules, loadScales, loadTheme, saveModules, saveScales, saveTheme, type ChartId, type ChartScale, type ChartScales, type Modules, type Theme } from '../lib/prefs';

// Two small page-wide stores (lib/prefs.ts): every reader re-renders when either changes.
function makeStore<T>(initial: T, save: (v: T) => void) {
  let value = initial;
  const listeners = new Set<() => void>();
  return {
    get: () => value,
    set: (v: T) => { value = v; save(v); listeners.forEach(l => l()); },
    subscribe: (l: () => void) => { listeners.add(l); return () => { listeners.delete(l); }; },
  };
}
const themeStore = makeStore<Theme>(loadTheme(undefined, typeof window !== 'undefined' ? window.location.search : ''), t => saveTheme(t));
const modulesStore = makeStore<Modules>(loadModules(), m => saveModules(m));
const scalesStore = makeStore<ChartScales>(loadScales(), s => saveScales(s));

export function useTheme(): [Theme, (t: Theme) => void] {
  return [useSyncExternalStore(themeStore.subscribe, themeStore.get), themeStore.set];
}
export function useModules(): [Modules, (m: Modules) => void] {
  return [useSyncExternalStore(modulesStore.subscribe, modulesStore.get), modulesStore.set];
}
/** A chart's linear/log value axis, remembered in this browser (every view of that chart follows it). */
export function useChartScale(id: ChartId): [ChartScale, (s: ChartScale) => void] {
  const all = useSyncExternalStore(scalesStore.subscribe, scalesStore.get);
  return [all[id], (s: ChartScale) => scalesStore.set({ ...scalesStore.get(), [id]: s })];
}

/**
 * Night theme: a red layer over the whole page, multiplied, so only red light leaves the
 * screen, whatever color a chart or control uses underneath. Display only.
 */
export function NightOverlay() {
  const [theme] = useTheme();
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  return theme === 'night' ? <div className="night-overlay" aria-hidden /> : null;
}

export function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  const night = theme === 'night';
  return (
    <button onClick={() => setTheme(night ? 'dark' : 'night')} aria-pressed={night}
      aria-label={night ? 'Night theme on; switch to dark' : 'Switch to the red night theme'}
      title="Red night theme for observing: only red light, dimmed. Remembered in this browser (shared with the legacy pages)."
      className="px-1.5 py-[3px] text-[9px] mono rounded-[2px] whitespace-nowrap uppercase tracking-[0.08em]"
      style={night
        ? { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }
        : { border:'1px solid var(--border)', color:'var(--t3)' }}>
      Night
    </button>
  );
}
