import { useRef, useState } from 'react';
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts';
import { Card, CardHeader, CardBody, MetricRow, ProvenanceTag, RangeSelector, ELI5, LoadingNote, EmptyNote } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll, isPending } from '../api/station';
import {
  BINDING_LABEL, exportFilename, fitLine, fmtBytes, fmtSlope, fmtTerm, HOLDOVER_LABEL, holdoverRows, importOutcome, MODEL_LABEL,
  oscPoints, profileCurve, scatterPoints, spanDays,
  dayTicks,
} from '../lib/oscillator';
import type { Oscillator, ProfileImportResult } from '../api/types';
import { ApiError } from '../api/client';
import { fmtSci } from '../lib/units';
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
  const prof = d?.profile;
  const curve = profileCurve(prof);
  const span = spanDays(pts);
  const time = pts.map(p => ({ ts: p.ts, temp: p.temp, freq: p.freq }));
  const days = time.length > 1 ? dayTicks(time[0].ts, time[time.length - 1].ts) : [];
  const fmtT = (ts: number) => new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  return (
    <div className="space-y-4">
      <ApiErrorNote error={osc.error} />
      <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
        <Card pending={isPending(osc)}>
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
                    {line.length > 0 && <Scatter name="straight line" data={line} line={{ stroke: 'var(--calc-text)', strokeWidth: 1, strokeDasharray: '4 3' }} shape={() => null} />}
                    {curve.length > 0 && <Scatter name="profile" data={curve} line={{ stroke: 'var(--mod-text)', strokeWidth: 1.4 }} shape={() => null} />}
                  </ScatterChart>
                </ResponsiveContainer>
              : <div className="text-[10px] py-10 text-center" style={{ color:'var(--t3)' }}>{d?.reason ?? 'No bins yet.'}</div>}
            <div className="text-[9px] mt-1" style={{ color:'var(--t3)' }}>
              One point per 10-minute bin. Frequency is chrony's estimate of how fast the uncorrected clock runs (+ = fast).
              {curve.length > 0 && <> <span style={{ color:'var(--mod-text)' }}>— profile</span> (at the end of its span), <span style={{ color:'var(--calc-text)' }}>- - straight line</span>.</>}
            </div>
          </CardBody>
        </Card>

        <Card pending={isPending(osc)}>
          <CardHeader title="Temperature Coefficient" badge={<ProvenanceTag type="calculated" />} />
          <CardBody>
            <MetricRow label="Slope (straight-line fit)" value={fmtSlope(d?.fit.slope_ppm_per_c)} provenance="calculated" />
            <MetricRow label="Correlation r" value={d?.fit.r ?? null} />
            <MetricRow label="Bins used (PPS throughout)" value={d ? d.fit.bins_used : null} />
            <MetricRow label="Temperature span" value={d?.fit.temp_span_c != null ? `${d.fit.temp_span_c} °C` : null} />
            {d?.fit.reason && <div className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>No slope yet: {d.fit.reason}.</div>}
            <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>{d?.fit_note}</div>
            <div className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>{d?.sensor}</div>
          </CardBody>
        </Card>
      </div>

      <Card pending={isPending(osc)}>
        <CardHeader title="Oscillator Profile (fit)" badge={<ProvenanceTag type="modeled" />} />
        <CardBody>
          {!prof ? (isPending(osc) ? <LoadingNote what="the oscillator profile" /> : <EmptyNote>Not available: the station did not answer (see the error above).</EmptyNote>)
            : prof.status !== 'fitted' ? <EmptyNote>No profile yet: {prof.reason}.</EmptyNote>
            : <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-x-8">
                <div>
                  <MetricRow label="Model" value={prof.model ? MODEL_LABEL[prof.model] : null} provenance="modeled" />
                  {prof.terms.map(t => { const f = fmtTerm(t); return <MetricRow key={t.name} label={f.label} value={f.text} /> })}
                  <MetricRow label="Reference temperature" value={prof.temp_ref_c != null ? `${prof.temp_ref_c.toFixed(1)} °C` : null} />
                </div>
                <div>
                  <MetricRow label="Residual RMS" value={prof.residual_rms_ppm != null ? `${fmtSci(prof.residual_rms_ppm * 1e-6, 2)} (${prof.residual_rms_ppm.toFixed(4)} ppm)` : null} provenance="calculated" />
                  <MetricRow label="R²" value={prof.r2} provenance="calculated" />
                  <MetricRow label="Bins used (PPS throughout)" value={`${prof.bins_used.toLocaleString()}${prof.outliers ? ` (${prof.outliers} outliers left out)` : ''}`} />
                  <MetricRow label="Covers" value={prof.covers ? `${prof.covers.temp_min_c.toFixed(1)}–${prof.covers.temp_max_c.toFixed(1)} °C, ${prof.covers.days.toFixed(1)} days` : null} />
                  <MetricRow label="Span" value={prof.covers ? `${fmtUtc(prof.covers.first_utc)} → ${fmtUtc(prof.covers.last_utc)}` : null} />
                  <MetricRow label="Models compared (BIC, lower is better)" value={prof.candidates.map(c => `${c.model} ${c.bic.toFixed(0)}`).join(' · ')} />
                </div>
              </div>}
          {prof && <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>{prof.note}</div>}
          <ELI5 text="The profile is a formula for how fast this board's clock would run at a given temperature, learned while GPS kept it right. Holdover estimates can later use it instead of assuming today's rate stays fixed. It only knows the temperatures and the days it has seen." />
        </CardBody>
      </Card>

      <HoldoverCard d={d} pending={isPending(osc)} />

      <ProfileFileCard d={d} pending={isPending(osc)} onImported={osc.refresh} />

      <Card pending={isPending(osc)}>
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
                        <XAxis dataKey="ts" type="number" domain={['dataMin', 'dataMax']} ticks={days} tickFormatter={fmtT} tick={TICK} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
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
            : isPending(osc) ? <LoadingNote what="the oscillator log" />
            : <EmptyNote>{d?.reason ?? 'Not available: the station did not answer (see the error above).'}</EmptyNote>}
        </CardBody>
      </Card>

      <Card pending={isPending(osc)}>
        <CardHeader title="Log" badge={<ProvenanceTag type="observed" />} />
        <CardBody>
          <MetricRow label="Latest bin" value={d?.latest ? `${fmtUtc(d.latest.bin_start_utc)} · ${d.latest.temp_c.value?.toFixed(1) ?? '—'} °C · ${d.latest.freq_ppm.value?.toFixed(3) ?? '—'} ppm` : null} />
          <MetricRow label="Bins in memory" value={d ? `${d.bins.length}${span != null ? ` (${span.toFixed(1)} days)` : ''}` : null} />
          <MetricRow label="File on the SD card" value={d ? `${fmtBytes(d.storage.bytes)} of ${fmtBytes(d.storage.max_bytes)} cap` : null} />
          <MetricRow label="Bins waiting to be written" value={d ? d.storage.pending_bins : null} />
          <MetricRow label="Board (hash of the serial number)" value={d?.board.serial_sha256 ?? null} />
          {(d?.problems ?? []).map(p => <div key={p} className="text-[10px] mt-1" style={{ color:'var(--warn-text)' }}>{p}</div>)}
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>{d?.storage.note}. The profile above is fitted on the whole file (up to 90 days); the charts show the last 7 days kept in memory.</div>
          <ELI5 text="A crystal oscillator runs a little faster or slower as it warms and cools. Logging how chrony's frequency estimate moves with temperature, while GPS keeps the clock right, shows how this board's clock would drift if GPS went away." />
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Holdover projections (GPS-008; modeled) ─────────────────────────────────
const HOLD_COLOR: Record<string, string> = { free_running: 'var(--warn-text)', trained_skew: 'var(--calc-text)', profile: 'var(--mod-text)' };

export function HoldoverCard({ d, pending }: { d: Oscillator | null | undefined; pending: boolean }) {
  const h = d?.holdover;
  const rows = holdoverRows(h);
  const prof = h?.projections.find(p => p.name === 'profile');
  return (
    <Card pending={pending}>
      <CardHeader title="Holdover Projection" badge={<ProvenanceTag type="modeled" />} />
      <CardBody>
        {!h ? (pending ? <LoadingNote what="the holdover projection" /> : <EmptyNote>Not available: the station did not answer (see the error above).</EmptyNote>)
          : <>
              <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>
                Time until the clock would be off by each amount if GPS and PPS went away now{h.sample_utc ? <> (from the sample at {fmtUtc(h.sample_utc)})</> : null}.
              </div>
              <div className="table-scroll"><table className="w-full text-[11px]">
                <thead>
                  <tr style={{ borderBottom:'1px solid var(--border)' }}>
                    <th className="text-left py-1.5 font-normal" style={{ color:'var(--t3)' }}>Error</th>
                    {h.projections.map(p => <th key={p.name} className="text-right py-1.5 font-normal pl-3" style={{ color:'var(--t3)' }}>{HOLDOVER_LABEL[p.name]}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.threshold} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                      <td className="py-1.5 mono whitespace-nowrap" style={{ color:'var(--t2)' }}>{r.threshold}</td>
                      {r.cells.map(c => <td key={c.name} className="py-1.5 pl-3 mono text-right tabular-nums whitespace-nowrap" style={{ color: c.text === '—' ? 'var(--t3)' : HOLD_COLOR[c.name] }}>{c.text}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <div className="mt-3 space-y-1">
                {h.projections.map(p => (
                  <div key={p.name} className="text-[10px]" style={{ color:'var(--t3)' }}>
                    <span style={{ color: HOLD_COLOR[p.name] }}>{HOLDOVER_LABEL[p.name]}</span>
                    {p.available
                      ? <>: {p.basis}{p.rate_ppm != null && <>. Rate {fmtSci(p.rate_ppm * 1e-6, 2)} ({p.rate_ppm.toFixed(4)} ppm)</>}{p.aging_ppm_per_day ? <>, aging {fmtSci(Math.abs(p.aging_ppm_per_day) * 1e-6, 2)} per day</> : null}.</>
                      : <>: not available, {p.reason}.</>}
                  </div>
                ))}
                {prof?.available && prof.temp_assumed_c && <div className="text-[10px]" style={{ color:'var(--t3)' }}>Temperatures assumed for the profile: {prof.temp_assumed_c[0].toFixed(1)}–{prof.temp_assumed_c[1].toFixed(1)} °C ({prof.temp_source}), as if the worst of them were reached at once.</div>}
                {prof?.caveat && <div className="text-[10px]" style={{ color:'var(--warn-text)' }}>Profile: {prof.caveat}.</div>}
              </div>
              <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>{h.note}</div>
            </>}
        <ELI5 text="If GPS disappeared, the clock would slowly drift. The first column is a clock nobody has trained. The second trusts chrony's learned rate. The third also allows for the temperature changing, using what this board has learned. They are estimates, not promises." />
      </CardBody>
    </Card>
  );
}

/** Timing → Overview: the same projection, polled on its own. */
export function HoldoverPanel() {
  const { api } = useStation();
  const osc = usePoll(() => api.oscillator(), 120_000, [api]);
  return <div className="space-y-4"><ApiErrorNote error={osc.error} /><HoldoverCard d={osc.data} pending={isPending(osc)} /></div>;
}

// ─── Profile file: export, import, board binding ─────────────────────────────
function ProfileFileCard({ d, pending, onImported }: { d: Oscillator | null | undefined; pending: boolean; onImported: () => void }) {
  const { api } = useStation();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const files = d?.profile_files;
  const btn = { border:'1px solid var(--border)', color:'var(--t2)' };

  const doExport = async () => {
    setBusy(true); setMsg(null);
    try {
      const doc = await api.oscillatorExport();
      const url = URL.createObjectURL(new Blob([JSON.stringify(doc)], { type: 'application/json' }));
      const a = document.createElement('a');
      a.href = url; a.download = exportFilename(doc); a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMsg({ ok: true, text: `Exported ${doc.fit_bins.rows.length.toLocaleString()} bins as ${exportFilename(doc)}.` });
    } catch (e) {
      setMsg({ ok: false, text: `Not exported: ${(e as Error).message}.` });
    } finally { setBusy(false); }
  };
  const doImport = async (file: File) => {
    setBusy(true); setMsg(null);
    try {
      let doc: unknown;
      try { doc = JSON.parse(await file.text()); }
      catch { setMsg({ ok: false, text: 'Not imported: the file is not JSON.' }); return; }
      const r: ProfileImportResult = await api.oscillatorImport(doc);
      setMsg(importOutcome(r));
      if (r.ok) onImported();
    } catch (e) {
      const auth = e instanceof ApiError && (e.status === 401 || e.status === 403);
      setMsg({ ok: false, text: `Not imported: ${(e as Error).message}${auth ? ' (enter the admin token under Administration → Admin access)' : ''}.` });
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
  };

  return (
    <Card pending={pending}>
      <CardHeader title="Profile File" badge={<ProvenanceTag type="modeled" />} />
      <CardBody>
        <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>
          One JSON file with the profile, the bins it was fitted on, and this board's serial hash, model, receiver and software version. No position.
          Export it before a reflash and import it afterwards. Only a file from this board (same serial hash) joins the fit; any other is kept for reference only. Importing needs the admin token.
        </div>
        <div className="flex flex-wrap gap-1.5 items-center mb-2">
          <button onClick={doExport} disabled={busy} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Export profile</button>
          <button onClick={() => input.current?.click()} disabled={busy} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Import profile…</button>
          <input ref={input} type="file" accept="application/json,.json" className="hidden" aria-label="Profile file to import"
                 onChange={e => { const f = e.target.files?.[0]; if (f) void doImport(f); }} />
        </div>
        {msg && <div className="text-[10px] mb-2" style={{ color: msg.ok ? 'var(--good-text)' : 'var(--warn-text)' }}>{msg.text}</div>}
        <MetricRow label="This board (hash of the serial number)" value={d ? d.board.serial_sha256 : null} />
        <MetricRow label="Imported file in use" value={!files ? null : files.imported
          ? `${files.imported.bins.toLocaleString()} bins, exported ${files.imported.exported_utc ? fmtUtc(files.imported.exported_utc) : 'UNKNOWN'} (${BINDING_LABEL[files.imported.binding]})` : 'none'} />
        <MetricRow label="Reference file" value={!files ? null : files.reference
          ? `${files.reference.board.model ?? 'unknown model'}, ${files.reference.bins.toLocaleString()} bins (${BINDING_LABEL[files.reference.binding]})` : 'none'} />
        {files?.reference && <>
          <div className="text-[10px] mt-1" style={{ color:'var(--warn-text)' }}>{files.reference.warning}</div>
          {files.reference.profile.status === 'fitted' && files.reference.profile.model &&
            <div className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>Its profile, refitted here for reference: {MODEL_LABEL[files.reference.profile.model]}; {files.reference.profile.terms.map(t => fmtTerm(t)).map(f => `${f.label.toLowerCase()} ${f.text}`).join('; ')}.</div>}
        </>}
      </CardBody>
    </Card>
  );
}
