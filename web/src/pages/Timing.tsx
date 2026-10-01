import { useState } from 'react';
import { Card, CardHeader, CardBody, MetricRow, StatusBadge, ELI5, RangeSelector, Tabs, SectionHeader, ProvenanceTag } from '../components/ui';
import { OffsetChart, PPSTimeline, HoldoverScatter, OutageBarChart } from '../components/charts';
import { offset1h, offset24h, offset7d, ppsOutages, ppsStats, errorBudget } from '../data/demo';

const RANGES = ['1h','24h','7d'];

// ─── Time-to-error thresholds ─────────────────────────────────────────────────
const thresholds = [
  { label:'±1 µs',   tRaw: 0.007,  tTrained: 0.3,   region:'observed'  },
  { label:'±10 µs',  tRaw: 0.07,   tTrained: 3.1,   region:'observed'  },
  { label:'±100 µs', tRaw: 0.7,    tTrained: 31,    region:'modeled'   },
  { label:'±1 ms',   tRaw: 6.9,    tTrained: 308,   region:'modeled'   },
  { label:'±10 ms',  tRaw: 69,     tTrained: 3080,  region:'extrapolated'},
  { label:'±100 ms', tRaw: 694,    tTrained: 30800, region:'extrapolated'},
  { label:'±1 s',    tRaw: 6944,   tTrained: 308000,region:'extrapolated'},
];

const regionBg: Record<string,string> = {
  observed:     'bg-cyan-400/20',
  modeled:      'bg-purple-400/15',
  extrapolated: 'bg-slate-500/10',
};
const regionTextVar: Record<string,string> = {
  observed:     'var(--live)',
  modeled:      'var(--mod-text)',
  extrapolated: 'var(--t3)',
};
const regionLabel: Record<string,string> = {
  observed:'OBSERVED',modeled:'MODELED',extrapolated:'EXTRAPOLATED',
};

// ─── Light distance table ─────────────────────────────────────────────────────
const lightDistRows = [
  { dt:'1 s',    dist:'299,792 km', note:'~1.28 × Moon distance' },
  { dt:'1 ms',   dist:'299.8 km',   note:'New York to Philadelphia' },
  { dt:'1 µs',   dist:'299.8 m',    note:'3 football fields' },
  { dt:'100 ns', dist:'30.0 m',     note:'10-story building' },
  { dt:'10 ns',  dist:'3.0 m',      note:'One step' },
  { dt:'1 ns',   dist:'0.30 m',     note:'Palm of hand' },
  { dt:'12.3 ns (current)', dist:'3.69 m', note:'Station current Δt', highlight:true },
];

// ─── Error Budget ─────────────────────────────────────────────────────────────
function ErrorBudget() {
  return (
    <Card>
      <CardHeader title="Timing Error Budget" badge={<ProvenanceTag type="modeled" />} />
      <CardBody>
        <div className="text-[10px] mb-3" style={{ color:'var(--t3)' }}>Signal chain from satellite reference to application. Corrections applied where calibrated.</div>
        <div className="space-y-0">
          {errorBudget.map((s, i) => (
            <div key={i} className="flex items-center gap-3 py-2" style={{ borderBottom:'1px solid var(--border)', ...(i===0?{borderTop:'1px solid var(--border)'}:{}) }}>
              <div className="flex items-center gap-2 w-52">
                {i < errorBudget.length-1 && (
                  <svg width="8" height="16" viewBox="0 0 8 16"><line x1="4" y1="0" x2="4" y2="16" stroke="#2c3040" strokeWidth="1"/><polygon points="4,14 1,10 7,10" fill="#2c3040"/></svg>
                )}
                {i === errorBudget.length-1 && <span className="w-2"/>}
                <span className="text-[11px]" style={{ color:'var(--t2)' }}>{s.stage}</span>
              </div>
              <div className="flex-1 grid grid-cols-4 gap-3 text-[10px]">
                <div>
                  <div style={{ color:'var(--t3)' }}>Nominal</div>
                  <div className="mono" style={{ color:'var(--t2)' }}>{s.nominalNs} ns</div>
                </div>
                <div>
                  <div style={{ color:'var(--t3)' }}>Correction</div>
                  <div className="mono" style={{ color:'var(--t2)' }}>{s.corrNs > 0 ? `−${s.corrNs}` : '—'} {s.corrNs > 0 ? 'ns' : ''}</div>
                </div>
                <div>
                  <div style={{ color:'var(--t3)' }}>Uncertainty</div>
                  <div className="mono" style={{ color:'var(--t2)' }}>±{s.uncertNs} ns</div>
                </div>
                <div>
                  <div style={{ color:'var(--t3)' }}>Calibrated</div>
                  <div className="font-mono" style={{ color: s.calibrated ? 'var(--good-text)' : 'var(--t3)' }}>{s.calibrated ? '✓' : '—'}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function Timing() {
  const [range, setRange] = useState('1h');
  const [tab, setTab] = useState('Overview');

  const dataMap: Record<string, typeof offset1h> = { '1h': offset1h, '24h': offset24h, '7d': offset7d };

  return (
    <div className="space-y-4 page-enter">
      <div className="flex items-baseline justify-between">
        <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Timing & Reliability</h1>
        <StatusBadge variant="good" label="GPS PPS LOCKED" pulse />
      </div>

      <Tabs tabs={['Overview','PPS Stats','Error Budget','Light Distance']} active={tab} onChange={setTab} />

      {tab === 'Overview' && (
        <div className="space-y-4">
          {/* Offset history */}
          <Card>
            <CardHeader
              title="Time Offset History — Δt"
              badge={<ProvenanceTag type="observed" />}
              action={<RangeSelector ranges={RANGES} active={range} onChange={setRange} />}
            />
            <CardBody>
              <OffsetChart data={dataMap[range]} range={range} />
              <div className="mt-4">
                <div className="text-[9px] font-semibold uppercase tracking-[0.18em] mb-1" style={{ color:'var(--t3)' }}>PPS State Availability (today)</div>
                <PPSTimeline events={[
                  { date:'Sep 28', durationS: 58 },
                  { date:'Sep 28', durationS: 34 },
                ]} />
              </div>
            </CardBody>
          </Card>

          {/* PPS Stats summary */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardHeader title="PPS Availability" />
              <CardBody>
                <div className="text-center py-2">
                  <div className="mono text-4xl" style={{ color:'var(--good-text)' }}>{ppsStats.availabilityPct}</div>
                  <div className="text-[10px] mono" style={{ color:'var(--t3)' }}>% — 30-day window</div>
                </div>
                <MetricRow label="Current streak" value={ppsStats.currentLockStreak} />
                <MetricRow label="Longest streak" value={ppsStats.longestLock} />
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Outage Statistics" />
              <CardBody>
                <MetricRow label="Events (30d)" value={ppsStats.lossEvents30d} />
                <MetricRow label="Total holdover" value={`${ppsStats.totalHoldoverH}h`} />
                <MetricRow label="Avg outage" value={`${ppsStats.avgOutageDurationS}s`} />
                <MetricRow label="Median outage" value={`${ppsStats.medianOutageDurationS}s`} />
                <MetricRow label="Longest outage" value={ppsStats.longestOutageDuration} />
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Recovery" />
              <CardBody>
                <MetricRow label="MTBF" value={ppsStats.mtbf} />
                <MetricRow label="Mean recovery" value={`${ppsStats.mttRecoveryS}s`} />
                <div className="mt-3">
                  <div className="text-[10px] mb-1" style={{ color:'var(--t3)' }}>Outage durations</div>
                  <OutageBarChart data={ppsOutages} />
                </div>
              </CardBody>
            </Card>
          </div>

          {/* Holdover performance */}
          <div className="grid grid-cols-2 gap-4">
            <Card>
              <CardHeader title="Holdover Performance" badge={<ProvenanceTag type="observed" />} />
              <CardBody>
                <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>Observed clock error upon PPS reacquisition vs. outage duration. Each point is a real event.</div>
                <HoldoverScatter data={ppsOutages} />
                <ELI5 text="After a GPS outage, when PPS returns we can see how far off the clock drifted. Longer outages should mean larger errors — this plot confirms or surprises that expectation." />
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Estimated Time-to-Error Thresholds" />
              <CardBody>
                <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>How long before the free-running or trained oscillator crosses each error threshold.</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr style={{ borderBottom:'1px solid var(--border)' }}>
                        <th className="text-left py-1.5 font-normal" style={{ color:'var(--t3)' }}>Threshold</th>
                        <th className="text-right py-1.5 font-normal" style={{ color:'var(--t3)' }}>Raw osc.</th>
                        <th className="text-right py-1.5 font-normal" style={{ color:'var(--t3)' }}>Trained</th>
                        <th className="text-right py-1.5 font-normal" style={{ color:'var(--t3)' }}>Region</th>
                      </tr>
                    </thead>
                    <tbody>
                      {thresholds.map(t => (
                        <tr key={t.label} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                          <td className="py-1.5 mono" style={{ color:'var(--t2)' }}>{t.label}</td>
                          <td className="py-1.5 mono text-right" style={{ color:'var(--warn-text)' }}>{t.tRaw < 1 ? `${(t.tRaw*60).toFixed(0)}m` : t.tRaw < 60 ? `${t.tRaw.toFixed(0)}h` : `${(t.tRaw/24).toFixed(0)}d`}</td>
                          <td className="py-1.5 mono text-right" style={{ color:'var(--live)' }}>{t.tTrained < 60 ? `${t.tTrained.toFixed(0)}h` : `${(t.tTrained/24).toFixed(0)}d`}</td>
                          <td className="py-1.5 text-right">
                            <span className={`px-1.5 py-0.5 rounded text-[9px] mono uppercase ${regionBg[t.region]}`} style={{ color: regionTextVar[t.region] }}>{regionLabel[t.region]}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      )}

      {tab === 'PPS Stats' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Card>
              <CardHeader title="PPS Loss Event Log" />
              <CardBody>
                <table className="w-full text-[11px]">
                  <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
                    <th className="text-left py-1.5 font-normal" style={{ color:'var(--t3)' }}>Date</th>
                    <th className="text-right py-1.5 font-normal" style={{ color:'var(--t3)' }}>Duration</th>
                    <th className="text-right py-1.5 font-normal" style={{ color:'var(--t3)' }}>Recovery error</th>
                  </tr></thead>
                  <tbody>
                    {ppsOutages.map((o,i) => (
                      <tr key={i} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                        <td className="py-1.5" style={{ color:'var(--t2)' }}>{o.date}</td>
                        <td className="py-1.5 text-right mono" style={{ color:'var(--warn-text)' }}>{o.duration}</td>
                        <td className="py-1.5 text-right mono" style={{ color:'var(--t2)' }}>{o.errorNsOnRecovery} ns</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Outage Duration Bar Chart" />
              <CardBody>
                <OutageBarChart data={ppsOutages} />
                <div className="mt-3 space-y-1">
                  <MetricRow label="Total holdover time" value={`${ppsStats.totalHoldoverH}h`} muted />
                  <MetricRow label="MTBF (PPS loss)" value={ppsStats.mtbf} muted />
                  <MetricRow label="Mean recovery time" value={`${ppsStats.mttRecoveryS}s`} muted />
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      )}

      {tab === 'Error Budget' && <ErrorBudget />}

      {tab === 'Light Distance' && (
        <Card>
          <CardHeader title="Timing Uncertainty — Light-Distance Equivalent" badge={<ProvenanceTag type="calculated" />} />
          <CardBody>
            <div className="text-[10px] mb-4 max-w-2xl" style={{ color:'var(--t3)' }}>
              A useful way to internalize timing uncertainty: how far does light travel in vacuum during this interval?
              This is an equivalent propagation distance, not a position accuracy claim.
            </div>
            <table className="w-full text-[12px]">
              <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
                <th className="text-left py-2 font-normal" style={{ color:'var(--t3)' }}>Time interval</th>
                <th className="text-right py-2 font-normal" style={{ color:'var(--t3)' }}>Distance</th>
                <th className="text-right py-2 font-normal" style={{ color:'var(--t3)' }}>Reference</th>
              </tr></thead>
              <tbody>
                {lightDistRows.map((r) => (
                  <tr key={r.dt} className={r.highlight ? 'bg-cyan-400/5' : ''} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                    <td className="py-2 mono" style={{ color: r.highlight ? 'var(--live)' : 'var(--t2)' }}>{r.dt}</td>
                    <td className="py-2 text-right mono" style={{ color: r.highlight ? 'var(--live-bright)' : 'var(--t2)' }}>{r.dist}</td>
                    <td className="py-2 text-right text-[11px]" style={{ color:'var(--t3)' }}>{r.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ELI5 text="Light travels at ~299,792 km per second in vacuum. If your clock is 12.3 nanoseconds off, that's equivalent to the time it takes light to travel 3.69 metres — useful for understanding just how precise GPS timing is." />
          </CardBody>
        </Card>
      )}
    </div>
  );
}
