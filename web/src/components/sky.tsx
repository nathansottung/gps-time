import { useState } from 'react';
import type { ObjectResult } from '../api/types';
import { useStation } from '../api/station';
import { Card, CardHeader, CardBody, ProvenanceTag, StatusBadge } from './ui';
import { isSky, objectRows, skyLayout } from '../lib/sky';

const SZ = 400, C = SZ / 2, R = 185;
const BTN = { border:'1px solid var(--border)', color:'var(--t2)' } as const;

/** Stars, constellation lines, Sun/Moon/planets and the looked-up target, at the chosen time. */
export function SkyMapCard({ sky, when, demo }: { sky: unknown; when: string | null; demo?: boolean }) {
  const ok = isSky(sky);
  const L = ok ? skyLayout(sky, C, C, R) : null;
  return (
    <Card>
      <CardHeader title="Sky map" badge={<ProvenanceTag type="predicted" />} />
      <CardBody>
        <div className="text-[10px] mb-2 mono" style={{ color:'var(--t3)' }}>{when ? `at ${when}` : ''}{demo ? ' · demo positions (shapes only)' : ''}</div>
        {!L ? <StatusBadge variant="muted" label="UNKNOWN" dot={false} /> : (
          <svg viewBox={`0 0 ${SZ} ${SZ}`} className="w-full max-w-[440px] mx-auto block" data-layout-ok="plot" role="img"
            aria-label={`Sky map: ${L.stars.length} stars, ${L.bodies.map(b => b.name).join(', ') || 'no bodies'} above the horizon${L.target === 'below' ? '; target below the horizon' : L.target ? '; target marked' : ''}`}>
            <circle cx={C} cy={C} r={R} fill="var(--sky-night)" stroke="var(--border-em)" />
            {[30, 60].map(alt => <circle key={alt} cx={C} cy={C} r={R * (1 - alt / 90)} fill="none" stroke="var(--border)" strokeDasharray="2 4" />)}
            {L.lines.map((pts, i) => <polyline key={i} points={pts} fill="none" stroke="var(--t3)" strokeOpacity={0.45} strokeWidth={0.7} />)}
            {L.stars.map((s, i) => <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="var(--t1)" fillOpacity={0.85} />)}
            {L.bodies.map(b => (
              <g key={b.name}>
                <circle cx={b.x} cy={b.y} r={b.r} fill={b.name === 'Sun' ? 'var(--sky-day)' : 'var(--t2)'} />
                <text x={b.x + 8} y={b.y + 3} fontSize="9.5" fill="var(--t2)" fontFamily="JetBrains Mono">{b.name}</text>
              </g>
            ))}
            {L.target && L.target !== 'below' && (
              <g stroke="var(--good-text)" strokeWidth={1.6} fill="none">
                <circle cx={L.target.x} cy={L.target.y} r={7} />
                <line x1={L.target.x - 11} y1={L.target.y} x2={L.target.x - 5} y2={L.target.y} />
                <line x1={L.target.x + 5} y1={L.target.y} x2={L.target.x + 11} y2={L.target.y} />
              </g>
            )}
            {L.target === 'below' && <text x={C} y={C} fontSize="11" fill="var(--t2)" textAnchor="middle" fontFamily="JetBrains Mono">target below the horizon</text>}
            {([['N', C, 11], ['S', C, SZ - 3], ['E', SZ - 6, C + 4], ['W', 6, C + 4]] as const).map(([l, x, y]) => (
              <text key={l} x={x} y={y} fontSize="11" fill="var(--t3)" textAnchor={l === 'E' ? 'end' : l === 'W' ? 'start' : 'middle'} fontFamily="JetBrains Mono">{l}</text>
            ))}
          </svg>
        )}
        <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>
          Map view: zenith at the centre, horizon at the edge, north up, east right (as the other sky plots here). Rings at 30° and 60° altitude.
        </div>
      </CardBody>
    </Card>
  );
}

/** Look up a Messier number, star, planet or J2000 coordinates; the result is marked on the sky map. */
export function ObjectLookupCard({ date, tz, at, onTarget }: { date: string; tz: string; at: string; onTarget: (q: string) => void }) {
  const { api } = useStation();
  const [q, setQ] = useState('');
  const [res, setRes] = useState<ObjectResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const look = async () => {
    const text = q.trim();
    if (!text) return;
    setBusy(true); setErr(null);
    try {
      const r = await api.object(text, { date, tz, at });
      setRes(r);
      onTarget('available' in r && r.available ? text : '');
    } catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };
  const clear = () => { setQ(''); setRes(null); setErr(null); onTarget(''); };
  return (
    <Card>
      <CardHeader title="Find an object" badge={<ProvenanceTag type="predicted" />} />
      <CardBody>
        <div className="flex gap-1.5">
          <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') look(); }}
            placeholder="M31, Vega, Jupiter, or 00h42m44s +41d16m09s" aria-label="Object to look up" spellCheck={false}
            className="flex-1 mono text-[11px] px-2 py-1 rounded-[2px]" style={{ background:'var(--bg)', border:'1px solid var(--border)', color:'var(--t1)' }} />
          <button onClick={look} disabled={busy || !q.trim()} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={BTN}>{busy ? 'Looking…' : 'Look up'}</button>
          {res && <button onClick={clear} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={BTN}>Clear</button>}
        </div>
        <div className="text-[9px] mt-1" style={{ color:'var(--t3)' }}>Coordinates are read as J2000. The lookup is for this page only; the station keeps no shared target.</div>
        {err && <div className="text-[10px] mono mt-2" style={{ color:'var(--err-text)' }}>{err}</div>}
        {res && 'error' in res && (
          <div className="text-[10px] mt-2" style={{ color:'var(--warn-text)' }}>
            Could not read that. Try <span className="mono">M31</span> · <span className="mono">Vega</span> · <span className="mono">Jupiter</span> · <span className="mono">00:42:44 +41:16:09</span> · <span className="mono">10.684 +41.269</span>
          </div>
        )}
        {res && 'available' in res && !res.available && <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>Unavailable: {res.reason}</div>}
        {res && 'available' in res && res.available && (
          <div className="mt-3">
            {objectRows(res, date, tz).map(([k, v, sub]) => (
              <div key={k} className="flex items-baseline justify-between gap-4 py-[5px] row-sep">
                <span className="text-[11px]" style={{ color:'var(--t2)' }}>{k}</span>
                <div className="text-right">
                  <div className="mono tabular text-[12px] font-medium" style={{ color:'var(--t1)' }}>{v}</div>
                  {sub && <div className="text-[9px]" style={{ color:'var(--t3)' }}>{sub}</div>}
                </div>
              </div>
            ))}
            {res.demo && <div className="text-[9px] mt-1" style={{ color:'var(--demo-text)' }}>Demo values.</div>}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
