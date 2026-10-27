// Administration: an SDR module's readiness and settings (under its row in Experimental modules),
// and the SDR receivers card (GET /api/sdr). Logic: lib/modules.ts, lib/sdr.ts.
import { useState } from 'react';
import { Card, CardHeader, CardBody, MaturityBadge, MetricRow, StatusBadge } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll } from '../api/station';
import type { ModuleRow, SettingResult } from '../api/types';
import { configText, parseConfig, readinessLines, schemaRows } from '../lib/modules';
import { dongleRow, feedRow, sdrSummary, unitRows } from '../lib/sdr';

const COLOR = { good: 'var(--good-text)', warn: 'var(--warn-text)', error: 'var(--err-text)', muted: 'var(--t3)' } as const;
const btn = { border: '1px solid var(--border)', color: 'var(--t2)' };

/** What the module needs that the station can observe; UNKNOWN where it can't. */
export function ModuleReadiness({ row }: { row: ModuleRow }) {
  const lines = readinessLines(row.readiness);
  if (!lines.length) return null;
  return (
    <div className="mb-2" aria-label={`Readiness of ${row.name}`}>
      <div className="text-[10px] mb-1" style={{ color: 'var(--t3)' }}>Before it runs (observed by the station)</div>
      {lines.map(l => (
        <div key={l.check} className="flex flex-wrap items-baseline gap-x-2 text-[10px] py-[2px]">
          <span className="mono" style={{ color: COLOR[l.variant], minWidth: 64 }}>{l.mark}</span>
          <span style={{ color: 'var(--t1)' }}>{l.check}</span>
          <span className="mono" style={{ color: 'var(--t3)' }}>{l.detail}</span>
        </div>
      ))}
    </div>
  );
}

/** The module's settings (module_config): JSON with the manifest's keys, checked before sending. */
export function ModuleSettings({ row, canWrite, busy, send }: {
  row: ModuleRow; canWrite: boolean; busy: boolean;
  send: (what: string, call: () => Promise<SettingResult>) => Promise<void>;
}) {
  const { api } = useStation();
  const saved = configText(row.config);
  const [text, setText] = useState<string | null>(null);   // null: showing what the station has
  const [problem, setProblem] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const shown = text ?? saved;
  const rows = schemaRows(row.config_schema);
  if (!rows.length) return null;
  const save = () => {
    const r = parseConfig(shown, row.config_schema);
    if (!r.ok) { setProblem(r.error); return; }
    setProblem(null);
    void send(`${row.name} settings`, () => api.setModuleConfig(row.name, r.value)).then(() => setText(null));
  };
  const clear = () => { setProblem(null); void send(`${row.name} settings cleared`, () => api.setModuleConfig(row.name, null)).then(() => setText(null)); };
  return (
    <div className="mb-2">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="text-[10px] mono px-2 py-[3px] rounded-[2px]" style={btn}>
        {open ? 'Hide settings' : 'Settings'} {saved === '{}' ? '(the manifest defaults)' : '(set by the owner)'}
      </button>
      {open && <div className="mt-2">
        <textarea value={shown} onChange={e => { setText(e.target.value); setProblem(null); }} spellCheck={false}
          aria-label={`Settings of ${row.name} (JSON)`} disabled={!canWrite} rows={Math.min(14, Math.max(3, shown.split('\n').length))}
          className="mono text-[11px] w-full px-2 py-1 rounded-[2px]"
          style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--t1)', resize: 'vertical' }} />
        {problem && <div className="text-[10px] mono mt-1" role="alert" style={{ color: 'var(--err-text)' }}>{problem}</div>}
        <div className="flex flex-wrap gap-1.5 mt-1.5">
          <button onClick={save} disabled={!canWrite || busy || text === null} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Save settings</button>
          <button onClick={() => { setText(null); setProblem(null); }} disabled={text === null} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Undo edits</button>
          <button onClick={clear} disabled={!canWrite || busy || saved === '{}'} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Back to defaults</button>
        </div>
        <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>
          Only these keys; no positions (a module gets the station's site, privacy-filtered). A change restarts the module set.
        </div>
        <div className="table-scroll"><table className="w-full text-[10px] mt-1">
          <thead><tr>
            {['Setting', 'Type', 'Default', 'What it is'].map(h => (
              <th key={h} className="py-1 pr-2 font-normal text-left" style={{ color: 'var(--t3)' }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.name} className="row-sep align-top">
                <td className="py-1 pr-2 mono" style={{ color: 'var(--t1)' }}>{r.name}</td>
                <td className="py-1 pr-2 mono" style={{ color: 'var(--t2)', whiteSpace: 'nowrap' }}>{r.type}</td>
                <td className="py-1 pr-2 mono" style={{ color: 'var(--t2)', overflowWrap: 'anywhere' }}>{r.dflt}</td>
                <td className="py-1" style={{ color: 'var(--t3)' }}>{r.description}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </div>}
    </div>
  );
}

/** The optional SDR stack, read only: receiver units, RTL-SDR dongles, decoder feeds. */
export function SdrReceivers() {
  const { api } = useStation();
  const sdr = usePoll(() => api.sdr(), 15_000, [api]);
  const st = sdr.data;
  const sum = st ? sdrSummary(st) : null;
  return (
    <Card>
      <CardHeader title="SDR receivers" badge={<MaturityBadge level="experimental" />} />
      <CardBody>
        <ApiErrorNote error={sdr.error} />
        <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>
          The receivers the SDR modules read, installed only with GTP_SDR=1. Read only: this page starts and stops none of them.
          Each listens on 127.0.0.1 only, or not at all.
        </div>
        {!st && !sdr.error && <div className="text-[11px]" style={{ color: 'var(--t3)' }}>…</div>}
        {st && sum && <div className="text-[11px] mb-2" style={{ color: COLOR[sum.variant] }}>{sum.text}</div>}
        {st && st.units && st.units.length > 0 && (
          <div className="table-scroll"><table className="w-full text-[11px]" aria-label="SDR units">
            <thead><tr>
              {['Unit', 'State', 'CPU (avg)', 'Memory', 'Restarts'].map((h, i) => (
                <th key={h} className={`py-1 pr-2 font-normal ${i >= 2 ? 'text-right' : 'text-left'}`} style={{ color: 'var(--t3)', fontSize: 10 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {unitRows(st).map(u => (
                <tr key={u.unit} className="row-sep align-top">
                  <td className="py-1.5 pr-2"><div className="mono" style={{ color: 'var(--t1)' }}>{u.unit}</div>
                    <div className="text-[10px]" style={{ color: 'var(--t3)' }}>{u.what}</div></td>
                  <td className="py-1.5 pr-2"><StatusBadge variant={u.state.variant} label={u.state.label} dot={false} className="text-[9px]" /></td>
                  <td className="py-1.5 pr-2 text-right mono tabular" style={{ color: 'var(--t2)', whiteSpace: 'nowrap' }}>{u.cpu ?? '—'}</td>
                  <td className="py-1.5 pr-2 text-right mono tabular" style={{ color: 'var(--t2)', whiteSpace: 'nowrap' }}>{u.memory ?? '—'}</td>
                  <td className="py-1.5 text-right mono tabular" style={{ color: 'var(--t2)' }}>{u.restarts ?? 'UNKNOWN'}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
        {st && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 mt-3">
            <div aria-label="RTL-SDR dongles">
              <div className="text-[10px] mb-1" style={{ color: 'var(--t3)' }}>RTL-SDR dongles on USB (observed)</div>
              {st.dongles === null && <div className="text-[11px]" style={{ color: 'var(--t3)' }}>UNKNOWN: USB devices could not be read</div>}
              {st.dongles && st.dongles.length === 0 && <div className="text-[11px]" style={{ color: 'var(--t3)' }}>None found</div>}
              {(st.dongles ?? []).map(d => {
                const r = dongleRow(d);
                return (
                  <div key={r.port} className="py-1 row-sep">
                    <MetricRow label={`${r.serial} · ${r.role}`} value={r.speed} unit="" provenance="observed" />
                    {r.problem && <div className="text-[10px]" style={{ color: 'var(--warn-text)' }}>{r.problem}</div>}
                  </div>
                );
              })}
            </div>
            <div aria-label="Decoder feeds">
              <div className="text-[10px] mb-1" style={{ color: 'var(--t3)' }}>Decoder feeds (aircraft.json in RAM; counts only, no positions)</div>
              {st.feeds.map(f => {
                const r = feedRow(f);
                return (
                  <div key={r.band} className="py-1 row-sep">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] mono tabular" style={{ color: 'var(--t2)' }}>{r.band}</span>
                      <StatusBadge variant={r.state.variant} label={r.state.label} dot={false} className="text-[9px]" />
                    </div>
                    <MetricRow label="Written" value={r.age} unit="" provenance="observed" />
                    <MetricRow label="Aircraft in the file" value={r.aircraft} unit="" provenance="observed" />
                  </div>
                );
              })}
            </div>
          </div>
        )}
        {st && <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>{st.note} CPU is the average since each unit started, in % of one core.</div>}
      </CardBody>
    </Card>
  );
}
