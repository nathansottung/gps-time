// GNSS & Site → Sky Obstruction: the learned sky-obstruction map (GET /api/sky-obstruction).
// Read only. Logic: lib/skymap.ts; classes come from the station (gps_time_pi/skymap.py).
import { useState } from 'react';
import { Card, CardHeader, CardBody, EmptyNote, ELI5, LoadingNote, MetricRow, ProvenanceTag, StatusBadge, Toggle } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll, isPending } from '../api/station';
import type { SkyObstruction, SkyObstructionResult } from '../api/types';
import {
  CLASS_LABEL, CN0_HI, CN0_LO, cellPath, cellShade, cellTitle, lossRows, lossTotals, lossVariant, sectorVariant,
  summaryLine, type ShadeBy,
} from '../lib/skymap';

const RING = 'rgba(255,255,255,0.05)';
const swatch = (fill: string, opacity: number) => ({ background: `color-mix(in srgb, ${fill} ${Math.round(opacity * 100)}%, transparent)` });

function PolarMap({ m, by }: { m: SkyObstruction; by: ShadeBy }) {
  const sz = 240, cx = sz / 2, cy = sz / 2, r = sz / 2 - 18;
  return (
    <svg width={sz} height={sz} viewBox={`0 0 ${sz} ${sz}`} style={{ maxWidth: '100%', height: 'auto' }}
      data-layout-ok="plot" role="img" aria-label="Learned sky-obstruction map, north up, east right">
      {m.cells.map(c => {
        const s = cellShade(c, by);
        return (
          <path key={`${c.az0}-${c.el0}`} d={cellPath(c, m.az_step, m.el_step, cx, cy, r)} fill={s.fill} fillOpacity={s.opacity} stroke="none">
            <title>{cellTitle(c, m.az_step, m.el_step)}</title>
          </path>
        );
      })}
      {[0, 30, 60].map(el => (
        <circle key={el} cx={cx} cy={cy} r={(1 - el / 90) * r} fill="none" stroke={RING} strokeWidth={el === 0 ? 1 : 0.5} />
      ))}
      {[0, 45, 90, 135].map(a => {
        const rad = (a - 90) * Math.PI / 180;
        return <line key={a} x1={cx - r * Math.cos(rad)} y1={cy - r * Math.sin(rad)} x2={cx + r * Math.cos(rad)} y2={cy + r * Math.sin(rad)} stroke={RING} strokeWidth={0.5} />;
      })}
      {[{ l: 'N', x: cx, y: 11, a: 'middle' }, { l: 'E', x: sz - 6, y: cy + 3, a: 'end' },
        { l: 'S', x: cx, y: sz - 4, a: 'middle' }, { l: 'W', x: 7, y: cy + 3, a: 'start' }].map(t => (
        <text key={t.l} x={t.x} y={t.y} textAnchor={t.a as 'middle' | 'end' | 'start'} fontSize="8" fill="var(--t3)" fontFamily="JetBrains Mono">{t.l}</text>
      ))}
      <text x={cx + 2} y={cy - r / 3 + 2} fontSize="7" fill="var(--t3)" fontFamily="JetBrains Mono">60°</text>
      <text x={cx + 2} y={cy - r * 2 / 3 + 2} fontSize="7" fill="var(--t3)" fontFamily="JetBrains Mono">30°</text>
    </svg>
  );
}

function Legend({ by }: { by: ShadeBy }) {
  if (by === 'cn0') {
    const lo = cellShade({ cn0_mean: CN0_LO } as never, 'cn0'), hi = cellShade({ cn0_mean: CN0_HI } as never, 'cn0');
    return (
      <div className="flex flex-wrap items-center gap-2 text-[10px] mono" style={{ color: 'var(--t3)' }}>
        <span className="tabular">{CN0_LO}</span>
        <span aria-hidden className="inline-block h-2 w-20 rounded-[2px]"
          style={{ background: `linear-gradient(to right, ${swatch(lo.fill, lo.opacity).background}, ${swatch(hi.fill, hi.opacity).background})` }} />
        <span className="tabular">{CN0_HI} dB-Hz</span>
        <span>· mean C/N₀ per cell</span>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] mono" style={{ color: 'var(--t3)' }}>
      {(['clear', 'attenuated', 'blocked', 'unknown'] as const).map(k => {
        const s = cellShade({ class: k, cn0_mean: null } as never, 'class');
        return (
          <span key={k} className="flex items-center gap-1">
            <span aria-hidden className="w-3 h-2 inline-block rounded-[2px]" style={swatch(s.fill, Math.max(s.opacity, 0.3))} />{CLASS_LABEL[k]}
          </span>
        );
      })}
    </div>
  );
}

export function SkyObstructionPanel() {
  const { api } = useStation();
  const poll = usePoll<SkyObstructionResult>(() => api.skyObstruction(), 60_000, [api]);
  const [by, setBy] = useState<ShadeBy>('class');
  const d = poll.data;

  if (d && !d.available) {
    return (
      <Card>
        <CardHeader title="Learned Sky Obstruction" />
        <CardBody><EmptyNote>{d.reason}</EmptyNote></CardBody>
      </Card>
    );
  }
  const m = d && d.available ? d : null;
  const sum = m ? summaryLine(m) : null;
  const pending = isPending(poll);
  // After a failed request: say so, never an endless loading state.
  const waiting = (what: string) => pending ? <LoadingNote what={what} /> : <EmptyNote>Not available: the station did not answer.</EmptyNote>;
  return (
    <div className="space-y-4">
      <ApiErrorNote error={poll.error} />
      <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
        <Card pending={pending}>
          <CardHeader title="Learned Sky Obstruction" badge={<ProvenanceTag type="inferred" />} />
          <CardBody className="flex flex-col items-center py-4">
            {!m ? waiting('the sky-obstruction map') : (
              <>
                <div className="flex gap-1 mb-3" role="group" aria-label="Shade the map by">
                  {(['class', 'cn0'] as ShadeBy[]).map(k => (
                    <button key={k} onClick={() => setBy(k)} aria-pressed={by === k}
                      className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
                      style={by === k ? { border: '1px solid var(--accent)', color: 'var(--accent)', background: 'var(--accent-dim)' }
                        : { border: '1px solid var(--border)', color: 'var(--t3)' }}>
                      {k === 'class' ? 'obstruction' : 'C/N₀'}
                    </button>
                  ))}
                </div>
                <PolarMap m={m} by={by} />
                <div className="mt-2"><Legend by={by} /></div>
                <div className="mt-3 w-full">
                  <div className="text-[11px] mb-2" style={{ color: 'var(--t2)' }}>{sum!.text}</div>
                  <MetricRow label="Satellite-minutes recorded" value={m.summary.satellite_minutes} provenance="observed" />
                  <MetricRow label="Cells with data" value={`${m.summary.cells_with_data} of ${m.summary.cells_total}`} />
                  <MetricRow label="Receiver lists untracked satellites" value={m.summary.untracked_reported ? 'yes' : 'not seen'} />
                  <MetricRow label="Saved to SD" value={m.file.last_write_utc ? m.file.last_write_utc.replace('T', ' ').replace('Z', ' UTC') : 'not yet (hourly)'} />
                </div>
                {m.file.problems.map(p => (
                  <div key={p} className="text-[10px] mt-1 w-full" style={{ color: 'var(--warn-text)' }}>{p}</div>
                ))}
                <div className="mt-3 p-2 rounded-[2px] text-[10px] w-full" style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--t3)' }}>
                  {m.note}
                </div>
              </>
            )}
          </CardBody>
        </Card>

        <Card pending={pending}>
          <CardHeader title="Sectors" badge={<ProvenanceTag type="inferred" />} />
          <CardBody>
            {!m ? waiting('the sectors') : (
              <>
                {m.sectors.map(s => (
                  <div key={s.sector} className="flex items-center justify-between gap-2 py-[5px]" style={{ borderBottom: '1px solid var(--border)' }}>
                    <span className="mono text-[11px] w-8" style={{ color: 'var(--t1)' }}>{s.sector}</span>
                    <span className="text-[11px] flex-1" style={{ color: 'var(--t2)' }}>{s.text}</span>
                    <StatusBadge variant={sectorVariant(s.state)} label={s.state.toUpperCase()} dot={false} />
                  </div>
                ))}
                <ELI5 text="The station learns which directions its antenna normally hears well. A satellite lost where the sky is normally blocked is expected; one lost where the sky is normally clear is worth a look. The map never says what is in the way." />
              </>
            )}
          </CardBody>
        </Card>
      </div>

      <Card pending={pending}>
        <CardHeader title="Satellite Losses" badge={<ProvenanceTag type="inferred" />} />
        <CardBody>
          {!m ? waiting('satellite losses') : (
            <>
              <div className="text-[11px] mb-2" style={{ color: 'var(--t2)' }}>{lossTotals(m)}</div>
              {m.sky_wide.count > 0 && (
                <div className="text-[11px] mb-2" style={{ color: 'var(--warn-text)' }}>
                  Sky-wide C/N₀ drops: {m.sky_wide.count}. {m.sky_wide.recent[0]?.note}
                </div>
              )}
              {m.losses.recent.length === 0 ? <EmptyNote>No satellite lost since the service started.</EmptyNote> : (
                <div className="table-scroll"><table className="w-full text-[11px]">
                  <thead><tr style={{ color: 'var(--t3)' }}>
                    {['Time', 'Satellite', 'Az / El', 'Class', 'Why'].map(h => <th key={h} className="text-left font-normal px-2 py-1">{h}</th>)}
                  </tr></thead>
                  <tbody>
                    {lossRows(m).map((l, i) => (
                      <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                        <td className="px-2 py-1 mono tabular" style={{ color: 'var(--t2)' }}>{l.when}</td>
                        <td className="px-2 py-1 mono" style={{ color: 'var(--t1)' }}>{l.sat}</td>
                        <td className="px-2 py-1 mono tabular" style={{ color: 'var(--t2)' }}>{l.dir}</td>
                        <td className="px-2 py-1"><StatusBadge variant={lossVariant(l.cls)} label={l.cls} dot={false} /></td>
                        <td className="px-2 py-1" style={{ color: 'var(--t3)' }}>{l.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>
              )}
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

/** Administration → Capability record: what the station would publish, and the sky-quality opt-in. */
export function CapabilityCard({ canWrite, authKnown, onAuthError }: { canWrite: boolean; authKnown: boolean; onAuthError: () => void }) {
  const { api, core } = useStation();
  const mode = core.data?.location.mode;
  const cap = usePoll(() => api.capability(), 60_000, [api, mode]);   // re-read when the privacy mode changes
  const [msg, setMsg] = useState<string | null>(null);
  const c = cap.data;
  const hidden = mode === 'hidden';
  const share = async (on: boolean) => {
    try {
      const r = await api.setSkyQualityShare(on);
      setMsg(r.ok ? (on ? 'The sky-quality summary is included.' : 'The sky-quality summary is left out.') : 'The station rejected the setting.');
      cap.refresh();
    } catch (e) { setMsg((e as Error).message); onAuthError(); }
  };
  const q = c?.sky_quality;
  return (
    <Card pending={isPending(cap)}>
      <CardHeader title="Capability record" />
      <CardBody>
        <ApiErrorNote error={cap.error} />
        <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>
          What this station is and can do, in the form a coordinator join carries (GET /api/capability). It never holds an exact position.
        </div>
        <MetricRow label="Station ID" value={c ? (c.station_id ?? 'no station key') : null} />
        <MetricRow label="Timing" value={c ? [c.timing.state, c.timing.source].filter(Boolean).join(' · ') || null : null} provenance="calculated" />
        <MetricRow label="Location" value={c ? (c.location.lat === null ? c.location.precision : `${c.location.lat}, ${c.location.lon} (${c.location.precision})`) : null} sensitive />
        <div className="flex items-center justify-between gap-3 mt-3">
          <div>
            <div className="text-[11px]" style={{ color: 'var(--t1)' }}>Include the sky-quality summary</div>
            <div className="text-[10px]" style={{ color: 'var(--t3)' }}>
              Off by default. The eight sectors of the learned sky-obstruction map, in the capability record and the diagnostics export; never the grid or any time. Never in hidden mode.
            </div>
          </div>
          <Toggle on={!!c?.sky_quality_opt_in} onChange={share} label="Include the sky-quality summary" disabled={!c || !canWrite} />
        </div>
        <MetricRow label="Sky quality in the record" value={c ? (q ? `${q.state}, ${q.days} days, ${q.clear_pct ?? '—'} % clear` : `not included (${c.sky_quality_note})`) : null} provenance={q ? 'inferred' : undefined} />
        {hidden && c?.sky_quality_opt_in && (
          <div className="text-[10px] mt-1" style={{ color: 'var(--t3)' }}>Opted in, but location privacy is hidden: nothing is included.</div>
        )}
        {!canWrite && authKnown && (
          <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>Changing this needs an admin sign-in (Admin sign-in, at the top).</div>
        )}
        {msg && <div className="text-[10px] mono mt-2" style={{ color: 'var(--t3)' }}>{msg}</div>}
      </CardBody>
    </Card>
  );
}
