import { useState } from 'react';
import { Card, CardHeader, CardBody, MetricRow, ProvenanceTag, RangeSelector, ELI5 } from './ui';
import { StabilityChart } from './charts';
import { ApiErrorNote } from './planned';
import { useStation, usePoll } from '../api/station';
import {
  METRIC_LABEL, chartRows, fmtDeviation, fmtInterval, type StabilityMetric,
} from '../lib/stability';
import { fmtDuration, fmtUtc } from '../lib/format';

const METRICS: Record<string, StabilityMetric> = { ADEV: 'adev', MDEV: 'mdev', TDEV: 'tdev' };
const TH = { color:'var(--t3)', fontWeight:400, fontFamily:'JetBrains Mono', fontSize:10, letterSpacing:'0.05em',
             padding:'6px 16px', borderBottom:'1px solid var(--border)' } as const;

// ─── Stability analysis (/api/stability) ─────────────────────────────────────
export function StabilityPanel() {
  const { api } = useStation();
  const st = usePoll(() => api.stability(), 60_000, [api]);
  const [sel, setSel] = useState('ADEV');
  const metric = METRICS[sel];
  const s = st.data;
  const rows = chartRows(s?.points, metric);
  const sec = s?.series.seconds;
  const min = s?.series.minutes;
  const pct = (f: number | null | undefined) => f === null || f === undefined ? null : `${(f * 100).toFixed(0)}%`;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title={`Frequency Stability — ${METRIC_LABEL[metric]}`}
          badge={<ProvenanceTag type="calculated" />}
          action={<RangeSelector ranges={Object.keys(METRICS)} active={sel} onChange={setSel} />}
        />
        <CardBody>
          <ApiErrorNote error={st.error} />
          {rows.length
            ? <StabilityChart rows={rows} metric={metric} />
            : <div className="text-[10px] py-10 text-center" style={{ color:'var(--t4)' }}>
                {s ? (s.reason ?? 'No value at any averaging time yet for this statistic.') : 'Stability data not loaded.'}
              </div>}
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>
            {s?.measurement_layer ?? 'System clock against kernel PPS timestamps (the Linux/chrony view of PPS).'}
          </div>
          {metric === 'adev'
            ? <div className="text-[9px] mt-1" style={{ color:'var(--t4)' }}>
                Bars: {s ? `${(s.confidence.level * 100).toFixed(0)}%` : '68%'} confidence interval. {s?.confidence.method}
              </div>
            : <div className="text-[9px] mt-1" style={{ color:'var(--t4)' }}>No confidence interval is calculated for {sel}.</div>}
          {s?.notes.map(n => <div key={n} className="text-[9px] mt-1" style={{ color:'var(--warn-text)' }}>{n}</div>)}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Key Points" badge={<ProvenanceTag type="calculated" />} />
        <CardBody className="p-0">
          <div className="table-scroll"><table className="w-full text-[11px]">
            <thead><tr>
              {['τ', 'ADEV', 'Interval', 'MDEV', 'TDEV', 'Noise type', 'Terms'].map((h, i) => (
                <th key={h} style={{ ...TH, textAlign: i === 0 || i === 5 ? 'left' : 'right' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {(s?.key_points ?? []).map(k => (
                <tr key={k.label} className="row-sep">
                  <td className="px-4 py-2 mono tabular" style={{ color:'var(--t1)' }}>{k.label}</td>
                  {k.point ? <>
                    <td className="px-4 py-2 mono tabular text-right whitespace-nowrap" style={{ color:'var(--t2)' }}>{fmtDeviation(k.point.adev, 'adev')}</td>
                    <td className="px-4 py-2 mono tabular text-right whitespace-nowrap" style={{ color:'var(--t3)' }}>{fmtInterval(k.point) ?? 'UNKNOWN'}</td>
                    <td className="px-4 py-2 mono tabular text-right whitespace-nowrap" style={{ color:'var(--t2)' }}>{fmtDeviation(k.point.mdev, 'mdev') ?? 'UNKNOWN'}</td>
                    <td className="px-4 py-2 mono tabular text-right whitespace-nowrap" style={{ color:'var(--t2)' }}>{fmtDeviation(k.point.tdev_s, 'tdev') ?? 'UNKNOWN'}</td>
                    <td className="px-4 py-2" style={{ color:'var(--t3)' }}>
                      {k.point.noise ? <>{k.point.noise}{k.point.noise_assumed ? ' (assumed)' : ''} <ProvenanceTag type="inferred" /></> : 'UNKNOWN'}
                    </td>
                    <td className="px-4 py-2 mono tabular text-right whitespace-nowrap" style={{ color:'var(--t3)' }}>{k.point.adev_terms}</td>
                  </> : (
                    <td colSpan={6} className="px-4 py-2 text-[10px]" style={{ color:'var(--t4)' }}>UNKNOWN — {k.reason}</td>
                  )}
                </tr>
              ))}
              {!s && <tr><td colSpan={7} className="px-4 py-3 text-[10px]" style={{ color:'var(--t4)' }}>Stability data not loaded.</td></tr>}
            </tbody>
          </table></div>
          <div className="px-4 py-2 text-[10px]" style={{ color:'var(--t4)' }}>
            ADEV and MDEV are fractional frequency deviations (dimensionless). "Assumed" means too few points at that
            averaging time to identify the noise type; the type found at a shorter one was kept.
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Data Behind These Values" badge={<ProvenanceTag type="observed" />} />
        <CardBody>
          <MetricRow label="History since" value={fmtUtc(s?.since_utc)} />
          <MetricRow label="1 s samples" value={sec ? `${sec.samples} of the last ${fmtDuration(sec.span_s) ?? '0 s'}` : null} />
          <MetricRow label="Seconds without a sample" value={sec ? sec.gaps : null} />
          <MetricRow label="PPS selected by chrony (1 s series)" value={pct(sec?.pps_selected_fraction)} />
          <MetricRow label="Minute summaries" value={min ? `${min.samples} (${fmtDuration(min.span_s) ?? '0 s'})` : null} />
          <MetricRow label="Storage" value={s?.storage ?? null} />
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>{s?.method}</div>
          <ELI5 text="Allan deviation answers: if I compare the clock's rate over one stretch of time with its rate over the next stretch of the same length, how much do they typically differ? Short stretches are dominated by timestamp jitter; longer ones show how steadily the clock is being held." />
        </CardBody>
      </Card>
    </div>
  );
}
