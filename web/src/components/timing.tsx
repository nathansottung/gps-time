// Source-aware status banner and timing-chain card (CHG-PPS-HEALTH-DIAGNOSTICS:
// "Main Status Banner", "Dashboard Requirement"). All values come from
// /api/timing-chain; nothing here infers health the station did not report.

import type { ReactNode } from 'react';
import { Card, CardHeader, CardBody, StatusBadge, ProvenanceTag } from './ui';
import { useStation } from '../api/station';
import { fmtDuration, fmtSeconds } from '../lib/format';

import { bannerView, statusVariant, type Variant, type BannerView } from '../lib/banner';
export { bannerView, statusVariant };
export type { Variant, BannerView };

const STYLE: Record<Variant, { bg: string; border: string; text: string }> = {
  good:  { bg: 'var(--good-bg)', border: 'var(--good-border)', text: 'var(--good-text)' },
  warn:  { bg: 'var(--warn-bg)', border: 'var(--warn-border)', text: 'var(--warn-text)' },
  error: { bg: 'var(--err-bg)',  border: 'var(--err-border)',  text: 'var(--err-text)' },
  info:  { bg: 'transparent',    border: 'var(--border)',      text: 'var(--t2)' },
  muted: { bg: 'transparent',    border: 'var(--border)',      text: 'var(--t3)' },
};
export const variantStyle = (v: Variant) => STYLE[v];


/** Full-width banner shown at the top of every page. */
export function TimingBanner() {
  const { chain, core } = useStation();
  const v = bannerView(chain.data, !!(chain.error && !chain.data) || !!(core.error && !core.data && !chain.data));
  const s = STYLE[v.variant];
  return (
    <div className="flex items-start gap-3 px-3 py-2 rounded-[2px]" role="status"
      style={{ background: s.bg, border: `1px solid ${s.border}` }}>
      <span className={`mt-[5px] w-1.5 h-1.5 rounded-full flex-shrink-0 ${v.variant === 'good' ? 'pulse-dot' : ''}`} style={{ background: s.text }} />
      <div className="min-w-0">
        <div className="mono text-[11px] font-medium uppercase tracking-[0.08em]" style={{ color: s.text }}>{v.title}</div>
        {(v.detail || v.outage) && (
          <div className="text-[10px] mt-0.5" style={{ color: 'var(--t2)' }}>
            {v.outage && <span className="mono" style={{ color: s.text }}>{v.outage}. </span>}
            {v.detail}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Timing-chain card ───────────────────────────────────────────────────────

function Row({ k, v, mono = true }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-2 py-[2px] text-[10px]">
      <span style={{ color: 'var(--t3)' }}>{k}</span>
      <span className={mono ? 'mono tabular text-right' : 'text-right'} style={{ color: v === null || v === undefined ? 'var(--t4)' : 'var(--t1)' }}>
        {v === null || v === undefined || v === '' ? 'UNKNOWN' : v}
      </span>
    </div>
  );
}

function Column({ title, state, variant, children }: { title: string; state: string; variant: Variant; children: ReactNode }) {
  const s = STYLE[variant];
  return (
    <div className="rounded-[2px] p-2.5 min-w-0" style={{ background: 'rgba(255,255,255,0.015)', border: '1px solid var(--border-dim)' }}>
      <div className="text-[9px] mono uppercase tracking-[0.14em] mb-1" style={{ color: 'var(--t4)' }}>{title}</div>
      <div className="mono text-[12px] font-medium uppercase mb-1.5 break-words leading-tight" style={{ color: s.text }}>{state}</div>
      {children}
    </div>
  );
}

const STAGE_VARIANT: Record<string, Variant> = {
  OK: 'good', DEGRADED: 'warn', FAILED: 'error', UNKNOWN: 'muted', NOT_OBSERVABLE: 'muted', NOT_APPLICABLE: 'muted', INFO: 'info',
};
export const stageVariant = (s: string | undefined): Variant => (s ? STAGE_VARIANT[s] ?? 'muted' : 'muted');

const PULSE_VARIANT: Record<string, Variant> = { HEALTHY: 'good', DEGRADED: 'warn', LOST: 'error' };
const CHRONY_PPS_VARIANT = (s: string) => (s === 'SELECTED' ? 'good' : s === 'UNKNOWN' ? 'muted' : 'warn');

export function fmtAge(s: number | null | undefined): string | null {
  if (s === null || s === undefined) return null;
  return s < 60 ? `${s.toFixed(2)} s ago` : `${fmtDuration(s)} ago`;
}

/** GNSS → PPS device → PPS signal → chrony PPS → system clock, in the spec's order. */
export function TimingChainCard({ onOpenDiagnostics }: { onOpenDiagnostics?: () => void }) {
  const { chain } = useStation();
  const c = chain.data;
  if (!c) {
    return (
      <Card>
        <CardHeader title="Timing Status" badge={<StatusBadge variant="muted" label="UNKNOWN" />} />
        <CardBody><div className="text-[11px]" style={{ color: 'var(--t3)' }}>
          {chain.error ? `Timing chain not available: ${chain.error}` : 'Loading timing chain…'}</div></CardBody>
      </Card>
    );
  }
  const g = c.gnss, p = c.pps, ch = c.chrony;
  const gnssState = g.healthy === true ? 'HEALTHY' : g.healthy === false ? 'UNHEALTHY' : 'UNKNOWN';
  const devPresent = p.device_present.value;
  const ref = ch.pps;
  const view = bannerView(c, false);
  const sysLabel = view.title.split('·').slice(1).join('·').trim() || c.status.headline;
  const off = ref?.offset_s.value;
  return (
    <Card>
      <CardHeader title="Timing Status — GNSS → PPS → chrony" badge={<ProvenanceTag type="observed" />}
        action={onOpenDiagnostics && (
          <button onClick={onOpenDiagnostics} className="px-2.5 py-[3px] text-[10px] mono rounded-[2px]"
            style={{ border: '1px solid var(--border)', color: 'var(--t2)' }}>PPS diagnostics →</button>)} />
      <CardBody>
        <div className="grid grid-cols-1 @sm:grid-cols-2 @xl:grid-cols-3 @4xl:grid-cols-5 gap-2">
          <Column title="GNSS" state={gnssState} variant={g.healthy === true ? 'good' : g.healthy === false ? 'error' : 'muted'}>
            <Row k="Satellites used / visible" v={g.satellites_used?.value != null ? `${g.satellites_used.value} / ${g.satellites_visible?.value ?? '—'}` : null} />
            <Row k="TDOP" v={g.tdop?.value ?? null} />
            <Row k="Best C/N₀" v={g.best_cn0?.value != null ? `${g.best_cn0.value} dB-Hz` : null} />
          </Column>
          <Column title="PPS device" state={devPresent === true ? 'PRESENT' : devPresent === false ? 'MISSING' : 'UNKNOWN'}
            variant={devPresent === true ? 'good' : devPresent === false ? 'error' : 'muted'}>
            <Row k="Device" v={p.device.value} />
            <Row k="GPIO" v={p.boot_config?.gpio ?? null} />
          </Column>
          <Column title="PPS signal (kernel)" state={p.pulse_health || 'UNKNOWN'} variant={PULSE_VARIANT[p.pulse_health] ?? 'muted'}>
            <Row k="Last pulse" v={fmtAge(p.age_s?.value)} />
            <Row k="Rate" v={p.rate_hz?.value != null ? `${p.rate_hz.value.toFixed(6)} Hz` : null} />
          </Column>
          <Column title="chrony PPS" state={(ch.pps_status || 'UNKNOWN').replace(/_/g, ' ')} variant={CHRONY_PPS_VARIANT(ch.pps_status)}>
            <Row k="Refclock" v={ch.refclocks.pps} />
            <Row k="Reach" v={ref?.reach.value ?? null} />
            <Row k="Last sample" v={ref?.reach.value === '0' ? 'no samples' : off != null ? `${off >= 0 ? '+' : '−'}${fmtSeconds(off)}` : null} />
            {ref && (
              <div className="text-[9px] mt-1 leading-snug" style={{ color: 'var(--t3)' }}>
                <span className="mono" style={{ color: 'var(--t1)' }}>{ref.state_symbol.value ?? '?'}</span> {ref.state_meaning}
              </div>
            )}
          </Column>
          <Column title="System clock" state={sysLabel} variant={view.variant}>
            <Row k="Current source" v={ch.selected ? `${ch.selected.name} (${ch.selected.kind})` : null} />
            <Row k="Stratum" v={ch.tracking?.stratum ?? null} />
            <Row k="PPS unavailable/unused for" v={c.events.open ? fmtDuration(c.events.open.duration_s) : 'no open outage'} mono={!!c.events.open} />
          </Column>
        </div>
        <div className="text-[9px] mt-2" style={{ color: 'var(--t4)' }}>
          The receiver's PPS output itself is not observable by software; PPS signal values are Linux kernel timestamps.
        </div>
      </CardBody>
    </Card>
  );
}
