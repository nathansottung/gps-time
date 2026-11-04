// Radio → Clips (GET /api/clips; POST /api/setting {clip} / {clip_delete}). Logic: lib/clips.ts.
import { useState } from 'react';
import { Card, CardHeader, CardBody, MaturityBadge } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll } from '../api/station';
import { ApiError } from '../api/client';
import type { ClipKind } from '../api/types';
import { checkRequest, lastLine, storageLine, timeLabel, type Variant } from '../lib/clips';

const COLOR: Record<Variant, string> = { good: 'var(--good-text)', warn: 'var(--warn-text)', error: 'var(--err-text)', muted: 'var(--t3)' };
const btn = { border: '1px solid var(--border)', color: 'var(--t2)' };
const field = { background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--t1)' };

export function ClipsCard() {
  const { api } = useStation();
  const cl = usePoll(() => api.clips(), 5_000, [api]);
  const auth = usePoll(() => api.auth(), 0, [api]);
  const canWrite = !!auth.data && (auth.data.authenticated || !auth.data.auth_required);
  const [kind, setKind] = useState<ClipKind>('am');
  const [mhz, setMhz] = useState('121.500');
  const [secs, setSecs] = useState('10');
  const [rate, setRate] = useState(1_024_000);
  const [msg, setMsg] = useState<{ text: string; variant: Variant } | null>(null);
  const st = cl.data;
  const check = st ? checkRequest(st, kind, mhz, secs, rate) : null;
  const act = async (what: string, call: () => Promise<unknown>) => {
    setMsg(null);
    try { await call(); setMsg({ text: `${what}: done.`, variant: 'good' }); }
    catch (e) {
      const status = e instanceof ApiError ? e.status : null;
      setMsg({ text: `${what}: ${status === null ? 'no answer' : 'refused'}. ${(e as Error).message}`, variant: status === null ? 'warn' : 'error' });
      if (status === 401) auth.refresh();
    } finally { cl.refresh(); }
  };
  const store = st ? storageLine(st) : null;
  const last = st ? lastLine(st) : null;
  return (
    <Card pending={!st && !cl.error}>
      <CardHeader title="Clips" badge={<MaturityBadge level="experimental" />} />
      <CardBody>
        <ApiErrorNote error={cl.error} />
        <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>
          Short recordings from the SDR stack's rtl_tcp dongle: audio (AM, NFM, wide FM) or raw IQ, as SigMF files with the station's timing,
          signed with its key. Kept in RAM or on a drive you named, never on the SD card.
        </div>
        {store && <div className="text-[11px] mb-1" style={{ color: COLOR[store.variant] }}>{store.text}</div>}
        {last && <div className="text-[10px] mb-2" role="status" style={{ color: COLOR[last.variant] }}>{last.text}</div>}
        {st && (
          <div className="flex flex-wrap items-end gap-2 mb-2">
            <label className="text-[10px]" style={{ color: 'var(--t3)' }}>Kind
              <select value={kind} onChange={e => setKind(e.target.value as ClipKind)} className="mono text-[11px] block px-2 py-1 rounded-[2px]" style={field}>
                {st.kinds.map(k => <option key={k} value={k}>{k === 'iq' ? 'IQ (raw)' : k.toUpperCase()}</option>)}
              </select></label>
            <label className="text-[10px]" style={{ color: 'var(--t3)' }}>MHz
              <input value={mhz} onChange={e => setMhz(e.target.value)} inputMode="decimal" className="mono text-[11px] block px-2 py-1 rounded-[2px] w-[110px]" style={field} /></label>
            <label className="text-[10px]" style={{ color: 'var(--t3)' }}>Seconds
              <input value={secs} onChange={e => setSecs(e.target.value)} inputMode="decimal" className="mono text-[11px] block px-2 py-1 rounded-[2px] w-[70px]" style={field} /></label>
            {kind === 'iq' && (
              <label className="text-[10px]" style={{ color: 'var(--t3)' }}>Rate
                <select value={rate} onChange={e => setRate(Number(e.target.value))} className="mono text-[11px] block px-2 py-1 rounded-[2px]" style={field}>
                  {st.iq_rates.map(r => <option key={r} value={r}>{(r / 1e6).toFixed(3)} MS/s</option>)}
                </select></label>
            )}
            <button onClick={() => check?.req && act('Record', () => api.recordClip(check.req!))} disabled={!canWrite || !check?.req || !!st.pending || !!st.storage.problem}
              className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Record</button>
          </div>
        )}
        {check?.problem && <div className="text-[10px] mb-2" style={{ color: 'var(--warn-text)' }}>{check.problem}</div>}
        {msg && <div className="text-[10px] mono mb-2" role="status" style={{ color: COLOR[msg.variant] }}>{msg.text}</div>}
        {!canWrite && auth.data && <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>Recording and deleting need an admin sign-in (Administration → Admin sign-in).</div>}
        {st && st.clips.length > 0 && (
          <div className="table-scroll"><table className="w-full text-[11px]" aria-label="Clips">
            <thead><tr>
              {['Start (UTC)', 'Kind', 'MHz', 's', 'Timing', 'Files', ''].map((h, i) => (
                <th key={i} className="py-1 pr-2 font-normal text-left" style={{ color: 'var(--t3)', fontSize: 10 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {st.clips.map(c => (
                <tr key={c.name} className="row-sep align-top">
                  <td className="py-1 pr-2 mono tabular" style={{ color: 'var(--t1)', whiteSpace: 'nowrap' }}>{(c.start_utc ?? 'UNKNOWN').replace('T', ' ').slice(0, 19)}</td>
                  <td className="py-1 pr-2 mono" style={{ color: 'var(--t2)' }}>{c.kind ?? '—'}</td>
                  <td className="py-1 pr-2 mono tabular" style={{ color: 'var(--t2)' }}>{c.freq_hz ? (c.freq_hz / 1e6).toFixed(4) : '—'}</td>
                  <td className="py-1 pr-2 mono tabular" style={{ color: 'var(--t2)' }}>{c.seconds ?? '—'}</td>
                  <td className="py-1 pr-2 text-[10px]" style={{ color: 'var(--t3)' }}>{timeLabel(c)}{c.signed ? '' : ' · unsigned'}</td>
                  <td className="py-1 pr-2 text-[10px]" style={{ whiteSpace: 'nowrap' }}>
                    {c.files.map(f => <a key={f} href={api.clipUrl(c.name, f)} className="underline mr-2" style={{ color: 'var(--t2)' }}>{f === 'wav' ? 'WAV' : f === 'sigmf-meta' ? 'meta' : 'data'}</a>)}
                  </td>
                  <td className="py-1"><button onClick={() => act('Delete', () => api.deleteClip(c.name))} disabled={!canWrite}
                    className="px-2 py-[3px] text-[10px] mono rounded-[2px]" style={btn}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </CardBody>
    </Card>
  );
}
