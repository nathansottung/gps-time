import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Survey } from '../api/types';
import { Card, CardHeader, CardBody, MetricRow, ProvenanceTag, StatusBadge } from './ui';
import { bullseye, convergenceSeries, fmtMetres, logDomain, rejectedRows } from '../lib/survey';

const GRID = 'rgba(255,255,255,0.05)';
const AXIS = 'rgba(255,255,255,0.08)';
const TICK = { fill:'var(--t3)', fontSize:9, fontFamily:'JetBrains Mono' };
const LOG_TICKS = [0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30, 100];

/** Standard error of the surveyed mean over time, log scale (legacy /history, parity 14). */
export function ConvergenceCard({ survey }: { survey: Survey | null }) {
  const pts = convergenceSeries(survey?.history);
  const dom = logDomain(pts);
  // Three ticks (start, middle, end): four full date-time labels collide at 360 px.
  const xTicks = pts.length > 1 ? [0, 1, 2].map(i => pts[0].t + (pts[pts.length - 1].t - pts[0].t) * i / 2) : [];
  const fmtT = (t: number) => new Date(t).toLocaleString('en-GB', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit', hour12:false });
  return (
    <Card>
      <CardHeader title="Survey convergence" badge={<ProvenanceTag type="calculated" />} />
      <CardBody>
        {!survey ? <StatusBadge variant="muted" label="UNKNOWN" dot={false} />
        : pts.length < 2 || !dom ? <div className="text-[11px]" style={{ color:'var(--t3)' }}>{survey.note ?? 'Not enough survey history yet.'}</div>
        : <>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={pts} margin={{ top:8, right:8, left:0, bottom:0 }}>
              <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false} />
              <XAxis dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']} ticks={xTicks} interval="preserveStartEnd" minTickGap={8} tickFormatter={fmtT} tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} />
              <YAxis scale="log" domain={dom} ticks={LOG_TICKS.filter(v => v >= dom[0] && v <= dom[1])} allowDataOverflow
                tickFormatter={(v: number) => fmtMetres(v) ?? ''} tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} width={46} />
              <Tooltip labelFormatter={(t) => fmtT(Number(t))} formatter={(v, name) => [fmtMetres(Number(v)) ?? '—', name === 'horiz' ? 'horizontal SE' : 'vertical SE']}
                contentStyle={{ background:'var(--card)', border:'1px solid var(--border)', fontSize:10 }} />
              <Line dataKey="horiz" stroke="var(--good-text)" strokeWidth={1.5} dot={false} connectNulls={false} isAnimationActive={false} />
              <Line dataKey="vert" stroke="var(--t3)" strokeWidth={1.2} strokeDasharray="4 3" dot={false} connectNulls={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
          <div className="flex gap-4 text-[9px] mono mt-1" style={{ color:'var(--t3)' }}>
            <span style={{ color:'var(--good-text)' }}>— horizontal</span><span>- - vertical</span>
          </div>
        </>}
        <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>
          Standard error of the mean, computed as if the fixes were independent. GNSS errors are correlated over minutes to hours, so the real uncertainty of the mean is larger, and below about 1 m it is set by systematic error, not by the number of fixes.
        </div>
      </CardBody>
    </Card>
  );
}

const SZ = 300;

/** This session's fixes around the surveyed mean (metres; no absolute position). */
export function ScatterCard({ survey }: { survey: Survey | null }) {
  const st = survey?.stats;
  const b = survey ? bullseye(survey.fixes, st ?? {}, SZ) : null;
  const c = SZ / 2;
  return (
    <Card>
      <CardHeader title="This session's fixes" badge={<ProvenanceTag type="observed" />} />
      <CardBody>
        {!b ? <StatusBadge variant="muted" label="UNKNOWN" dot={false} /> : <>
          <svg viewBox={`0 0 ${SZ} ${SZ}`} className="w-full max-w-[300px] mx-auto block" data-layout-ok="plot" role="img"
            aria-label={`${survey!.fixes.length} fixes around the mean; per-fix scatter ${fmtMetres(b.sd)}`}>
            {b.rings.map((r, i) => <circle key={i} cx={c} cy={c} r={r} fill="none" stroke="var(--border)" />)}
            <circle cx={c} cy={c} r={b.rings[0]} fill="none" stroke="var(--t3)" strokeDasharray="5 4" />
            {b.fixes.map((f, i) => <circle key={i} cx={f.x} cy={f.y} r={2} fill="var(--t1)" fillOpacity={f.opacity} />)}
            {b.seRing !== null && <circle cx={c} cy={c} r={b.seRing} fill="none" stroke="var(--good-text)" strokeWidth={2} />}
            <circle cx={c} cy={c} r={3} fill="var(--good-text)" />
            <text x={c} y={c - b.rings[0] - 5} fontSize="10" fill="var(--t3)" textAnchor="middle" fontFamily="JetBrains Mono">{fmtMetres(b.sd)} scatter</text>
            <text x={c} y={11} fontSize="10" fill="var(--t3)" textAnchor="middle" fontFamily="JetBrains Mono">N</text>
            <text x={SZ - 4} y={c + 4} fontSize="10" fill="var(--t3)" textAnchor="end" fontFamily="JetBrains Mono">E</text>
          </svg>
          <div className="text-[10px] mt-2 text-center mono" style={{ color:'var(--t3)' }}>{survey!.fixes.length} fixes this session</div>
        </>}
        <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>
          Dashed ring: per-fix scatter (1σ); grey rings 2σ and 3σ; green ring: standard error of the mean. Offsets from the mean only.
        </div>
      </CardBody>
    </Card>
  );
}

/** How the survey collector is doing this session (parity 15). */
export function IngestCard({ survey }: { survey: Survey | null }) {
  const ing = survey?.ingest;
  const rej = rejectedRows(ing?.rejected_this_session);
  return (
    <Card>
      <CardHeader title="Survey ingest" badge={<ProvenanceTag type="observed" />} />
      <CardBody>
        <MetricRow label="Collector" value={ing ? (ing.collector_running ? 'running' : 'NOT RUNNING') : null} />
        <MetricRow label="Accepted this session" value={ing ? ing.accepted_this_session.toLocaleString() : null} />
        <MetricRow label="Rejected this session" value={ing ? rej.reduce((n, [, k]) => n + k, 0).toLocaleString() : null} />
        {rej.map(([reason, n]) => (
          <div key={reason} className="flex justify-between text-[10px] pl-3 py-[2px]">
            <span className="mono" style={{ color:'var(--t3)' }}>{reason}</span>
            <span className="mono tabular" style={{ color:'var(--t2)' }}>{n.toLocaleString()}</span>
          </div>
        ))}
        <MetricRow label="Last rejection" value={ing ? (ing.last_reason ?? 'none') : null} />
        <MetricRow label="Accepted in total" value={survey ? survey.stats.n.toLocaleString() : null} />
        <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>
          Only fresh 3D fixes are accepted. Counters start again when the web service restarts.
        </div>
      </CardBody>
    </Card>
  );
}
