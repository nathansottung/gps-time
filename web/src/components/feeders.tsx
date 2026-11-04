// Administration → Feeders and Location sharing (GET /api/feeders, POST /api/setting {feeder}).
// Logic: lib/feeders.ts. Each feeder is off until turned on here with the admin token and its
// name typed exactly; PiAware MLAT, which shares the exact location, has its own confirmation.
import { useState } from 'react';
import { Card, CardHeader, CardBody, MaturityBadge, StatusBadge } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll } from '../api/station';
import { ApiError } from '../api/client';
import type { FeederRow, SettingResult } from '../api/types';
import { claimNote, confirmed, feederState, locationWarning, outcome, sharingSummary, type Variant } from '../lib/feeders';

const COLOR: Record<Variant, string> = { good: 'var(--good-text)', warn: 'var(--warn-text)', error: 'var(--err-text)', muted: 'var(--t3)' };
const btn = { border: '1px solid var(--border)', color: 'var(--t2)' };

function TypedConfirm({ label, want, busy, onConfirm, onCancel }: {
  label: string; want: string; busy: boolean; onConfirm: () => void; onCancel: () => void;
}) {
  const [typed, setTyped] = useState('');
  return (
    <div role="alertdialog" aria-label={label} className="mt-2 rounded-[2px] p-3" style={{ background: 'var(--warn-bg)', border: '1px solid var(--warn-border)' }}>
      <div className="text-[11px] mb-2" style={{ color: 'var(--t1)' }}>{label}</div>
      <label className="text-[10px] block mb-1" style={{ color: 'var(--t2)' }}>Type <span className="mono" style={{ color: 'var(--t1)' }}>{want}</span> to confirm</label>
      <input value={typed} onChange={e => setTyped(e.target.value)} autoFocus spellCheck={false} aria-label={`Type ${want} to confirm`}
        className="mono text-[11px] w-full px-2 py-1 rounded-[2px] mb-2" style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--t1)' }} />
      <div className="flex flex-wrap gap-1.5">
        <button onClick={onConfirm} disabled={busy || !confirmed(typed, want)} className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
          style={{ border: '1px solid var(--warn-border)', color: 'var(--warn-text)' }}>Confirm</button>
        <button onClick={onCancel} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Cancel</button>
      </div>
    </div>
  );
}

function FeederCard({ row, canWrite, busy, send }: {
  row: FeederRow; canWrite: boolean; busy: boolean; send: (what: string, call: () => Promise<SettingResult>) => Promise<void>;
}) {
  const { api } = useStation();
  const [asking, setAsking] = useState<'on' | 'mlat' | null>(null);
  const st = feederState(row);
  const warn = locationWarning(row);
  const claim = claimNote(row);
  return (
    <div className="py-2 row-sep" aria-label={`Feeder ${row.service}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[12px]" style={{ color: 'var(--t1)' }}>{row.service}{row.target && <span className="mono text-[10px] ml-2" style={{ color: 'var(--t3)' }}>{row.target}</span>}</span>
        <StatusBadge variant={st.variant} label={st.label} dot={false} className="text-[9px]" />
      </div>
      <div className="text-[11px] mt-1" style={{ color: COLOR[warn.variant] }}>{warn.text}</div>
      {claim && <div className="text-[11px] mt-0.5" style={{ color: 'var(--warn-text)' }}>{claim}</div>}
      <div className="text-[10px] mt-0.5" style={{ color: 'var(--t3)' }}>{row.shares}</div>
      <div className="flex flex-wrap gap-1.5 mt-2">
        {row.on
          ? <button onClick={() => send(`${row.service} off`, () => api.setFeeder(row.name, false))} disabled={!canWrite || busy}
              className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Turn off</button>
          : <button onClick={() => setAsking('on')} disabled={!canWrite || busy} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Turn on…</button>}
        {row.mlat && (row.mlat.on
          ? <button onClick={() => send('MLAT off', () => api.setFeederMlat(row.name, false))} disabled={!canWrite || busy}
              className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>MLAT off</button>
          : <button onClick={() => setAsking('mlat')} disabled={!canWrite || busy || !row.mlat.allowed}
              title={row.mlat.refused ?? undefined} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>MLAT on…</button>)}
      </div>
      {row.mlat?.refused && <div className="text-[10px] mt-1" style={{ color: 'var(--t3)' }}>{row.mlat.refused}.</div>}
      {asking === 'on' && (
        <TypedConfirm label={`Turn on ${row.service}? ${row.shares}`} want={row.confirm} busy={busy} onCancel={() => setAsking(null)}
          onConfirm={() => { setAsking(null); void send(`${row.service} on`, () => api.setFeeder(row.name, true, row.confirm)); }} />
      )}
      {asking === 'mlat' && row.mlat && (
        <TypedConfirm label={`Turn MLAT on? Shares your exact location with ${row.service}.`} want={row.mlat.confirm} busy={busy}
          onCancel={() => setAsking(null)}
          onConfirm={() => { setAsking(null); void send('MLAT on', () => api.setFeederMlat(row.name, true, row.mlat!.confirm)); }} />
      )}
    </div>
  );
}

export function FeedersCard({ canWrite, authKnown, onAuthError }: { canWrite: boolean; authKnown: boolean; onAuthError: () => void }) {
  const { api } = useStation();
  const st = usePoll(() => api.feeders(), 15_000, [api]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ text: string; variant: Variant } | null>(null);
  const send = async (what: string, call: () => Promise<SettingResult>) => {
    setBusy(true); setResult(null);
    try { setResult(outcome(what, await call())); }
    catch (e) {
      const status = e instanceof ApiError ? e.status : null;
      setResult(outcome(what, null, { message: (e as Error).message, status }));
      if (status === 401) onAuthError();
    } finally { setBusy(false); st.refresh(); }
  };
  const d = st.data;
  return (
    <>
      <Card pending={!d && !st.error}>
        <CardHeader title="Feeders" badge={<MaturityBadge level="experimental" />} />
        <CardBody>
          <ApiErrorNote error={st.error} />
          <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>
            Optional: the aircraft the station receives, sent to the services you choose. Each is off until turned on here,
            one by one, with its name typed out. No feeder is given the station's position; only MLAT shares it.
          </div>
          {d && !d.installed && <div className="text-[11px]" style={{ color: 'var(--t3)' }}>Not installed. It is optional: <span className="mono">sudo GTP_FEEDERS=1 bash install.sh</span> (docs/deploy/feeders.md).</div>}
          {d && d.feeders.map(r => <FeederCard key={r.name} row={r} canWrite={canWrite} busy={busy} send={send} />)}
          {result && <div className="text-[10px] mono mt-2" role="status" style={{ color: COLOR[result.variant] }}>{result.text}</div>}
          {!canWrite && authKnown && d?.installed && <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>Turning a feeder on or off needs the admin token (Admin access, above).</div>}
        </CardBody>
      </Card>
      <Card pending={!d && !st.error}>
        <CardHeader title="Location sharing" />
        <CardBody>
          <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>Everything that shares, or could share, where the station is, in one place.</div>
          {d && (() => { const s = sharingSummary(d); return <div className="text-[11px] mb-2" style={{ color: COLOR[s.variant] }}>{s.text}</div>; })()}
          {d && (
            <div className="table-scroll"><table className="w-full text-[11px]" aria-label="Location sharing">
              <thead><tr>
                {['What', 'To', 'Location', 'Now'].map(h => <th key={h} className="py-1 pr-2 font-normal text-left" style={{ color: 'var(--t3)', fontSize: 10 }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {d.sharing.rows.map(r => (
                  <tr key={r.what} className="row-sep align-top">
                    <td className="py-1 pr-2" style={{ color: 'var(--t1)' }}>{r.what}</td>
                    <td className="py-1 pr-2" style={{ color: 'var(--t2)', overflowWrap: 'anywhere' }}>{r.to}</td>
                    <td className="py-1 pr-2" style={{ color: r.location === 'exact' ? 'var(--warn-text)' : 'var(--t2)' }}>{r.location}</td>
                    <td className="py-1"><StatusBadge variant={r.active ? (r.location === 'exact' ? 'warn' : 'info') : 'muted'} label={r.active ? 'ACTIVE' : 'OFF'} dot={false} className="text-[9px]" /></td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </CardBody>
      </Card>
    </>
  );
}
