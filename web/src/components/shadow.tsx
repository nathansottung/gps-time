import { useState, type MouseEvent } from 'react';
import { Card, CardHeader, CardBody, MetricRow, ProvenanceTag, StatusBadge, ELI5 } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll } from '../api/station';
import type { SatelliteNow, SatellitePass, ShadowMap, ShadowReport } from '../api/types';
import {
  SHELL_PRESETS, STATE_FILL, STATE_OPACITY, compass, elementAge, fmtDeg, fmtDurationShort, fmtKm, mapSegments,
  nowLine, parseShell, segmentPath, skyXY, stateLabel, stateVariant, xyToSky,
} from '../lib/shadow';
import { fmtClock, fmtUtc, browserTimeZone } from '../lib/format';

const TZ = browserTimeZone();
const TH = { color:'var(--t3)', fontWeight:400, fontFamily:'JetBrains Mono', fontSize:10, letterSpacing:'0.05em',
             padding:'6px 16px', borderBottom:'1px solid var(--border)' } as const;
const LABEL = 'text-[9px] font-semibold uppercase tracking-[0.18em]';

function Unavailable({ reason }: { reason: string | null | undefined }) {
  return <div className="text-[11px]" style={{ color:'var(--t3)' }}>Not available: {reason ?? 'not loaded'}</div>;
}

// ─── Illumination sky map (SVG) ──────────────────────────────────────────────
function ShadowSkyMap({ map, sun, picked, onPick }: {
  map: ShadowMap; sun: ShadowReport['sun']; picked: { az: number; alt: number } | null;
  onPick: (p: { az: number; alt: number }) => void;
}) {
  const sz = 300, cx = sz / 2, cy = sz / 2, r = sz / 2 - 20;
  const click = (e: MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const p = xyToSky((e.clientX - box.left) * sz / box.width, (e.clientY - box.top) * sz / box.height, cx, cy, r);
    if (p) onPick(p);
  };
  const sunUp = sun.altitude_deg >= 0;
  const sunPos = skyXY(sun.azimuth_deg, Math.max(0, sun.altitude_deg), cx, cy, r);
  const pick = picked && skyXY(picked.az, picked.alt, cx, cy, r);
  return (
    <svg width={sz} height={sz} viewBox={`0 0 ${sz} ${sz}`} style={{ maxWidth:'100%', cursor:'crosshair' }} onClick={click}
         role="img" aria-label={`Sky map of sunlight and Earth shadow at ${map.shell_km} km`}>
      {mapSegments(map).map((s, i) => (
        <path key={i} d={segmentPath(s, cx, cy, r)} fill={STATE_FILL[s.code]} fillOpacity={STATE_OPACITY[s.code]} stroke="none" />
      ))}
      {[0, 30, 60].map(el => (
        <circle key={el} cx={cx} cy={cy} r={(1 - el / 90) * r} fill="none" stroke="rgba(255,255,255,0.10)" strokeWidth={el === 0 ? 1 : 0.5} />
      ))}
      {[0, 45, 90, 135].map(a => {
        const rad = (a - 90) * Math.PI / 180;
        return <line key={a} x1={cx - r * Math.cos(rad)} y1={cy - r * Math.sin(rad)} x2={cx + r * Math.cos(rad)} y2={cy + r * Math.sin(rad)}
                     stroke="rgba(255,255,255,0.06)" strokeWidth={0.5} />;
      })}
      {[{ l:'N', x:cx, y:12 }, { l:'E', x:sz - 8, y:cy + 3 }, { l:'S', x:cx, y:sz - 5 }, { l:'W', x:8, y:cy + 3 }].map(c => (
        <text key={c.l} x={c.x} y={c.y} textAnchor="middle" fontSize="9" fill="var(--t3)" fontFamily="JetBrains Mono">{c.l}</text>
      ))}
      <text x={cx + 3} y={cy - r / 3 + 3} fontSize="7" fill="var(--t3)" fontFamily="JetBrains Mono">60°</text>
      <text x={cx + 3} y={cy - r * 2 / 3 + 3} fontSize="7" fill="var(--t3)" fontFamily="JetBrains Mono">30°</text>
      {/* direction of the Sun: on the horizon circle when it is below the horizon */}
      <circle cx={sunPos.x} cy={sunPos.y} r={4} fill={sunUp ? 'var(--warn-text)' : 'none'} stroke="var(--warn-text)" strokeWidth={1.2} />
      <text x={sunPos.x} y={sunPos.y - 7} textAnchor="middle" fontSize="7" fill="var(--warn-text)" fontFamily="JetBrains Mono">
        {sunUp ? 'SUN' : 'SUN ↓'}
      </text>
      {pick && <>
        <circle cx={pick.x} cy={pick.y} r={5} fill="none" stroke="var(--t1)" strokeWidth={1} />
        <line x1={pick.x - 8} y1={pick.y} x2={pick.x + 8} y2={pick.y} stroke="var(--t1)" strokeWidth={0.6} />
        <line x1={pick.x} y1={pick.y - 8} x2={pick.x} y2={pick.y + 8} stroke="var(--t1)" strokeWidth={0.6} />
      </>}
    </svg>
  );
}

function Legend() {
  const item = (code: string, text: string) => (
    <span className="flex items-center gap-1 text-[9px] mono" style={{ color:'var(--t3)' }}>
      <span className="inline-block w-2.5 h-2.5 rounded-[2px]" style={{ background: STATE_FILL[code], opacity: Math.max(0.35, STATE_OPACITY[code]) }} />{text}
    </span>
  );
  return <div className="flex gap-4 mt-2">{item('S', 'SUNLIT')}{item('P', 'PENUMBRA')}{item('U', 'UMBRA (SHADOW)')}</div>;
}

// ─── Earth shadow (/api/shadow) ──────────────────────────────────────────────
export function ShadowPanel() {
  const { api } = useStation();
  const [shell, setShell] = useState(550);
  const [custom, setCustom] = useState('');
  const [picked, setPicked] = useState<{ az: number; alt: number } | null>(null);
  const sh = usePoll(() => api.shadow({ shell, az: picked?.az, alt: picked?.alt }), 30_000, [api, shell, picked?.az, picked?.alt]);
  const d = sh.data && sh.data.available ? sh.data : null;
  const reason = sh.data && !sh.data.available ? sh.data.reason : null;
  const by = (km: number) => d?.shells.find(s => s.altitude_km === km);
  const z = d?.zenith;
  const customKm = parseShell(custom);

  if (!d) {
    return <div className="space-y-2"><ApiErrorNote error={sh.error} /><Unavailable reason={reason} /></div>;
  }
  return (
    <div className="space-y-4">
      <ApiErrorNote error={sh.error} />
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader title="Satellite Shadow at Zenith" badge={<ProvenanceTag type="modeled" />} />
          <CardBody>
            <div className={LABEL} style={{ color:'var(--t3)' }}>550 km shell, straight up</div>
            <div className="mt-1 mb-3"><StatusBadge variant={stateVariant(by(550)?.zenith)} label={stateLabel(by(550)?.zenith)} dot={false} /></div>
            <div className={LABEL} style={{ color:'var(--t3)' }}>Earth shadow height at zenith</div>
            {z && z.ground_state === 'SUNLIT'
              ? <div className="text-[11px] mt-1" style={{ color:'var(--t2)' }}>No shadow overhead: the Sun is up.</div>
              : <>
                  <MetricRow label="Full shadow (umbra) up to" value={z?.beyond_limit && z.umbra_top_km === null ? `above ${fmtKm(z.search_limit_km)}` : fmtKm(z?.umbra_top_km)} provenance="modeled" />
                  <MetricRow label="Full sunlight above" value={z?.beyond_limit && z.penumbra_top_km === null ? `above ${fmtKm(z.search_limit_km)}` : fmtKm(z?.penumbra_top_km)} provenance="modeled" />
                </>}
            <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>{z?.note}</div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Satellite Contamination" badge={<ProvenanceTag type="modeled" />} />
          <CardBody>
            <MetricRow label="Sun altitude" value={fmtDeg(d.sun.altitude_deg)} provenance="calculated" />
            <MetricRow label="550 km zenith" value={stateLabel(by(550)?.zenith)} />
            <MetricRow label="550 km, sunlit sky above 10°" value={by(550) ? `${(by(550)!.sunlit_sky_fraction * 100).toFixed(0)}%${by(550)!.sunlit_sectors.length ? ' · ' + by(550)!.sunlit_sectors.join(', ') : ''}` : null} />
            <MetricRow label="1200 km, sunlit sky above 10°" value={by(1200) ? `${(by(1200)!.sunlit_sky_fraction * 100).toFixed(0)}%${by(1200)!.sunlit_sectors.length ? ' · ' + by(1200)!.sunlit_sectors.join(', ') : ''}` : null} />
            <MetricRow label="Astronomical darkness" value={d.darkness.astronomical_darkness ? 'YES' : `NO (${d.darkness.stage})`} provenance="calculated" />
            <div className="mt-2 space-y-1">
              {d.messages.map(m => <div key={m} className="text-[10px]" style={{ color:'var(--t2)' }}>{m}</div>)}
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title={`Illumination Sky Map — ${fmtKm(d.map.shell_km)} shell`} badge={<ProvenanceTag type="modeled" />}
          action={
            <div className="flex items-center gap-1">
              {SHELL_PRESETS.map(km => (
                <button key={km} onClick={() => setShell(km)} className="px-2 py-[3px] text-[9px] mono rounded-[2px]"
                  style={{ border:'1px solid var(--border)', color: shell === km ? 'var(--t1)' : 'var(--t3)', background: shell === km ? 'var(--float)' : 'transparent' }}>
                  {km} km
                </button>
              ))}
              <input value={custom} onChange={e => setCustom(e.target.value)} placeholder="custom km" aria-label="Custom shell height in km"
                onKeyDown={e => { if (e.key === 'Enter' && customKm) setShell(customKm); }}
                className="w-20 px-2 py-[3px] text-[9px] mono rounded-[2px]"
                style={{ border:'1px solid var(--border)', color:'var(--t1)', background:'var(--bg)' }} />
              <button onClick={() => customKm && setShell(customKm)} disabled={!customKm} className="px-2 py-[3px] text-[9px] mono rounded-[2px]"
                style={{ border:'1px solid var(--border)', color: customKm ? 'var(--t2)' : 'var(--t4)' }}>SET</button>
            </div>} />
        <CardBody>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <ShadowSkyMap map={d.map} sun={d.sun} picked={picked} onPick={setPicked} />
              <Legend />
              <div className="text-[9px] mt-1" style={{ color:'var(--t4)' }}>
                Zenith at the centre, horizon at the edge, north up. The penumbra is a thin band. Click the map to ask about one direction.
              </div>
              {custom !== '' && !customKm && <div className="text-[9px] mt-1" style={{ color:'var(--warn-text)' }}>Shell height must be 100 to 50,000 km.</div>}
            </div>
            <div>
              <div className={LABEL} style={{ color:'var(--t3)' }}>Would a satellite there be sunlit?</div>
              {d.query
                ? <div className="mt-2">
                    <div className="text-[11px]" style={{ color:'var(--t2)' }}>
                      At azimuth {fmtDeg(d.query.azimuth_deg)} ({compass(d.query.azimuth_deg)}), altitude {fmtDeg(d.query.altitude_deg)}, a satellite at {fmtKm(d.query.shell_km)} would be:
                    </div>
                    <div className="mt-2"><StatusBadge variant={stateVariant(d.query.state)} label={stateLabel(d.query.state)} dot={false} /></div>
                    <MetricRow label="Distance to that point" value={fmtKm(d.query.range_km)} provenance="modeled" />
                    {d.query.state === 'PENUMBRA' && <MetricRow label="Sunlit fraction (estimate)" value={`${(d.query.sunlit_fraction * 100).toFixed(0)}%`} />}
                  </div>
                : <div className="text-[10px] mt-2" style={{ color:'var(--t4)' }}>Click a point on the map.</div>}
              <div className="text-[10px] mt-3" style={{ color:'var(--t3)' }}>{d.meaning}</div>
            </div>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Orbital Shells" badge={<ProvenanceTag type="modeled" />} />
        <CardBody className="p-0">
          <table className="w-full text-[11px]">
            <thead><tr>
              {['Shell', 'At zenith', 'Sunlit sky above 10°', 'Sunlit up to', 'Where'].map((h, i) => (
                <th key={h} style={{ ...TH, textAlign: i === 2 || i === 3 ? 'right' : 'left' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {d.shells.map(s => (
                <tr key={s.altitude_km} className="row-sep">
                  <td className="px-4 py-2 mono tabular" style={{ color:'var(--t1)' }}>{fmtKm(s.altitude_km)}</td>
                  <td className="px-4 py-2"><StatusBadge variant={stateVariant(s.zenith)} label={stateLabel(s.zenith)} dot={false} className="text-[9px]" /></td>
                  <td className="px-4 py-2 mono tabular text-right" style={{ color:'var(--t2)' }}>{(s.sunlit_sky_fraction * 100).toFixed(0)}%</td>
                  <td className="px-4 py-2 mono tabular text-right" style={{ color:'var(--t2)' }}>{s.sunlit_max_altitude_deg === null ? 'nowhere' : fmtDeg(s.sunlit_max_altitude_deg, 0)}</td>
                  <td className="px-4 py-2 text-[10px]" style={{ color:'var(--t3)' }}>{s.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Shadow Geometry" badge={<ProvenanceTag type="modeled" />} />
        <CardBody>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <MetricRow label="Sun azimuth" value={`${fmtDeg(d.sun.azimuth_deg)} (${compass(d.sun.azimuth_deg)})`} />
              <MetricRow label="Sun altitude" value={fmtDeg(d.sun.altitude_deg)} />
              <MetricRow label="Solar depression below horizon" value={d.sun.altitude_deg < 0 ? fmtDeg(d.sun.depression_deg) : 'Sun is up'} />
              <MetricRow label="Anti-solar point" value={`${fmtDeg(d.sun.antisolar.azimuth_deg)} az, ${fmtDeg(d.sun.antisolar.altitude_deg)} alt`} />
            </div>
            <div>
              <MetricRow label="Umbra cone half-angle" value={fmtDeg(d.cone.umbra_half_angle_deg, 4)} />
              <MetricRow label="Penumbra cone half-angle" value={fmtDeg(d.cone.penumbra_half_angle_deg, 4)} />
              <MetricRow label="Umbra length behind the Earth" value={fmtKm(d.cone.umbra_length_km)} />
              <MetricRow label="Shadow axis" value={d.cone.axis} />
            </div>
          </div>
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>{d.model}</div>
          <div className="text-[9px] mt-1" style={{ color:'var(--t4)' }}>
            As of {fmtUtc(d.as_of_utc)}.{d.location_display === 'rounded' && ' Computed for the rounded site (~11 km), per the privacy setting.'}
          </div>
          <ELI5 text="After sunset the ground is in the Earth's shadow, but a satellite hundreds of kilometres up can still catch the Sun and leave a bright trail in a photo. As the night deepens the shadow climbs, low satellites go dark overhead first, and sunlit ones remain only low in the sky toward where the Sun set." />
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Satellites from cached orbital elements (/api/satellites) ───────────────
function PassRow({ p }: { p: SatellitePass }) {
  const t = (utc: string | undefined | null) => fmtClock(utc, TZ) ?? '—';
  return (
    <tr className="row-sep">
      <td className="px-4 py-2 mono tabular whitespace-nowrap" style={{ color:'var(--t1)' }}>
        {p.rise ? t(p.rise.utc) : 'under way'}<span style={{ color:'var(--t4)' }}> {p.rise ? compass(p.rise.azimuth_deg) : ''}</span>
      </td>
      <td className="px-4 py-2 mono tabular whitespace-nowrap" style={{ color:'var(--t2)' }}>
        {t(p.culmination.utc)} · {fmtDeg(p.culmination.altitude_deg, 0)} {compass(p.culmination.azimuth_deg)} · {fmtKm(p.culmination.range_km)}
      </td>
      <td className="px-4 py-2 mono tabular whitespace-nowrap" style={{ color:'var(--t2)' }}>
        {p.set ? t(p.set.utc) : 'still up'}<span style={{ color:'var(--t4)' }}> {p.set ? compass(p.set.azimuth_deg) : ''}</span>
      </td>
      <td className="px-4 py-2 text-[10px]" style={{ color:'var(--t3)' }}>
        {p.shadow_changes.length ? p.shadow_changes.map(c => `${c.kind} ${t(c.utc)}`).join(' · ') : `${stateLabel(p.culmination.state).toLowerCase()} throughout`}
      </td>
      <td className="px-4 py-2 text-[10px] whitespace-nowrap">
        {p.visible
          ? <span style={{ color:'var(--warn-text)' }}>{t(p.visible.start_utc)} to {t(p.visible.end_utc)} ({fmtDurationShort(p.visible.duration_s)}), up to {fmtDeg(p.visible.max_altitude_deg, 0)}</span>
          : <span style={{ color:'var(--t4)' }}>none</span>}
      </td>
    </tr>
  );
}

function NowCard({ s }: { s: SatelliteNow }) {
  const age = elementAge(s.age_days);
  return (
    <div className="px-3 py-2 rounded-[2px]" style={{ background:'var(--bg)', border:'1px solid var(--border-dim)' }}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[11px] font-medium" style={{ color:'var(--t1)' }}>{s.name ?? `NORAD ${s.norad}`}</span>
        <StatusBadge variant={age.variant} label={age.text} dot={false} className="text-[9px]" />
      </div>
      <div className="mono text-[11px] mt-1" style={{ color:'var(--t2)' }}>{nowLine(s)}</div>
      {s.available && (
        <div className="flex items-center gap-2 mt-1">
          <StatusBadge variant={stateVariant(s.state)} label={stateLabel(s.state)} dot={false} className="text-[9px]" />
          <span className="text-[10px] mono" style={{ color:'var(--t3)' }}>
            {s.height_km} km high{s.angular_speed_deg_s != null ? ` · ${s.angular_speed_deg_s.toFixed(2)}°/s` : ''}{s.could_be_seen ? ' · could be seen now' : ''}
          </span>
        </div>
      )}
      {s.age_note && <div className="text-[10px] mt-1" style={{ color:'var(--err-text)' }}>{s.age_note}</div>}
    </div>
  );
}

export function SatellitesPanel() {
  const { api } = useStation();
  const [sat, setSat] = useState<number | undefined>(undefined);
  const [text, setText] = useState('');
  const [q, setQ] = useState('');
  const rep = usePoll(() => api.satellites({ sat, q: q || undefined }), 30_000, [api, sat, q]);
  const data = rep.data;
  const d = data && 'cache' in data ? data : null;
  const hiddenReason = data && !('cache' in data) ? data.reason : null;
  const cache = d?.cache ?? null;
  const cacheAge = elementAge(cache?.newest_age_days, cache?.stale_after_days);

  if (!d) {
    return <div className="space-y-2"><ApiErrorNote error={rep.error} /><Unavailable reason={hiddenReason} /></div>;
  }
  return (
    <div className="space-y-4">
      <ApiErrorNote error={rep.error} />
      <Card>
        <CardHeader title="Orbital Elements (offline cache)" badge={<ProvenanceTag type="external" />}
          action={cache && cache.satellites > 0 ? <StatusBadge variant={cacheAge.variant} label={`NEWEST ${cacheAge.text}`} dot={false} /> : undefined} />
        <CardBody>
          {!d.available && <div className="text-[11px] mb-2" style={{ color:'var(--t2)' }}>{d.reason}</div>}
          <MetricRow label="Satellites in the cache" value={cache ? cache.satellites : null} />
          <MetricRow label="Newest elements" value={cache?.newest_epoch_utc ? fmtUtc(cache.newest_epoch_utc) : (cache ? 'none' : null)} provenance={cache?.newest_epoch_utc ? 'external' : undefined} />
          {(cache?.groups ?? []).map(g => (
            <MetricRow key={g.group} label={`${g.group} (${g.count} sets)`}
              value={`fetched ${g.fetched_utc ? fmtUtc(g.fetched_utc) : 'at an unknown time'} · ${g.source ?? 'source unknown'}`} />
          ))}
          {(cache?.problems ?? []).map(p => <div key={p} className="text-[10px] mt-1" style={{ color:'var(--warn-text)' }}>{p}</div>)}
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>
            Orbital elements come from outside the station and go out of date: for low orbits, predictions get poor after about {cache?.stale_after_days ?? 14} days.
            The station never downloads them on its own. Once they are in the cache, everything here is calculated offline.
          </div>
        </CardBody>
      </Card>

      {d.available && <>
        <Card>
          <CardHeader title="Now" badge={<ProvenanceTag type="modeled" />} />
          <CardBody>
            <div className="grid grid-cols-2 gap-3">
              {d.featured.map(s => <NowCard key={s.norad} s={s} />)}
              {d.satellite && !d.featured.some(f => f.norad === d.satellite!.norad) && <NowCard s={d.satellite} />}
            </div>
            {!d.featured.length && !d.satellite && <div className="text-[10px]" style={{ color:'var(--t4)' }}>Search for a satellite below.</div>}
            <div className="flex items-center gap-2 mt-3">
              <input value={text} onChange={e => setText(e.target.value)} placeholder="name or NORAD number" aria-label="Search the cached satellites"
                onKeyDown={e => { if (e.key === 'Enter') setQ(text.trim()); }}
                className="w-56 px-2 py-1 text-[11px] mono rounded-[2px]" style={{ border:'1px solid var(--border)', color:'var(--t1)', background:'var(--bg)' }} />
              <button onClick={() => setQ(text.trim())} className="px-2 py-1 text-[10px] mono rounded-[2px]" style={{ border:'1px solid var(--border)', color:'var(--t2)' }}>SEARCH</button>
              {[...d.featured, ...d.matches].filter((s, i, a) => a.findIndex(x => x.norad === s.norad) === i).map(s => (
                <button key={s.norad} onClick={() => setSat(s.norad)} className="px-2 py-1 text-[10px] mono rounded-[2px]"
                  style={{ border:'1px solid var(--border)', color: d.satellite?.norad === s.norad ? 'var(--t1)' : 'var(--t3)', background: d.satellite?.norad === s.norad ? 'var(--float)' : 'transparent' }}>
                  {s.name ?? s.norad}
                </button>
              ))}
            </div>
            {q && !d.matches.length && <div className="text-[10px] mt-1" style={{ color:'var(--t4)' }}>No cached satellite matches "{q}".</div>}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title={`Passes — ${d.satellite?.name ?? 'no satellite'} · next ${d.window_hours ?? 24} h`} badge={<ProvenanceTag type="predicted" />}
            action={d.satellite?.available !== undefined && d.satellite.age_days !== undefined
              ? <StatusBadge variant={elementAge(d.satellite.age_days).variant} label={elementAge(d.satellite.age_days).text} dot={false} /> : undefined} />
          <CardBody className="p-0">
            {d.satellite && !d.satellite.available && <div className="px-4 py-3 text-[11px]" style={{ color:'var(--t3)' }}>{d.satellite.reason}</div>}
            <table className="w-full text-[11px]">
              <thead><tr>
                {['Rise', 'Culmination', 'Set', 'Earth shadow', 'Could be seen'].map(h => <th key={h} style={{ ...TH, textAlign:'left' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {d.passes.map((p, i) => <PassRow key={i} p={p} />)}
                {!d.passes.length && <tr><td colSpan={5} className="px-4 py-3 text-[10px]" style={{ color:'var(--t4)' }}>No passes above the horizon in this window.</td></tr>}
              </tbody>
            </table>
            <div className="px-4 py-2 text-[10px]" style={{ color:'var(--t4)' }}>
              Times in {TZ}. {d.meaning}{d.location_display === 'rounded' && ' Computed for the rounded site (~11 km), per the privacy setting: times can be off by several seconds.'}
            </div>
          </CardBody>
        </Card>
      </>}
    </div>
  );
}
