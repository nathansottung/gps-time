// Radio → Web SDR: OpenWebRX+ behind the station's LAN gate, login optional (GET /api/websdr), its
// Start and Stop (admin actions websdr_start / websdr_stop: open to anyone on the LAN, no token),
// Sign out all browsers (websdr_signout_all, admin token, when the login is on), and the usage log: CPU, temperature and PPS
// jitter while it runs, against the minutes before it started. Logic: lib/websdr.ts.
import { useState } from 'react';
import { Card, CardHeader, CardBody, MaturityBadge, MetricRow, ProvenanceTag, StatusBadge } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll } from '../api/station';
import { ApiError } from '../api/client';
import type { AdminAction } from '../api/types';
import { compareRows, hfLine, loginLine, sessionLine, websdrOutcome, websdrState, websdrUrl, type Variant } from '../lib/websdr';
import { cycleLine, mhz, refreshLine, rows as airbandRows } from '../lib/airband';

const COLOR: Record<Variant, string> = { good: 'var(--good-text)', warn: 'var(--warn-text)', error: 'var(--err-text)', muted: 'var(--t3)' };
const btn = { border: '1px solid var(--border)', color: 'var(--t2)' };
const startConfirm = (pauses: string | null | undefined) => 'Start the web SDR? '
  + (pauses === null ? 'No other service uses its dongle. '
    : `${pauses ?? 'The service on its dongle'} stops while it runs, so the aircraft on that band pause. `)
  + 'It stops by itself after the session limit.';
const SIGNOUT_CONFIRM = 'Sign out every browser of the web SDR? Remembered browsers have to sign in again, '
  + 'and anyone listening now is disconnected. The password stays the same.';

export function WebSdrCard() {
  const { api } = useStation();
  const ws = usePoll(() => api.websdr(), 10_000, [api]);
  const auth = usePoll(() => api.auth(), 0, [api]);
  const canWrite = !!auth.data && (auth.data.authenticated || !auth.data.auth_required);
  const [confirming, setConfirming] = useState<null | 'start' | 'signout'>(null);
  const [busy, setBusy] = useState<AdminAction | null>(null);
  const [outcome, setOutcome] = useState<{ variant: Variant; text: string } | null>(null);
  const st = ws.data;
  const state = st ? websdrState(st) : null;
  const url = st ? websdrUrl(window.location.hostname, st.port) : null;
  const login = st ? loginLine(st) : null;
  const loginOn = st?.auth?.enabled === true;

  const run = async (a: AdminAction) => {
    setConfirming(null); setBusy(a); setOutcome(null);
    try { setOutcome(websdrOutcome(a, await api.admin(a), undefined, st?.pauses)); }
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
          A browser radio for the station's RTL-SDR, open to anyone on the LAN (never beyond it), with decoders (FT8, FT4, WSPR, APRS, packet, SSTV, CW,
          RTTY, fax) and band bookmarks. While it runs it has its dongle to itself: {st?.pauses === null ? 'no other service uses that dongle'
          : `${st?.pauses ?? 'the service on that dongle'} is stopped and starts again when the web SDR stops`}; the other decoders keep running.
        </div>
        {st && st.installed === false && st.node_host && (
          <div className="text-[11px]" style={{ color: 'var(--t2)' }}>
            The web SDR runs on the SDR node at <span className="mono">{st.node_host}</span>, so its load stays off this timing Pi.{' '}
            <a href={websdrUrl(st.node_host, 8073) ?? '#'} target="_blank" rel="noreferrer" className="underline">Open it ↗</a>
            {' '}or manage it on the node's own page (<a href={`http://${st.node_host.includes(':') ? `[${st.node_host}]` : st.node_host}/app/#radio`} target="_blank" rel="noreferrer" className="underline">Radio &amp; SDR ↗</a>).
          </div>
        )}
        {st && st.installed === false && !st.node_host && (
          <div className="text-[11px]" style={{ color: 'var(--t3)' }}>
            Not installed. It is optional: <span className="mono">sudo GTP_WEBSDR=1 bash install.sh</span> (docs/deploy/websdr.md),
            here or on an SDR node (docs/deploy/sdr-node.md).
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
              <div>
                <MetricRow label="Login" value={login} />
              </div>
              <div>
                <MetricRow label="HF profiles" value={hfLine(st.hf)} />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-1.5 mt-3">
              {state?.running && url
                ? <a href={url} target="_blank" rel="noreferrer" className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
                     style={{ border: '1px solid var(--accent)', color: 'var(--accent)', background: 'var(--accent-dim)' }}>
                    Open the web SDR ↗</a>
                : <span className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={{ border: '1px solid var(--border-dim)', color: 'var(--t3)' }}>
                    Open the web SDR (not running)</span>}
              <button onClick={() => { setConfirming('start'); setOutcome(null); }} disabled={busy !== null || !!state?.running || !st.installed}
                className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>{busy === 'websdr_start' ? 'Start…' : 'Start'}</button>
              <button onClick={() => run('websdr_stop')} disabled={busy !== null || !state?.running}
                className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>{busy === 'websdr_stop' ? 'Stop…' : 'Stop'}</button>
              {loginOn && (
                <button onClick={() => { setConfirming('signout'); setOutcome(null); }} disabled={!canWrite || busy !== null}
                  className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>
                  {busy === 'websdr_signout_all' ? 'Sign out all browsers…' : 'Sign out all browsers'}</button>
              )}
            </div>
            {confirming === 'signout' && (
              <div role="alertdialog" aria-label="Confirm: Sign out all browsers" className="mt-3 rounded-[2px] p-3"
                style={{ background: 'var(--warn-bg)', border: '1px solid var(--warn-border)' }}>
                <div className="text-[11px] mb-2" style={{ color: 'var(--t1)' }}>{SIGNOUT_CONFIRM}</div>
                <div className="flex gap-1.5">
                  <button onClick={() => run('websdr_signout_all')} className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
                    style={{ border: '1px solid var(--warn-border)', color: 'var(--warn-text)' }}>Confirm: Sign out all browsers</button>
                  <button onClick={() => setConfirming(null)} autoFocus className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Cancel</button>
                </div>
              </div>
            )}
            {confirming === 'start' && (
              <div role="alertdialog" aria-label="Confirm: Start web SDR" className="mt-3 rounded-[2px] p-3"
                style={{ background: 'var(--warn-bg)', border: '1px solid var(--warn-border)' }}>
                <div className="text-[11px] mb-2" style={{ color: 'var(--t1)' }}>{startConfirm(st?.pauses)}</div>
                <div className="flex gap-1.5">
                  <button onClick={() => run('websdr_start')} className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
                    style={{ border: '1px solid var(--warn-border)', color: 'var(--warn-text)' }}>Confirm: Start web SDR</button>
                  <button onClick={() => setConfirming(null)} autoFocus className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Cancel</button>
                </div>
              </div>
            )}
            {outcome && <div className="text-[10px] mono mt-2" role="status" style={{ color: COLOR[outcome.variant] }}>{outcome.text}</div>}
            <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>
              Anyone on the LAN can start and stop it; no admin token is needed.
              {loginOn && !canWrite && auth.data ? ' Sign out all browsers needs an admin sign-in (Administration → Admin sign-in).' : ''}
            </div>
            <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>
              {loginOn
                ? 'The web SDR asks for its own login (set on the station); "Remember this browser" keeps a signed cookie. A new password signs every browser out too.'
                : st.auth?.enabled === false ? 'No login: anyone on the LAN can listen. sudo GTP_WEBSDR_AUTH=1 bash install.sh turns it on.' : null}
              {' '}Its listening page is plain HTTP: use it on the LAN only. Below 24 MHz needs HF profiles (docs/deploy/websdr.md → HF).
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

/** Airband bookmarks for the web SDR: the built-ins and the FAA NASR set, with its cycle date. */
export function AirbandCard() {
  const { api } = useStation();
  const ab = usePoll(() => api.airband(), 30_000, [api]);
  const auth = usePoll(() => api.auth(), 0, [api]);
  const canWrite = !!auth.data && (auth.data.authenticated || !auth.data.auth_required);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ text: string; variant: Variant } | null>(null);
  const [open, setOpen] = useState(false);
  const st = ab.data;
  const refresh = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await api.admin('refresh_airband');
      setMsg(r.simulated ? { text: 'Refresh: demo, nothing fetched.', variant: 'muted' }
        : r.ok ? { text: 'Refresh started on the station; the result shows here in a minute or two.', variant: 'good' }
        : { text: `Refresh failed${r.detail ? ` (${r.detail})` : ''}.`, variant: 'error' });
    } catch (e) {
      const status = e instanceof ApiError ? e.status : null;
      setMsg({ text: `Refresh: ${status === null ? 'no answer' : 'refused'}. ${(e as Error).message}`, variant: status === null ? 'warn' : 'error' });
      if (status === 401) auth.refresh();
    } finally { setBusy(false); ab.refresh(); }
  };
  const line = st ? cycleLine(st) : null;
  const last = st ? refreshLine(st) : null;
  return (
    <Card pending={!st && !ab.error}>
      <CardHeader title="Airband bookmarks" />
      <CardBody>
        <ApiErrorNote error={ab.error} />
        <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>
          The web SDR's airband channels (AM): a few that are the same everywhere, and nearby ones from the FAA's 28-day NASR data,
          fetched only when you press Refresh now.
        </div>
        {line && <div className="text-[11px] mb-1" style={{ color: COLOR[line.variant] }}>{line.text}</div>}
        {last && <div className="text-[10px] mb-1" style={{ color: COLOR[last.variant] }}>{last.text}</div>}
        {st && <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>{st.refresh_note}</div>}
        <div className="flex flex-wrap gap-1.5">
          <button onClick={refresh} disabled={!canWrite || busy || !st?.refresh_allowed} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>
            {busy ? 'Refresh now…' : 'Refresh now'}</button>
          <button onClick={() => setOpen(!open)} aria-expanded={open} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>
            {open ? 'Hide channels' : 'Show channels'}</button>
        </div>
        {msg && <div className="text-[10px] mono mt-2" role="status" style={{ color: COLOR[msg.variant] }}>{msg.text}</div>}
        {!canWrite && auth.data && <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>Refresh needs an admin sign-in (Administration → Admin sign-in).</div>}
        {open && st && (
          <div className="table-scroll mt-2"><table className="w-full text-[11px]" aria-label="Airband channels">
            <thead><tr>
              {['MHz', 'Name', 'Use', 'km', 'From'].map((h, i) => (
                <th key={h} className={`py-1 pr-2 font-normal ${i === 0 || i === 3 ? 'text-right' : 'text-left'}`} style={{ color: 'var(--t3)', fontSize: 10 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {airbandRows(st).map(r => (
                <tr key={`${r.source}-${r.name}-${r.frequency_hz}`} className="row-sep">
                  <td className="py-1 pr-2 text-right mono tabular" style={{ color: 'var(--t1)' }}>{mhz(r.frequency_hz)}</td>
                  <td className="py-1 pr-2" style={{ color: 'var(--t1)' }}>{r.name}</td>
                  <td className="py-1 pr-2 mono" style={{ color: 'var(--t2)' }}>{r.use ?? '—'}</td>
                  <td className="py-1 pr-2 text-right mono tabular" style={{ color: 'var(--t2)' }}>{r.distance_km ?? '—'}</td>
                  <td className="py-1 mono text-[10px]" style={{ color: 'var(--t3)' }}>{r.source === 'nasr' ? `NASR ${st.nasr?.cycle}` : 'built-in'}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </CardBody>
    </Card>
  );
}
