import { useState, useEffect } from 'react';
import { formatUtc, unixSeconds } from './lib/localtime';
import { HourToggle, useStationTime } from './components/clock';
import { DemoBanner } from './components/ui';
import { ScreenshotToggle, Sensitive } from './components/screenshot';
import { NightOverlay, ThemeToggle, useModules } from './components/prefs';
import { visiblePage } from './lib/prefs';
import { hashFor, pageFromHash } from './lib/route';
import Overview from './pages/Overview';
import Timing from './pages/Timing';
import GNSS from './pages/GNSS';
import RadioSDR from './pages/RadioSDR';
import Configure from './pages/Configure';
import { SunAstronomy, Network, Aviation, Distributed, DataLogs, Admin } from './pages/Secondary';
import { useStation } from './api/station';
import PPS from './pages/PPS';
import { UI_VERSION, versionLine } from './lib/version';
import { TimingBanner, bannerView, statusVariant, variantStyle } from './components/timing';

// ─── Nav structure ────────────────────────────────────────────────────────────
const NAV = [
  { id:'overview',    label:'Overview',             icon:'○',  group:'' },
  { id:'timing',      label:'Timing & Reliability', icon:'∿',  group:'Measurement' },
  { id:'pps',         label:'PPS Diagnostics',      icon:'⏚',  group:'Measurement' },
  { id:'gnss',        label:'GNSS & Site',          icon:'◎',  group:'Measurement' },
  { id:'sun',         label:'Sun & Astronomy',      icon:'☀',  group:'Measurement' },
  { id:'network',     label:'Network & Devices',    icon:'⊕',  group:'Station' },
  { id:'radio',       label:'Radio & SDR',          icon:'≋',  group:'Station' },
  { id:'aviation',    label:'Aviation',             icon:'✈',  group:'Station' },
  { id:'distributed', label:'Distributed Obs.',     icon:'⊗',  group:'Research',  maturity:'research' },
  { id:'data',        label:'Data & Logs',          icon:'▤',  group:'System' },
  { id:'configure',   label:'Configure',            icon:'⊞',  group:'System' },
  { id:'admin',       label:'Administration',       icon:'⚙',  group:'System' },
];
const GROUPS = ['', 'Measurement', 'Station', 'Research', 'System'];

// ─── Header ───────────────────────────────────────────────────────────────────
function Header({ navOpen, onMenu }: { navOpen: boolean; onMenu: () => void }) {
  const { core, chain, isDemo } = useStation();
  // Same guarded text as the page banner; /api's copy is used only when the chain is unavailable.
  const unreachable = !chain.data && !!(chain.error || core.error);
  const view = chain.data || !core.data?.timing_status
    ? bannerView(chain.data, unreachable)
    : { variant: statusVariant(core.data.timing_status.code), title: core.data.timing_status.banner, detail: core.data.timing_status.detail };
  const st = variantStyle(view.variant);
  // Stratum/reference from the timing chain (the same snapshot as the banner). /api is used only
  // when there is no chain at all, never to fill a value the chain reports as unknown.
  const trk = chain.data ? chain.data.chrony.tracking : null;
  const stratum = (chain.data ? trk?.stratum : core.data?.quality.stratum) || 'UNKNOWN';
  const reference = (chain.data ? trk?.reference : core.data?.quality.reference) || 'UNKNOWN';
  const stationName = typeof window !== 'undefined' ? window.location.hostname : '';
  // Header clock: the same station time as the big clock on the Overview (components/clock.tsx).
  const time = useStationTime();
  const { zone, local } = time;
  const now = time.now.at;
  const basisNote = time.now.basis === 'station' ? "station clock, read through this browser" : "this browser's clock (station time not measured yet)";

  return (
    <header
      className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 px-3 sm:px-5 min-h-11 py-1.5 flex-shrink-0 select-none"
      style={{ background:'var(--nav)', borderBottom:'1px solid var(--border)' }}
    >
      {/* Left — identity; the menu button opens the navigation drawer below 1024 px */}
      <div className="flex items-center gap-3 min-w-0">
        <button onClick={onMenu} className="lg:hidden px-1.5 py-[3px] text-[11px] mono rounded-[2px]"
          aria-label={navOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={navOpen} aria-controls="gtp-nav"
          style={{ border:'1px solid var(--border)', color:'var(--t2)' }}>☰</button>
        {/* Instrument mark */}
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
          <circle cx="9" cy="9" r="7.5" stroke="var(--accent)" strokeWidth="1"/>
          <circle cx="9" cy="9" r="2" fill="var(--live)" fillOpacity="0.5" stroke="var(--live)" strokeWidth="0.75"/>
          {[0,90,180,270].map(a => {
            const r = a*Math.PI/180;
            return <line key={a}
              x1={9+4*Math.sin(r)} y1={9-4*Math.cos(r)}
              x2={9+6*Math.sin(r)} y2={9-6*Math.cos(r)}
              stroke="var(--accent)" strokeWidth="0.8" strokeOpacity="0.6"/>;
          })}
        </svg>
        <span className="mono text-[12px] font-semibold tracking-tight" style={{ color:'var(--t1)' }}>GPS Time</span>
        <span className="hidden sm:inline text-[9px] mono" style={{ color:'var(--t4)' }}>|</span>
        <span className="hidden sm:inline text-[11px] truncate" style={{ color:'var(--t3)' }}><Sensitive>{stationName}</Sensitive></span>
      </div>

      {/* Centre — station state chips (stratum and reference from 768 px) */}
      <div className="flex flex-wrap items-center gap-2 min-w-0">
        {/* Timing status from /api/timing-chain (calculated) */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-[2px]" title={view.detail ?? undefined}
          style={{ background: st.bg, border:`1px solid ${st.border}` }}>
          <span className={`w-1 h-1 rounded-full ${view.variant === 'good' ? 'pulse-dot' : ''}`} style={{ background: st.text }}/>
          <span className="mono text-[9px] font-medium uppercase tracking-[0.1em]" style={{ color: st.text }}>{view.title}</span>
        </div>

        <Chip label="STRATUM" value={stratum} className="hidden md:flex" />
        <Chip label="REF" value={reference} className="hidden md:flex" />

        {isDemo && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-[2px]"
            style={{ background:'var(--demo-bg)', border:'1px solid var(--demo-border)' }}>
            <span className="mono text-[9px] font-medium uppercase tracking-[0.1em]" style={{ color:'var(--demo-text)' }}>
              DEMO
            </span>
          </div>
        )}
      </div>

      {/* Right — time display (its own full-width row on narrow screens) */}
      <div className="flex items-center gap-x-3 gap-y-1.5 max-sm:w-full max-sm:flex-wrap max-sm:justify-between">
        <div className="text-right whitespace-nowrap" title={`${local.date} · ${zone.tz} — ${zone.label}; ${basisNote}. Display only; the station keeps UTC.`}>
          <div className="mono text-[12px] tabular font-medium" style={{ color:'var(--t1)', letterSpacing:'0.02em' }}>
            {local.time}{local.abbr && <span style={{ color:'var(--t2)' }}> {local.abbr}</span>}
            <span className="text-[9px]" style={{ color:'var(--t3)' }}> {local.offset}{local.dst ? ' · DST' : ''}</span>
          </div>
          <div className="mono text-[9px] tabular" style={{ color:'var(--t3)', marginTop:'1px' }}>
            UTC {formatUtc(now)}<span className="hidden md:inline"> · UNIX {unixSeconds(now)}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <HourToggle t={time} />
          <ThemeToggle />
          <ScreenshotToggle />
        </div>
      </div>
    </header>
  );
}

function Chip({ label, value, className = 'flex' }: { label: string; value?: string; className?: string }) {
  return (
    <div className={`${className} items-center gap-1.5 px-2.5 py-1 rounded-[2px]`}
      style={{ background:'rgba(255,255,255,0.030)', border:'1px solid var(--border)' }}>
      <span className="mono text-[9px] tracking-[0.08em]" style={{ color:'var(--t3)' }}>{label}</span>
      {value && <span className="mono text-[9px] font-medium" style={{ color:'var(--t2)' }}>{value}</span>}
    </div>
  );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
function Sidebar({ active, onNavigate, open }: { active: string; onNavigate: (id: string) => void; open: boolean }) {
  const { core } = useStation();
  const [modules] = useModules();
  return (
    <nav id="gtp-nav" aria-label="Pages"
      className={`w-[188px] flex-shrink-0 flex flex-col overflow-y-auto max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:z-40 transition-transform ${open ? '' : 'max-lg:-translate-x-full max-lg:invisible'}`}
      style={{ background:'var(--nav)', borderRight:'1px solid var(--border)' }}
    >
      <div className="flex-1 py-2">
        {GROUPS.map(group => {
          const items = NAV.filter(n => (n.group||'') === group && !modules.hiddenPages.includes(n.id));
          if (!items.length) return null;
          return (
            <div key={group} className={group ? 'mt-1' : ''}>
              {group && (
                <div className="px-4 pt-3 pb-1 text-[8px] mono uppercase tracking-[0.18em]" style={{ color:'var(--t4)' }}>
                  {group}
                </div>
              )}
              {items.map(item => (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)} aria-current={active===item.id ? 'page' : undefined}
                  className={`nav-item w-full text-left flex items-center gap-2.5 px-4 py-[7px] text-[11px] ${active===item.id ? 'active' : ''}`}
                  style={{ color: active===item.id ? 'var(--t1)' : 'var(--t2)' }}
                >
                  <span className="nav-icon text-[12px] w-4 text-center flex-shrink-0"
                    style={{ color: active===item.id ? 'var(--accent)' : 'var(--t4)' }}>
                    {item.icon}
                  </span>
                  <span className="truncate">{item.label}</span>
                  {item.maturity === 'research' && (
                    <span className="ml-auto text-[7px] mono uppercase tracking-wider flex-shrink-0 px-1 py-0.5 rounded-[2px]"
                      style={{ color:'var(--mod-text)', border:'1px solid var(--mod-border)', background:'var(--mod-bg)' }}>R</span>
                  )}
                </button>
              ))}
            </div>
          );
        })}
      </div>

      {/* Build info */}
      <div className="px-4 py-3" style={{ borderTop:'1px solid var(--border-dim)' }}>
        <div className="text-[8px] mono leading-relaxed" style={{ color:'var(--t4)' }}>
          {versionLine(UI_VERSION, core.data ? core.data.versions.app : core.error ? null : undefined)} · MIT License
        </div>
      </div>
    </nav>
  );
}

// ─── Router ───────────────────────────────────────────────────────────────────
function PageContent({ page, onNavigate }: { page: string; onNavigate: (id: string) => void }) {
  switch (page) {
    case 'overview':    return <Overview onNavigate={onNavigate} />;
    case 'timing':      return <Timing onNavigate={onNavigate} />;
    case 'pps':         return <PPS />;
    case 'gnss':        return <GNSS />;
    case 'sun':         return <SunAstronomy />;
    case 'network':     return <Network />;
    case 'radio':       return <RadioSDR />;
    case 'aviation':    return <Aviation />;
    case 'distributed': return <Distributed />;
    case 'data':        return <DataLogs />;
    case 'configure':   return <Configure />;
    case 'admin':       return <Admin />;
    default:            return <Overview onNavigate={onNavigate} />;
  }
}

// ─── Shell ────────────────────────────────────────────────────────────────────
export default function App() {
  // The page lives in the URL hash (lib/route.ts): reloads and bookmarks keep it.
  const [chosen, setChosen] = useState<string>(() => pageFromHash(window.location.hash));
  useEffect(() => {
    const onHash = () => setChosen(pageFromHash(window.location.hash));
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  const setPage = (id: string) => {
    setChosen(id);
    const h = hashFor(id);
    if (window.location.hash !== h) history.pushState(null, '', h || window.location.pathname + window.location.search);
  };
  const { isDemo } = useStation();
  const [modules] = useModules();
  const page = visiblePage(chosen, modules);   // a page hidden on Configure falls back to the Overview
  // Navigation drawer below 1024 px (Guidelines → Layout → Narrow screens); closed by navigating, the backdrop or Escape.
  const [navOpen, setNavOpen] = useState(false);
  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setNavOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navOpen]);
  const navigate = (id: string) => { setPage(id); setNavOpen(false); };

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background:'var(--bg)' }}>
      <NightOverlay />
      <Header navOpen={navOpen} onMenu={() => setNavOpen(o => !o)} />
      <div className="flex flex-1 overflow-hidden">
        {navOpen && <div className="lg:hidden fixed inset-0 z-30" style={{ background:'rgba(0,0,0,0.55)' }}
          onClick={() => setNavOpen(false)} aria-hidden />}
        <Sidebar active={page} onNavigate={navigate} open={navOpen} />
        <main className="@container flex-1 min-w-0 overflow-y-auto p-3 sm:p-5 space-y-4">
          {isDemo && <DemoBanner />}
          <TimingBanner />
          <PageContent page={page} onNavigate={navigate} />
        </main>
      </div>
    </div>
  );
}
