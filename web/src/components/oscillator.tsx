import { useState } from 'react';
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts';
import { Card, CardHeader, CardBody, MetricRow, ProvenanceTag, RangeSelector, ELI5 } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll } from '../api/station';
import { fitLine, fmtBytes, fmtSlope, oscPoints, scatterPoints, spanDays } from '../lib/oscillator';
import { fmtUtc } from '../lib/format';

const TICK = { fontSize: 9, fontFamily: 'JetBrains Mono', fill: 'var(--t3)' } as const;
const GRID = 'rgba(255,255,255,0.05)';

function Tip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="chart-tip">
      {p.ts !== undefined && <div style={{ color:'var(--t3)', marginBottom:2 }}>{new Date(p.ts).toISOString().slice(0, 16).replace('T', ' ')} UTC</div>}
      {payload.map((x: any, i: number) => (
        <div key={i} style={{ color: x.color ?? 'var(--live)' }}>{x.name}: {typeof x.value === 'number' ? x.value.toFixed(3) : x.value}</div>
      ))}
    </div>
  );
}

// ─── Oscillator log (/api/oscillator) ────────────────────────────────────────
export function OscillatorPanel() {
  const { api } = useStation();
  const osc = usePoll(() => api.oscillator(), 120_000, [api]);
  const [sel, setSel] = useState('PPS only');
  const d = osc.data;
  const pts = oscPoints(d?.bins);
  const scatter = scatterPoints(pts, sel === 'PPS only');
  const line = fitLine(d?.fit, scatter);
  const span = spanDays(pts);
  const time = pts.map(p => ({ ts: p.ts, temp: p.temp, freq: p.freq }));
  const fmtT = (ts: number) => new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  return (
    <div className="space-y-4">
      <ApiErrorNote error={osc.error} />
      <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
        <Card>
          <CardHeader title="Frequency vs Temperature" badge={<ProvenanceTag type="observed" />}
            action={<RangeSelector ranges={['PPS only', 'All']} active={sel} onChange={setSel} />} />
          <CardBody>
            {scatter.length
              ? <ResponsiveContainer width="100%" height={220}>
                  <ScatterChart margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="2 4" stroke={GRID} />
                    <XAxis interval="preserveStartEnd" minTickGap={8} dataKey="x" type="number" domain={['auto', 'auto']} name="°C" tick={TICK} tickLine={false}
                           axisLine={{ stroke: 'var(--border)' }} tickFormatter={(v: number) => `${v.toFixed(0)}°`} />
                    <YAxis dataKey="y" type="number" domain={['auto', 'auto']} name="ppm" tick={TICK} tickLine={false}
                           axisLine={false} width={40} tickFormatter={(v: number) => v.toFixed(2)} />
                    <ZAxis range={[12, 12]} />
                    <Tooltip content={<Tip />} />
                    <Scatter name="bin" data={scatter} fill="var(--live)" fillOpacity={0.5} />
                    {line.length > 0 && <Scatter name="fit" data={line} line={{ stroke: 'var(--mod-text)', strokeWidth: 1.2 }} shape={() => null} />}
                  </ScatterChart>
                </ResponsiveContainer>
              : <div className="text-[10px] py-10 text-center" style={{ color:'var(--t4)' }}>{d?.reason ?? 'No bins yet.'}</div>}
            <div className="text-[9px] mt-1" style={{ color:'var(--t4)' }}>
              One point per 10-minute bin. Frequency is chrony's estimate of how fast the uncorrected clock runs (+ = fast).
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Temperature Coefficient" badge={<ProvenanceTag type="calculated" />} />
          <CardBody>
            <MetricRow label="Slope (straight-line fit)" value={fmtSlope(d?.fit.slope_ppm_per_c)} provenance="calculated" />
            <MetricRow label="Correlation r" value={d?.fit.r ?? null} />
            <MetricRow label="Bins used (PPS throughout)" value={d ? d.fit.bins_used : null} />
            <MetricRow label="Temperature span" value={d?.fit.temp_span_c != null ? `${d.fit.temp_span_c} °C` : null} />
            {d?.fit.reason && <div className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>No slope yet: {d.fit.reason}.</div>}
            <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>{d?.fit_note}</div>
            <div className="text-[10px] mt-1" style={{ color:'var(--t4)' }}>{d?.sensor}</div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="Temperature and Frequency over Time" badge={<ProvenanceTag type="observed" />} />
        <CardBody>
          {time.length > 1
            ? <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
                {(['temp', 'freq'] as const).map(k => (
                  <div key={k}>
                    <div className="text-[10px] mb-1" style={{ color:'var(--t3)' }}>{k === 'temp' ? 'SoC temperature (°C)' : 'chrony frequency (ppm)'}</div>
                    <ResponsiveContainer width="100%" height={150}>
                      <LineChart data={time} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false} />
                        <XAxis interval="preserveStartEnd" minTickGap={8} dataKey="ts" type="number" domain={['dataMin', 'dataMax']} tickFormatter={fmtT} tick={TICK} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
                        <YAxis domain={['auto', 'auto']} tick={TICK} tickLine={false} axisLine={false} width={40}
                               tickFormatter={(v: number) => k === 'temp' ? v.toFixed(0) : v.toFixed(2)} />
                        <Tooltip content={<Tip />} />
                        <Line type="monotone" dataKey={k} name={k === 'temp' ? '°C' : 'ppm'} stroke={k === 'temp' ? 'var(--warn-text)' : 'var(--live)'}
                              strokeWidth={1.2} dot={false} connectNulls={false} isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ))}
              </div>
            : <div className="text-[10px] py-6 text-center" style={{ color:'var(--t4)' }}>{d?.reason ?? 'Not loaded.'}</div>}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Log" badge={<ProvenanceTag type="observed" />} />
        <CardBody>
          <MetricRow label="Latest bin" value={d?.latest ? `${fmtUtc(d.latest.bin_start_utc)} · ${d.latest.temp_c.value?.toFixed(1) ?? '—'} °C · ${d.latest.freq_ppm.value?.toFixed(3) ?? '—'} ppm` : null} />
          <MetricRow label="Bins in memory" value={d ? `${d.bins.length}${span != null ? ` (${span.toFixed(1)} days)` : ''}` : null} />
          <MetricRow label="File on the SD card" value={d ? `${fmtBytes(d.storage.bytes)} of ${fmtBytes(d.storage.max_bytes)} cap` : null} />
          <MetricRow label="Bins waiting to be written" value={d ? d.storage.pending_bins : null} />
          <MetricRow label="Board (hash of the serial number)" value={d?.board.serial_sha256 ?? null} />
          {(d?.problems ?? []).map(p => <div key={p} className="text-[10px] mt-1" style={{ color:'var(--warn-text)' }}>{p}</div>)}
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>{d?.storage.note}. This is the data the trained oscillator profile will be fitted on.</div>
          <ELI5 text="A crystal oscillator runs a little faster or slower as it warms and cools. Logging how chrony's frequency estimate moves with temperature, while GPS keeps the clock right, shows how this board's clock would drift if GPS went away." />
        </CardBody>
      </Card>
    </div>
  );
}
