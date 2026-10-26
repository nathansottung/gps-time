import { createContext, ReactNode, useContext, useState } from 'react';
import { Sensitive } from './screenshot';
import { useStarting } from '../api/station';

// Inside a pending card, or while the station's first answers load, a missing value is
// still loading ("…"), not UNKNOWN. UNKNOWN is only for what the station couldn't establish.
const PendingCtx = createContext(false);

/** The loading mark for one value. */
export function Loading() {
  return <span className="mono text-[12px]" style={{ color:'var(--t3)' }} role="status" aria-busy="true" aria-label="loading">…</span>;
}

// ─── Status Badge ─────────────────────────────────────────────────────────────
type BadgeVariant = 'good'|'warn'|'error'|'info'|'muted'|'demo';
interface BadgeProps { variant?: BadgeVariant; label: string; dot?: boolean; pulse?: boolean; className?: string; }
export function StatusBadge({ variant='muted', label, dot=true, pulse=false, className='' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-[3px] rounded-[2px] text-[9px] font-mono font-medium uppercase tracking-[0.1em] badge-${variant} ${className}`}>
      {dot && <span className={`w-1 h-1 rounded-full bg-current ${pulse ? 'pulse-dot' : ''}`}/>}
      {label}
    </span>
  );
}

// ─── Provenance Tag ───────────────────────────────────────────────────────────
// observed: measured by station hardware · calculated: derived mathematically from observations
// modeled: physical/statistical model output for a present or past quantity
// predicted: forecast of a future value · inferred: reasoned from indirect evidence
// external: obtained from a source outside the station (NTP server, feed, dataset)
export type ProvenanceType = 'observed'|'calculated'|'modeled'|'predicted'|'inferred'|'external';
export function ProvenanceTag({ type }: { type: ProvenanceType }) {
  return (
    <span className={`inline-flex px-1.5 py-[2px] rounded-[2px] text-[8px] font-mono uppercase tracking-[0.12em] tag-${type}`}>
      {type}
    </span>
  );
}

// ─── Maturity Badge ───────────────────────────────────────────────────────────
type Maturity = 'supported'|'experimental'|'research'|'planned'|'demo';
export function MaturityBadge({ level }: { level: Maturity }) {
  return (
    <span className={`inline-flex px-2 py-[3px] rounded-[2px] text-[9px] font-mono font-medium uppercase tracking-[0.08em] mat-${level}`}>
      {level}
    </span>
  );
}

// ─── Section Header ───────────────────────────────────────────────────────────
export function SectionHeader({ title, sub, action, provenance }: {
  title: string; sub?: string; action?: ReactNode; provenance?: ProvenanceType;
}) {
  return (
    <div className="flex items-center justify-between mb-3 pb-2" style={{ borderBottom: '1px solid var(--border-dim)' }}>
      <div className="flex items-center gap-2">
        <span className="text-[9px] font-semibold uppercase tracking-[0.18em]" style={{ color:'var(--t3)' }}>{title}</span>
        {provenance && <ProvenanceTag type={provenance} />}
        {sub && <span className="text-[10px]" style={{ color:'var(--t3)' }}>— {sub}</span>}
      </div>
      {action}
    </div>
  );
}

// ─── Metric Row ───────────────────────────────────────────────────────────────
export function MetricRow({ label, value, unit, uncertainty, provenance, muted, large, sensitive }: {
  label: string; value: string|number|null|undefined; unit?: string; uncertainty?: string|null;
  provenance?: ProvenanceType; muted?: boolean; large?: boolean;
  /** Hidden in screenshot mode (coordinates, heights). */
  sensitive?: boolean;
}) {
  // null/undefined = the station can't establish this value: show UNKNOWN, never a guess.
  // Before the data has arrived (pending card, or the station's first answers) it is loading instead.
  const inPendingCard = useContext(PendingCtx);
  const starting = useStarting();
  const pending = inPendingCard || starting;
  if (value === null || value === undefined) {
    return (
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-[5px] row-sep">
        <span className="text-[11px] min-w-0" style={{ color: muted ? 'var(--t3)' : 'var(--t2)' }}>{label}</span>
        {pending ? <Loading /> : <StatusBadge variant="muted" label="UNKNOWN" dot={false} />}
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-[5px] row-sep">
      <span className="text-[11px] min-w-0" style={{ color: muted ? 'var(--t3)' : 'var(--t2)' }}>{label}</span>
      <div className="flex items-baseline gap-1.5 ml-auto">
        <span className={`mono tabular ${large ? 'text-base' : 'text-[12px]'} font-medium`} style={{ color:'var(--t1)' }}>{sensitive ? <Sensitive>{value}</Sensitive> : value}</span>
        {unit && <span className="text-[10px]" style={{ color:'var(--t3)' }}>{unit}</span>}
        {uncertainty && <span className="text-[10px]" style={{ color:'var(--t3)' }}>± {uncertainty}</span>}
        {provenance && <ProvenanceTag type={provenance} />}
      </div>
    </div>
  );
}

// ─── Scientific Value (large display) ────────────────────────────────────────
export function SciValue({ value, unit, uncertainty, sub, highlight }: {
  value: string; unit?: string; uncertainty?: string; sub?: string; highlight?: boolean;
}) {
  return (
    <div className="flex flex-col">
      <div className="flex items-baseline gap-1.5">
        <span
          className={`mono tabular font-medium ${highlight ? 'text-xl' : 'text-base'}`}
          style={{ color: highlight ? 'var(--live)' : 'var(--t1)' }}
        >{value}</span>
        {unit        && <span className="text-[11px]" style={{ color:'var(--t3)' }}>{unit}</span>}
        {uncertainty && <span className="text-[10px]" style={{ color:'var(--t3)' }}>±{uncertainty}</span>}
      </div>
      {sub && <span className="text-[10px]" style={{ color:'var(--t3)' }}>{sub}</span>}
    </div>
  );
}

// ─── Card ─────────────────────────────────────────────────────────────────────
/** pending: this card's data hasn't arrived yet; its missing values show as loading. */
export function Card({ children, className='', pending=false }: { children: ReactNode; className?: string; pending?: boolean }) {
  const outer = useContext(PendingCtx);
  // Each card is a size container: grids inside it follow the card's width (@md:…), not the window's.
  return (
    <div className={`card-surface @container ${className}`} aria-busy={pending || undefined}>
      <PendingCtx.Provider value={pending || outer}>{children}</PendingCtx.Provider>
    </div>
  );
}

/** A chart, list or table area whose data is loading. */
export function LoadingNote({ what }: { what: string }) {
  return <div className="text-[10px] py-6 text-center" style={{ color:'var(--t3)' }} role="status" aria-busy="true">Loading {what}…</div>;
}

/** A chart, list or table area with nothing to show; says why. */
export function EmptyNote({ children }: { children: ReactNode }) {
  return <div className="text-[10px] py-6 text-center" style={{ color:'var(--t3)' }}>{children}</div>;
}

export function CardHeader({ title, badge, action, icon }: {
  title: string; badge?: ReactNode; action?: ReactNode; icon?: ReactNode;
}) {
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-2.5"
      style={{ borderBottom: '1px solid var(--border-dim)' }}
    >
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 min-w-0">
        {icon && <span style={{ color:'var(--t3)' }}>{icon}</span>}
        <span className="text-[9px] font-semibold uppercase tracking-[0.18em]" style={{ color:'var(--t3)' }}>{title}</span>
        {badge}
      </div>
      {action}
    </div>
  );
}

export function CardBody({ children, className='' }: { children: ReactNode; className?: string }) {
  return <div className={`px-4 py-3 ${className}`}>{children}</div>;
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
interface TabsProps { tabs: string[]; active: string; onChange: (t: string) => void; className?: string; }
export function Tabs({ tabs, active, onChange, className='' }: TabsProps) {
  return (
    <div role="tablist" className={`flex gap-0 overflow-x-auto ${className}`} style={{ borderBottom: '1px solid var(--border)' }}>
      {tabs.map(t => (
        <button key={t} onClick={() => onChange(t)} role="tab" aria-selected={active===t}
          className={`px-4 py-2 text-[10px] font-medium uppercase tracking-[0.1em] whitespace-nowrap flex-shrink-0 transition-colors ${active===t ? 'tab-active' : 'tab-inactive'}`}>
          {t}
        </button>
      ))}
    </div>
  );
}

// ─── ELI5 Expander ────────────────────────────────────────────────────────────
export function ELI5({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-1.5">
      <button onClick={() => setOpen(!open)}
        className="text-[9px] mono underline underline-offset-2 transition-colors"
        style={{ color:'var(--t3)' }}
        onMouseEnter={e=>(e.currentTarget.style.color='var(--t2)')}
        onMouseLeave={e=>(e.currentTarget.style.color='var(--t3)')}>
        {open ? 'hide explanation' : 'what does this mean?'}
      </button>
      {open && (
        <p className="mt-1.5 text-[11px] leading-relaxed italic px-3 py-2 rounded-[2px]"
          style={{ background:'rgba(255,255,255,0.025)', border:'1px solid var(--border-dim)', color:'var(--t2)' }}>
          {text}
        </p>
      )}
    </div>
  );
}

// ─── Demo Banner ──────────────────────────────────────────────────────────────
export function DemoBanner() {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-[2px] text-[10px] mono"
      style={{ background:'var(--demo-bg)', border:'1px solid var(--demo-border)', color:'var(--demo-text)' }}>
      <span className="w-1.5 h-1.5 rounded-full bg-current pulse-dot"/>
      DEMO MODE — All values are synthetic. Not actual measurements.
    </div>
  );
}

// ─── Range Selector ───────────────────────────────────────────────────────────
export function RangeSelector({ ranges, active, onChange }: { ranges: string[]; active: string; onChange: (r: string) => void; }) {
  return (
    <div className="flex gap-1">
      {ranges.map(r => (
        <button key={r} onClick={() => onChange(r)}
          className="px-2 py-[3px] text-[9px] font-mono rounded-[2px] transition-colors"
          style={active===r
            ? { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }
            : { border:'1px solid var(--border)', color:'var(--t3)' }}>
          {r}
        </button>
      ))}
    </div>
  );
}

// ─── Toggle ───────────────────────────────────────────────────────────────────
export function Toggle({ on, onChange, label, disabled }: { on: boolean; onChange: (v:boolean)=>void; label?: string; disabled?: boolean }) {
  return (
    <button onClick={() => onChange(!on)} role="switch" aria-checked={on} aria-label={label} disabled={disabled}
      className={`relative w-9 h-5 rounded-full transition-colors flex-shrink-0 ${on ? 'toggle-on' : 'toggle-off'}`}
      style={disabled ? { opacity: 0.4, cursor: 'not-allowed' } : undefined}>
      <span className={`absolute left-0 top-[2px] h-4 w-4 rounded-full transition-transform ${on ? 'toggle-thumb-on' : 'toggle-thumb-off'}`}/>
    </button>
  );
}

// ─── Tooltip ──────────────────────────────────────────────────────────────────
export function Tooltip({ children, tip }: { children: ReactNode; tip: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-flex" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 text-[10px] mono whitespace-nowrap z-50 rounded-[2px]"
          style={{ background:'var(--float)', border:'1px solid var(--border-em)', color:'var(--t2)', boxShadow:'0 4px 12px rgba(0,0,0,0.5)' }}>
          {tip}
        </span>
      )}
    </span>
  );
}
