// React wiring for the station API: data-source selection, a provider that
// polls the status endpoints every page needs, and small polling hooks.

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { httpApi, pingOnce, type DataSource, type PingSample, type StationApi } from './client';
import { demoApi } from './demo';
import type { CoreStatus, TimingChain } from './types';

/**
 * Data source, in order: ?source=demo|live in the page URL, then the build-time
 * VITE_GTP_SOURCE, then 'live'. There is no automatic fallback to demo.
 */
export function selectSource(): DataSource {
  try {
    const q = new URLSearchParams(window.location.search).get('source');
    if (q === 'demo' || q === 'live') return q;
  } catch { /* non-browser */ }
  return import.meta.env.VITE_GTP_SOURCE === 'demo' ? 'demo' : 'live';
}

export function createApi(source: DataSource = selectSource()): StationApi {
  return source === 'demo' ? demoApi() : httpApi('');
}

export interface Polled<T> {
  data: T | null;
  error: string | null;
  updatedAt: number | null;   // browser epoch ms of the last success
  refresh: () => void;
}

/** Poll fn every intervalMs (0 = once). Keeps the last good value and reports the latest error. */
export function usePoll<T>(fn: () => Promise<T>, intervalMs: number, deps: unknown[] = []): Polled<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null; updatedAt: number | null }>(
    { data: null, error: null, updatedAt: null });
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick(t => t + 1), []);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const run = async () => {
      try {
        const data = await fnRef.current();
        if (alive) setState({ data, error: null, updatedAt: Date.now() });
      } catch (e) {
        if (alive) setState(s => ({ ...s, error: (e as Error).message }));
      }
      if (alive && intervalMs > 0) timer = setTimeout(run, intervalMs);
    };
    run();
    return () => { alive = false; if (timer) clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, tick, ...deps]);

  return { ...state, refresh };
}

interface StationContext {
  api: StationApi;
  core: Polled<CoreStatus>;
  chain: Polled<TimingChain>;
  /** True when anything on screen may be synthetic: client demo adapter, or a server in GTP_DEMO mode. */
  isDemo: boolean;
}

const Ctx = createContext<StationContext | null>(null);

export function StationProvider({ api, children }: { api: StationApi; children: ReactNode }) {
  const core = usePoll(() => api.core(), 4000, [api]);
  const chain = usePoll(() => api.timingChain(), 5000, [api]);
  const isDemo = api.source === 'demo' || core.data?.demo === true || !!chain.data?.demo;
  return <Ctx.Provider value={{ api, core, chain, isDemo }}>{children}</Ctx.Provider>;
}

export function useStation(): StationContext {
  const c = useContext(Ctx);
  if (!c) throw new Error('useStation() outside <StationProvider>');
  return c;
}

export interface BrowserClock {
  samples: PingSample[];
  last: PingSample | null;
  minRttMs: number | null;
  medianRttMs: number | null;
  p95RttMs: number | null;
  jitterMs: number | null;
  /** Offset from the lowest-RTT sample (least path asymmetry): station − browser, ms. Inferred. */
  offsetMs: number | null;
  error: string | null;
}

/** Four-timestamp exchange with /api/ping every 3 s, keeping the last 24 samples (as the legacy dashboard does). */
export function useBrowserClock(): BrowserClock {
  const { api } = useStation();
  const [samples, setSamples] = useState<PingSample[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        const s = await pingOnce(api);
        if (alive) { setSamples(xs => [...xs, s].slice(-24)); setError(null); }
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
    };
    const first = setTimeout(run, 500);
    const id = setInterval(run, 3000);
    return () => { alive = false; clearTimeout(first); clearInterval(id); };
  }, [api]);

  const rtts = samples.map(s => s.rttMs).sort((a, b) => a - b);
  const q = (p: number) => (rtts.length ? rtts[Math.min(rtts.length - 1, Math.floor(p * rtts.length))] : null);
  const best = samples.length ? samples.reduce((a, b) => (b.rttMs < a.rttMs ? b : a)) : null;
  const mean = rtts.length ? rtts.reduce((a, b) => a + b, 0) / rtts.length : null;
  const jitter = mean === null || rtts.length < 2 ? null
    : Math.sqrt(rtts.reduce((a, r) => a + (r - mean) ** 2, 0) / (rtts.length - 1));
  return {
    samples, last: samples[samples.length - 1] ?? null,
    minRttMs: rtts[0] ?? null, medianRttMs: q(0.5), p95RttMs: q(0.95), jitterMs: jitter,
    offsetMs: best ? best.offsetMs : null, error,
  };
}
