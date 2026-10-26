// Per-browser display preferences (legacy removal step 5, owner decisions 2026-10-19):
// the theme (dark, or red night for observing; light was dropped) and which modules are shown.
// They replaced the legacy saved-layout editor (removed after v1.4.0). Nothing here changes the station.

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;
function store(storage?: StorageLike | null): StorageLike | null {
  if (storage !== undefined) return storage;
  try { return typeof localStorage !== 'undefined' ? localStorage : null; } catch { return null; }
}

// ─── Theme ───────────────────────────────────────────────────────────────────

export type Theme = 'dark' | 'night';
/** The key the legacy pages used, so an old choice carries over; their "light" (dropped) reads as dark. */
const THEME_KEY = 'gtp-theme';

/** ?theme=night|dark wins, then the stored choice, else dark. */
export function loadTheme(storage?: StorageLike | null, search = ''): Theme {
  try {
    const q = new URLSearchParams(search).get('theme');
    if (q === 'night' || q === 'dark') return q;
  } catch { /* ignore a bad query */ }
  try { return store(storage)?.getItem(THEME_KEY) === 'night' ? 'night' : 'dark'; } catch { return 'dark'; }
}

export function saveTheme(t: Theme, storage?: StorageLike | null): void {
  try { store(storage)?.setItem(THEME_KEY, t); } catch { /* storage unavailable: lasts for this page */ }
}

// ─── Modules ─────────────────────────────────────────────────────────────────

/** Pages that can be hidden. Overview, Configure and Administration always stay. */
export const PAGE_MODULES = [
  { id: 'timing', label: 'Timing & Reliability' }, { id: 'pps', label: 'PPS Diagnostics' },
  { id: 'gnss', label: 'GNSS & Site' }, { id: 'sun', label: 'Sun & Astronomy' },
  { id: 'network', label: 'Network & Devices' }, { id: 'radio', label: 'Radio & SDR' },
  { id: 'aviation', label: 'Aviation' }, { id: 'distributed', label: 'Distributed Obs.' },
  { id: 'data', label: 'Data & Logs' },
] as const;
export const ALWAYS_SHOWN = ['overview', 'configure', 'admin'] as const;

/** Overview cards that can be hidden. The timing chain, the clock and timing quality always show (CHG). */
export const OVERVIEW_CARDS = [
  { id: 'holdover', label: 'Holdover' }, { id: 'sun', label: 'Sun & daylight' }, { id: 'gnss', label: 'GNSS' },
  { id: 'network', label: 'Network' }, { id: 'datapacks', label: 'Data packs' }, { id: 'solar', label: 'Solar' },
  { id: 'moon', label: 'Moon' },
] as const;

export interface Modules { hiddenPages: string[]; hiddenCards: string[] }
const MODULES_KEY = 'gtp-modules';
const PAGE_IDS: readonly string[] = PAGE_MODULES.map(p => p.id);
const CARD_IDS: readonly string[] = OVERVIEW_CARDS.map(c => c.id);

/** Only known ids survive, so a stale or edited value can never hide Overview, Configure or Administration. */
export function sanitizeModules(v: unknown): Modules {
  const o = (v && typeof v === 'object' ? v : {}) as Partial<Record<keyof Modules, unknown>>;
  const ids = (x: unknown, known: readonly string[]) =>
    Array.isArray(x) ? [...new Set(x.filter((i): i is string => typeof i === 'string' && known.includes(i)))] : [];
  return { hiddenPages: ids(o.hiddenPages, PAGE_IDS), hiddenCards: ids(o.hiddenCards, CARD_IDS) };
}

export function loadModules(storage?: StorageLike | null): Modules {
  try { return sanitizeModules(JSON.parse(store(storage)?.getItem(MODULES_KEY) ?? '{}')); } catch { return sanitizeModules({}); }
}

export function saveModules(m: Modules, storage?: StorageLike | null): void {
  try { store(storage)?.setItem(MODULES_KEY, JSON.stringify(sanitizeModules(m))); } catch { /* lasts for this page */ }
}

export function toggled(list: string[], id: string): string[] {
  return list.includes(id) ? list.filter(x => x !== id) : [...list, id];
}

/** The page to show: a hidden page falls back to the Overview. */
export function visiblePage(page: string, m: Modules): string {
  return m.hiddenPages.includes(page) ? 'overview' : page;
}

// ─── Chart value-axis scale (lib/timeaxis.ts) ───────────────────────────────

export type ChartScale = 'linear' | 'log';
/** Charts with a linear/log toggle, and the scale each starts on. */
export const CHART_SCALE_DEFAULTS = {
  'overview-dt': 'linear',     // Overview: Δt over the last hour
  'offset-history': 'log',     // Timing: chrony's offset history (symmetric log, as before)
  'ref-offset': 'linear',      // References: offset of the picked server
  'ref-delay': 'linear',       // References: delay of the picked server
  'holdover': 'linear',        // Timing: error at PPS reacquisition
  'stability': 'log',          // Stability: ADEV / MDEV / TDEV (log–log, as before)
} as const satisfies Record<string, ChartScale>;
export type ChartId = keyof typeof CHART_SCALE_DEFAULTS;
export type ChartScales = Record<ChartId, ChartScale>;
const SCALES_KEY = 'gtp-chart-scales';

/** Known charts only, each 'linear' or 'log'; anything else falls back to its default. */
export function sanitizeScales(v: unknown): ChartScales {
  const o = (v && typeof v === 'object' ? v : {}) as Record<string, unknown>;
  const out = { ...CHART_SCALE_DEFAULTS } as ChartScales;
  for (const id of Object.keys(CHART_SCALE_DEFAULTS) as ChartId[]) {
    if (o[id] === 'linear' || o[id] === 'log') out[id] = o[id] as ChartScale;
  }
  return out;
}

export function loadScales(storage?: StorageLike | null): ChartScales {
  try { return sanitizeScales(JSON.parse(store(storage)?.getItem(SCALES_KEY) ?? '{}')); } catch { return sanitizeScales({}); }
}

export function saveScales(s: ChartScales, storage?: StorageLike | null): void {
  try { store(storage)?.setItem(SCALES_KEY, JSON.stringify(sanitizeScales(s))); } catch { /* lasts for this page */ }
}
