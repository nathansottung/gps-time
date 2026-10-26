import { useState } from 'react';
import { Card, CardHeader, CardBody, MetricRow, StatusBadge, ELI5, RangeSelector, Tabs, ProvenanceTag, LoadingNote, EmptyNote } from '../components/ui';
import { OffsetHistoryChart, PPSTimeline, HoldoverScatter, OutageBarChart, ScaleToggle } from '../components/charts';
import { offsetRows } from '../lib/offset';
import { Planned, ApiErrorNote } from '../components/planned';
import { StabilityPanel } from '../components/stability';
import { TimeScalesPanel } from '../components/timescales';
import { ReferencesPanel } from '../components/references';
import { HoldoverPanel, OscillatorPanel } from '../components/oscillator';
import { useStation, usePoll, isPending } from '../api/station';
import { allEvents } from '../api/view';
import type { StageStatus } from '../api/types';
import { ppsOutages, ppsStats, errorBudget } from '../api/previews';
import { fmtOffset, fmtSeconds, lightDistance, fmtDuration, fmtUtc } from '../lib/format';

const RANGES = ['1h','24h','7d'];
const RANGE_S: Record<string, number> = { '1h': 3600, '24h': 86400, '7d': 7 * 86400 };

// ─── Light distance table ─────────────────────────────────────────────────────
const lightDistRows: { dt: string; dist: string; note: string; highlight?: boolean }[] = [
  { dt:'1 s',    dist:'299,792 km', note:'~0.78 × Earth–Moon distance' },
  { dt:'1 ms',   dist:'299.8 km',   note:'Roughly Boston to New York' },
  { dt:'1 µs',   dist:'299.8 m',    note:'3 football fields' },
  { dt:'100 ns', dist:'30.0 m',     note:'10-story building' },
  { dt:'10 ns',  dist:'3.0 m',      note:'One step' },
  { dt:'1 ns',   dist:'0.30 m',     note:'Palm of hand' },
];

const STAGE_VARIANT: Record<StageStatus, 'good'|'warn'|'error'|'muted'|'info'> = {
  OK:'good', DEGRADED:'warn', FAILED:'error', UNKNOWN:'muted', NOT_OBSERVABLE:'muted', NOT_APPLICABLE:'muted', INFO:'info',
};

function statusVariant(code: string | undefined) {
  return !code || code === 'UNKNOWN' ? 'muted' : code === 'GPS_PPS' ? 'good' : code === 'UNSYNCHRONIZED' ? 'error' : 'warn';
}

// ─── Error Budget (planned) ───────────────────────────────────────────────────
function ErrorBudget() {
  return (
    <Planned title="Timing Error Budget" needs="calibration records for each stage of the signal chain">
    <Card>
      <CardHeader title="Timing Error Budget" badge={<ProvenanceTag type="modeled" />} />
      <CardBody>
        <div className="text-[10px] mb-3" style={{ color:'var(--t3)' }}>Signal chain from satellite reference to application. Corrections applied where calibrated.</div>
        <div className="space-y-0">
          {errorBudget.map((s, i) => (
            <div key={i} className="flex flex-col @md:flex-row @md:items-center gap-2 @md:gap-3 py-2" style={{ borderBottom:'1px solid var(--border)', ...(i===0?{borderTop:'1px solid var(--border)'}:{}) }}>
              <div className="flex items-center gap-2 @md:w-52 @md:flex-shrink-0">
                {i < errorBudget.length-1 && (
                  <svg width="8" height="16" viewBox="0 0 8 16"><line x1="4" y1="0" x2="4" y2="16" stroke="#2c3040" strokeWidth="1"/><polygon points="4,14 1,10 7,10" fill="#2c3040"/></svg>
                )}
                {i === errorBudget.length-1 && <span className="w-2"/>}
                <span className="text-[11px]" style={{ color:'var(--t2)' }}>{s.stage}</span>
              </div>
              <div className="flex-1 grid grid-cols-2 @lg:grid-cols-4 gap-3 text-[10px]">
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
    </Planned>
  );
}

// ─── Timing chain (GNSS → PPS → chrony), /api/timing-chain ──────────────────
function TimingChainPanel({ onNavigate }: { onNavigate?: (id: string) => void }) {
  const { chain } = useStation();
  const c = chain.data;
  return (
    <div className="space-y-4">
      <ApiErrorNote error={chain.error} />
      {c?.classification && (
        <Card>
          <CardHeader title="Classification" badge={<ProvenanceTag type="inferred" />} />
          <CardBody>
            <MetricRow label="Classification" value={c.classification.classification} provenance="inferred" />
            <MetricRow label="Confidence" value={c.classification.confidence} />
            <MetricRow label="Boundary" value={c.classification.boundary} />
            {c.classification.notes.map(n => <div key={n} className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>{n}</div>)}
          </CardBody>
        </Card>
      )}
      <Card>
        <CardHeader title="Stages — GNSS → PPS → chrony" badge={<ProvenanceTag type="calculated" />} />
        <CardBody className="p-0">
          <div className="table-scroll"><table className="w-full text-[11px]">
            <tbody>
              {(c?.stages ?? []).map(st => (
                <tr key={st.id} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                  <td className="px-4 py-2" style={{ color:'var(--t2)' }}>{st.label}</td>
                  <td className="px-4 py-2"><StatusBadge variant={STAGE_VARIANT[st.status] ?? 'muted'} label={st.status.replace(/_/g, ' ')} dot={false} className="text-[9px]" /></td>
                  <td className="px-4 py-2 text-[10px]" style={{ color:'var(--t3)' }}>{st.summary}</td>
                </tr>
              ))}
              {!c && <tr><td className="px-4 py-3 text-[10px]" style={{ color:'var(--t3)' }}>Timing chain not loaded.</td></tr>}
            </tbody>
          </table></div>
        </CardBody>
      </Card>
      <div className="text-[10px]" style={{ color:'var(--t3)' }}>
        Per-stage values, outage history and the COPY/DOWNLOAD diagnostic snapshot are on the{' '}
        <button onClick={() => onNavigate?.('pps')} className="underline" style={{ color:'var(--t2)' }}>PPS Diagnostics</button> page.
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function Timing({ onNavigate }: { onNavigate?: (id: string) => void }) {
  const [range, setRange] = useState('1h');
  const [tab, setTab] = useState('Overview');
  const { api, core, chain } = useStation();
  const hist = usePoll(() => api.history(), 30_000, [api]);
  const evid = usePoll(() => api.evidence(), 60_000, [api]);
  const rows = offsetRows(hist.data?.points, RANGE_S[range]);
  const [showMaxErr, setShowMaxErr] = useState(true);
  const status = chain.data?.status;
  const events = allEvents(chain.data?.events.open, chain.data?.events.recent);
  // The light-distance row uses chrony's error bound, not the remaining correction (GPS-007).
  const bound = core.data?.quality.max_error_bound_s;
  const cur = bound == null ? null : fmtSeconds(bound);
  const lightRows = cur
    ? [...lightDistRows, { dt:`≤ ${cur} (current bound)`, dist: lightDistance(bound) ?? '—', note:"chrony's error bound for this station, if the reference is right", highlight:true }]
    : lightDistRows;

  return (
    <div className="space-y-4 page-enter">
      <div className="flex items-baseline justify-between">
        <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Timing & Reliability</h1>
        <StatusBadge variant={statusVariant(status?.code)} label={status?.banner ?? 'UNKNOWN'} pulse={status?.code === 'GPS_PPS'} />
      </div>

      <Tabs tabs={['Overview','Stability','Oscillator','Time Scales','References','Timing Chain','PPS Events','Error Budget','Light Distance']} active={tab} onChange={setTab} />

      {tab === 'Overview' && (
        <div className="space-y-4">
          {/* Offset history */}
          <Card>
            <CardHeader
              title="Time Offset History"
              badge={<ProvenanceTag type="observed" />}
              action={<div className="flex flex-wrap items-center gap-2"><ScaleToggle chart="offset-history" /><RangeSelector ranges={RANGES} active={range} onChange={setRange} /></div>}
            />
            <CardBody>
              <ApiErrorNote error={hist.error} />
              {rows.length
                ? <OffsetHistoryChart rows={rows} range={range} showMaxErr={showMaxErr} />
                : isPending(hist) ? <LoadingNote what="the offset history" />
                : <EmptyNote>
                    {hist.error && !hist.data ? 'Not available: the station did not answer (see the error above).' : hist.data && !hist.data.available ? 'chrony tracking log not available (needs "log tracking" in chrony.conf)' : 'No samples in this range'}
                  </EmptyNote>}
              <div className="flex items-center justify-between gap-4 mt-1">
                <div className="flex gap-3 text-[9px] mono" style={{ color:'var(--t3)' }}>
                  <span style={{ color:'var(--live)' }}>— offset</span>
                  <span style={{ color:'var(--good-text)' }}>▮ ± offset SD</span>
                  {showMaxErr && <span>- - ± max error</span>}
                </div>
                <label className="flex items-center gap-1.5 text-[9px] mono" style={{ color:'var(--t3)' }}>
                  <input type="checkbox" checked={showMaxErr} onChange={e => setShowMaxErr(e.target.checked)} /> max-error bound
                </label>
              </div>
              <div className="text-[9px] mt-1" style={{ color:'var(--t3)' }}>
                From chrony's tracking log, one record per clock update: the offset chrony measured, ± its standard deviation of that offset (where chrony reported one; nothing is filled in), and ± chrony's maximum-error bound, which holds only if the reference is right. Log: a symmetric-log scale, linear within ±1 µs and one step per decade beyond; Lin: a linear scale.
                {hist.data && 'skipped_lines' in hist.data && hist.data.skipped_lines ? ` ${hist.data.note}` : ''}
              </div>
            </CardBody>
          </Card>

          {/* chrony's own tracking figures (parity 16); text exactly as chronyc reports it */}
          <Card>
            <CardHeader title="chrony tracking" badge={<ProvenanceTag type="observed" />} />
            <CardBody>
              <div className="grid grid-cols-1 @md:grid-cols-2 gap-x-8">
                <div>
                  <MetricRow label="Frequency" value={core.data?.quality.frequency ?? null} />
                  <MetricRow label="Residual frequency" value={core.data?.quality.residual_freq ?? null} />
                  <MetricRow label="Skew" value={core.data?.quality.skew ?? null} />
                </div>
                <div>
                  <MetricRow label="Update interval" value={core.data?.quality.update_interval ?? null} />
                  <MetricRow label="Last offset" value={fmtOffset(core.data?.quality.last_offset_s) ? `${fmtOffset(core.data?.quality.last_offset_s)!.value} ${fmtOffset(core.data?.quality.last_offset_s)!.unit}` : null} />
                  <MetricRow label="Reference time" value={core.data?.quality.ref_time ?? null} />
                </div>
              </div>
              <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>
                From <span className="mono">chronyc -n tracking</span>. Residual frequency is the difference between the frequency the reference indicates and the one chrony uses; skew is chrony's estimated error bound on that frequency. The PPS sample age is on PPS Diagnostics.
              </div>
            </CardBody>
          </Card>

          <Planned title="PPS State Availability (today)" needs="a per-day PPS state timeline from the event history">
            <Card>
              <CardHeader title="PPS State Availability (today)" />
              <CardBody>
                <PPSTimeline events={[{ date:'today', durationS: 58 }, { date:'today', durationS: 34 }]} />
              </CardBody>
            </Card>
          </Planned>

          {/* PPS Stats summary (planned) */}
          <Planned title="PPS Availability & Outage Statistics" needs="30-day event history rollups (the station keeps recent events only)">
          <div className="grid grid-cols-1 @2xl:grid-cols-2 @5xl:grid-cols-3 gap-4">
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
          </Planned>

          {/* Holdover performance (planned): needs the offset measured at PPS reacquisition */}
          <Planned title="Holdover Performance" needs="offset measured at PPS reacquisition">
            <Card>
              <CardHeader title="Holdover Performance" badge={<ProvenanceTag type="observed" />} action={<ScaleToggle chart="holdover" />} />
              <CardBody>
                <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>Observed clock error upon PPS reacquisition vs. outage duration.</div>
                <HoldoverScatter data={ppsOutages} />
                <ELI5 text="After a GPS outage, when PPS returns we can see how far off the clock drifted. Longer outages should mean larger errors — this plot confirms or surprises that expectation." />
              </CardBody>
            </Card>
          </Planned>

          {/* Time to each error in holdover (modeled; GPS-008) */}
          <HoldoverPanel />
        </div>
      )}

      {tab === 'Stability' && <StabilityPanel />}

      {tab === 'Oscillator' && <OscillatorPanel />}

      {tab === 'Time Scales' && <TimeScalesPanel />}

      {tab === 'References' && <ReferencesPanel />}

      {tab === 'Timing Chain' && <TimingChainPanel onNavigate={onNavigate} />}

      {tab === 'PPS Events' && (
        <div className="space-y-4">
          <Card>
            <CardHeader title="PPS Events (recent)" badge={<ProvenanceTag type="observed" />} />
            <CardBody className="p-0">
              <div className="table-scroll"><table className="w-full text-[11px]">
                <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
                  {['Start','Duration','Classification','Confidence','Boundary'].map(h => (
                    <th key={h} className="text-left px-4 py-1.5 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {events.map(e => (
                    <tr key={e.id} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                      <td className="px-4 py-1.5 mono" style={{ color:'var(--t2)' }}>{fmtUtc(e.start_utc)}{e.start_bound ? ' (or earlier)' : ''}</td>
                      <td className="px-4 py-1.5 mono" style={{ color:'var(--warn-text)' }}>{e.open ? 'OPEN · ' : ''}{fmtDuration(e.duration_s) ?? '—'}</td>
                      <td className="px-4 py-1.5"><span style={{ color:'var(--t2)' }}>{e.classification ?? 'UNKNOWN'}</span> <ProvenanceTag type={e.classification_provenance} /></td>
                      <td className="px-4 py-1.5 mono" style={{ color:'var(--t3)' }}>{e.confidence ?? '—'}</td>
                      <td className="px-4 py-1.5 text-[10px]" style={{ color:'var(--t3)' }}>{e.boundary ?? '—'}</td>
                    </tr>
                  ))}
                  {!events.length && <tr><td colSpan={5} className="px-4 py-3 text-[10px]" style={{ color:'var(--t3)' }}>
                    {chain.data ? 'No PPS events recorded.' : 'Timing chain not loaded.'}</td></tr>}
                </tbody>
              </table></div>
              <div className="px-4 py-2 text-[10px]" style={{ color:'var(--t3)' }}>
                Classifications are inferred from the evidence at the time. They name a boundary in the signal path, not a cause.
              </div>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Outage Evidence on the SD Card" badge={<ProvenanceTag type="observed" />} />
            <CardBody className="p-0">
              <ApiErrorNote error={evid.error} />
              <div className="table-scroll"><table className="w-full text-[11px]">
                <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
                  {['Outage start','Duration','Classification','Kept','Size',''].map(h => (
                    <th key={h} className="text-left px-4 py-1.5 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {(evid.data?.files ?? []).map(f => (
                    <tr key={f.id} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                      <td className="px-4 py-1.5 mono" style={{ color:'var(--t2)' }}>{fmtUtc(f.start_utc)}</td>
                      <td className="px-4 py-1.5 mono" style={{ color:'var(--t2)' }}>{fmtDuration(f.duration_s) ?? '—'}{f.phase === 'open' ? ' (open when written)' : ''}</td>
                      <td className="px-4 py-1.5" style={{ color:'var(--t3)' }}>{f.classification ?? 'UNKNOWN'}</td>
                      <td className="px-4 py-1.5 text-[10px]" style={{ color:'var(--t3)' }}>{f.timeline_points} timeline points, {f.tracking_lines} chrony lines</td>
                      <td className="px-4 py-1.5 mono" style={{ color:'var(--t3)' }}>{(f.bytes / 1024).toFixed(0)} kB</td>
                      <td className="px-4 py-1.5"><a href={`/api/evidence?id=${encodeURIComponent(f.id)}`} target="_blank" rel="noreferrer" className="underline text-[10px]" style={{ color:'var(--t2)' }}>JSON</a></td>
                    </tr>
                  ))}
                  {evid.data && !evid.data.files.length && <tr><td colSpan={6} className="px-4 py-3 text-[10px]" style={{ color:'var(--t3)' }}>No outage evidence kept.</td></tr>}
                </tbody>
              </table></div>
              <div className="px-4 py-2 text-[10px]" style={{ color:'var(--t3)' }}>
                {evid.data ? `${(evid.data.total_bytes / 1024).toFixed(0)} kB of ${(evid.data.max_bytes / 1048576).toFixed(0)} MB cap. ${evid.data.note} No position is stored.` : 'Not loaded.'}
              </div>
            </CardBody>
          </Card>
          <Planned title="Outage Duration & Recovery Statistics" needs="event history rollups and offset at reacquisition">
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
          </Planned>
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
            <div className="table-scroll"><table className="w-full text-[12px]">
              <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
                <th className="text-left py-2 font-normal" style={{ color:'var(--t3)' }}>Time interval</th>
                <th className="text-right py-2 font-normal" style={{ color:'var(--t3)' }}>Distance</th>
                <th className="text-right py-2 font-normal" style={{ color:'var(--t3)' }}>Reference</th>
              </tr></thead>
              <tbody>
                {lightRows.map((r) => (
                  <tr key={r.dt} style={{ borderBottom:'1px solid var(--border-dim)', background: r.highlight ? 'var(--live-dim)' : undefined }}>
                    <td className="py-2 mono" style={{ color: r.highlight ? 'var(--live)' : 'var(--t2)' }}>{r.dt}</td>
                    <td className="py-2 text-right mono" style={{ color: r.highlight ? 'var(--live-bright)' : 'var(--t2)' }}>{r.dist}</td>
                    <td className="py-2 text-right text-[11px]" style={{ color: r.highlight ? 'var(--t2)' : 'var(--t3)' }}>{r.note}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
            <ELI5 text="Light travels about 299,792 km per second in vacuum. A clock 10 nanoseconds off matches the time light takes to travel 3 metres — a way to picture how precise GPS timing is." />
          </CardBody>
        </Card>
      )}
    </div>
  );
}
