// Radio → Web SDR: OpenWebRX+ behind the station's password gate (GET /api/websdr), its Start and
// Stop (admin actions websdr_start / websdr_stop), and the usage log: CPU, temperature and PPS
// jitter while it runs, against the minutes before it started. Logic: lib/websdr.ts.
import { useState } from 'react';
import { Card, CardHeader, CardBody, MaturityBadge, MetricRow, ProvenanceTag, StatusBadge } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll } from '../api/station';
import { ApiError } from '../api/client';
import type { AdminAction } from '../api/types';
import { compareRows, sessionLine, websdrOutcome, websdrState, websdrUrl, type Variant } from '../lib/websdr';

const COLOR: Record<Variant, string> = { good: 'var(--good-text)', warn: 'var(--warn-text)', error: 'var(--err-text)', muted: 'var(--t3)' };
const btn = { border: '1px solid var(--border)', color: 'var(--t2)' };
const START_CONFIRM = 'Start the web SDR? readsb (1090 MHz ADS-B) stops while it runs, so the ADS-B references pause. '
  + 'It stops by itself after the session limit.';

export function WebSdrCard() {
  const { api } = useStation();
  const ws = usePoll(() => api.websdr(), 10_000, [api]);
  const auth = usePoll(() => api.auth(), 0, [api]);
  const canWrite = !!auth.data && (auth.data.authenticated || !auth.data.auth_required);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState<AdminAction | null>(null);
  const [outcome, setOutcome] = useState<{ variant: Variant; text: string } | null>(null);
  const st = ws.data;
  const state = st ? websdrState(st) : null;
  const url = st ? websdrUrl(window.location.hostname, st.port) : null;

  const run = async (a: AdminAction) => {
    setConfirming(false); setBusy(a); setOutcome(null);
    try { setOutcome(websdrOutcome(a, await api.admin(a))); }
    catch (e) {
      const status = e instanceof ApiError ? e.status : null;
      setOutcome(websdrOutcome(a, null, { message: (e as Error).message, status }));
      if (status === 401 || status === 403) auth.refresh();
    } finally { setBusy(null); ws.refresh(); }
  };

  const u = st?.usage;
  const live = u?.session ?? null;
  const last = u?.recent[0] ?? null;
  const shown = live ? { title: 'This session', before: live.before, during: live.during,
                         line: sessionLine(live.start_utc, null, live.during?.minutes ?? 0), partial: live.partial }
    : last ? { title: 'Last session', before: last.before, during: last.during,
               line: sessionLine(last.start_utc, last.duration_s, last.during?.minutes ?? 0), partial: last.partial }
    : null;

  return (
    <Card pending={!st && !ws.error}>
      <CardHeader title="Web SDR (OpenWebRX+)"
        badge={state ? <StatusBadge variant={state.variant} label={state.label} /> : undefined}
        action={<MaturityBadge level="experimental" />} />
      <CardBody>
        <ApiErrorNote error={ws.error} />
        <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>
          A browser radio for the station's RTL-SDR, on the LAN only and behind a password. While it runs it has the dongle to
          itself: readsb is stopped and starts again when the web SDR stops.
        </div>
        {st && st.installed === false && (
          <div className="text-[11px]" style={{ color: 'var(--t3)' }}>
            Not installed. It is optional: <span className="mono">sudo GTP_WEBSDR=1 bash install.sh</span> (docs/deploy/websdr.md).
          </div>
        )}
        {st && st.installed !== false && (
          <>
            <div className="grid grid-cols-1 @md:grid-cols-2 gap-x-6">
              <div>
                <MetricRow label="State" value={st.active.value} provenance="observed" />
                <MetricRow label="RTL-SDR serial" value={st.serial} />
              </div>
              <div>
                <MetricRow label="LAN port" value={st.port} />
                <MetricRow label="Session limit" value={st.max_hours === null ? null : `${st.max_hours} h`} />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-1.5 mt-3">
              {state?.running && url
                ? <a href={url} target="_blank" rel="noreferrer" className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
                     style={{ border: '1px solid var(--accent)', color: 'var(--accent)', background: 'var(--accent-dim)' }}>
                    Open the web SDR ↗</a>
                : <span className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={{ border: '1px solid var(--border-dim)', color: 'var(--t3)' }}>
                    Open the web SDR (not running)</span>}
              <button onClick={() => { setConfirming(true); setOutcome(null); }} disabled={!canWrite || busy !== null || !!state?.running || !st.installed}
                className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>{busy === 'websdr_start' ? 'Start…' : 'Start'}</button>
              <button onClick={() => run('websdr_stop')} disabled={!canWrite || busy !== null || !state?.running}
                className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>{busy === 'websdr_stop' ? 'Stop…' : 'Stop'}</button>
            </div>
            {confirming && (
              <div role="alertdialog" aria-label="Confirm: Start web SDR" className="mt-3 rounded-[2px] p-3"
                style={{ background: 'var(--warn-bg)', border: '1px solid var(--warn-border)' }}>
                <div className="text-[11px] mb-2" style={{ color: 'var(--t1)' }}>{START_CONFIRM}</div>
                <div className="flex gap-1.5">
                  <button onClick={() => run('websdr_start')} className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
                    style={{ border: '1px solid var(--warn-border)', color: 'var(--warn-text)' }}>Confirm: Start web SDR</button>
                  <button onClick={() => setConfirming(false)} autoFocus className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Cancel</button>
                </div>
              </div>
            )}
            {outcome && <div className="text-[10px] mono mt-2" role="status" style={{ color: COLOR[outcome.variant] }}>{outcome.text}</div>}
            {!canWrite && auth.data && (
              <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>Start and Stop need the admin token (Administration → Admin access).</div>
            )}
            <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>
              The web SDR asks for its own login (set on the station). Its listening page is plain HTTP: use it on the LAN only.
            </div>

            <div className="mt-4" aria-label="Web SDR usage">
              <div className="text-[10px] mb-1" style={{ color: 'var(--t3)' }}>
                Load and PPS jitter while the web SDR runs, against the minutes just before it started
              </div>
              {!shown && <div className="text-[11px]" style={{ color: 'var(--t3)' }}>No session recorded yet.</div>}
              {shown && (
                <>
                  <div className="text-[11px] mb-1 mono tabular" style={{ color: 'var(--t2)' }}>
                    {shown.title}: {shown.line}{shown.partial ? ' · started before the web service; the earlier part is not recorded' : ''}
                  </div>
                  <div className="table-scroll"><table className="w-full text-[11px]" aria-label="Before and during">
                    <thead><tr>
                      {['', 'Before', 'During', ''].map((h, i) => (
                        <th key={i} className={`py-1 pr-2 font-normal ${i === 1 || i === 2 ? 'text-right' : 'text-left'}`} style={{ color: 'var(--t3)', fontSize: 10 }}>{h}</th>
                      ))}
                    </tr></thead>
                    <tbody>
                      {compareRows(shown.before, shown.during).map(r => (
                        <tr key={r.label} className="row-sep">
                          <td className="py-1 pr-2" style={{ color: 'var(--t2)' }}>{r.label}</td>
                          <td className="py-1 pr-2 text-right mono tabular" style={{ color: 'var(--t2)', whiteSpace: 'nowrap' }}>{r.before ?? 'UNKNOWN'}</td>
                          <td className="py-1 pr-2 text-right mono tabular" style={{ color: 'var(--t1)', whiteSpace: 'nowrap' }}>{r.during ?? 'UNKNOWN'}</td>
                          <td className="py-1 text-right"><ProvenanceTag type={r.provenance} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table></div>
                </>
              )}
              {u && u.recent.length > 1 && (
                <div className="mt-2">
                  <div className="text-[10px] mb-1" style={{ color: 'var(--t3)' }}>Earlier sessions (PPS jitter, median minute: before → during)</div>
                  {u.recent.slice(live ? 0 : 1).map(s => (
                    <div key={s.start_utc} className="text-[10px] mono tabular py-[2px]" style={{ color: 'var(--t2)' }}>
                      {sessionLine(s.start_utc, s.duration_s, 0)} · {s.before?.pps_jitter_median_ns.value ?? 'UNKNOWN'} → {s.during?.pps_jitter_median_ns.value ?? 'UNKNOWN'} ns
                    </div>
                  ))}
                </div>
              )}
              {u && <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>
                {u.note} One summary per session is kept in {u.file.name}; the minutes are in RAM only.
                {u.file.error ? ` Last write failed: ${u.file.error}.` : ''}
              </div>}
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
