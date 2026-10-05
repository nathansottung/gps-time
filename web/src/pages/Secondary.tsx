import { useState } from 'react';
import { Card, CardHeader, CardBody, MetricRow, StatusBadge, MaturityBadge, ELI5, ProvenanceTag } from '../components/ui';
import { SolarCurve } from '../components/charts';
import { Planned, ApiErrorNote } from '../components/planned';
import { useStation, usePoll, useBrowserClock } from '../api/station';
import { allEvents, ntpClientCount } from '../api/view';
import type { AuthState, LocationMode, LunarDay, SolarDay } from '../api/types';
import type { Polled } from '../api/station';
import { adsbStats, dataPacks, ntpRequestRatePerMin } from '../api/previews';
import { SunDays, MoonPhaseIcon } from './Overview';
import { browserTimeZone, fmtClock, fmtDuration, fmtUtc } from '../lib/format';
import { isValidZone, resolveZone, zoneNames } from '../lib/localtime';

const TZ = browserTimeZone();

// ─── Sun & Astronomy ──────────────────────────────────────────────────────────
export function SunAstronomy() {
  const [safetyAck, setSafetyAck] = useState(false);
  const { api, core } = useStation();
  const alm = usePoll(() => api.almanac({ tz: TZ }), 10 * 60_000, [api]);
  const a = alm.data && alm.data.available ? alm.data : null;
  const sun = a && a.sun.available ? a.sun as SolarDay : null;
  const moon = a && a.moon.available ? a.moon as LunarDay : null;
  const unavailable = alm.data && !alm.data.available ? alm.data.reason : null;

  const irradData = Array.from({ length: 24 }, (_, h) => ({
    h, w: Math.round(Math.max(0, 850 * Math.sin(Math.PI * (h - 6) / 13)) * (h>=6&&h<=19?1:0)),
  }));

  return (
    <div className="space-y-4 page-enter">
      <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Sun & Astronomy</h1>
      <ApiErrorNote error={alm.error} />
      {unavailable && <div className="text-[11px]" style={{ color:'var(--t3)' }}>Almanac unavailable: {unavailable}</div>}

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader title="Sun / Daylight — Yesterday / Today / Tomorrow" badge={<ProvenanceTag type="predicted" />} />
          <CardBody>
            <SunDays almanac={a} />
            <div className="text-[9px] mt-2" style={{ color:'var(--t4)' }}>
              Times in {TZ}.{a?.location_display === 'rounded' && ' Computed for the rounded site (~11 km), per the privacy setting.'}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Twilight (today)" badge={<ProvenanceTag type="predicted" />} />
          <CardBody>
            <MetricRow label="Astronomical dawn" value={fmtClock(sun?.events.astro_dawn, TZ)} />
            <MetricRow label="Civil dawn" value={fmtClock(sun?.events.civil_dawn, TZ)} />
            <MetricRow label="Civil dusk" value={fmtClock(sun?.events.civil_dusk, TZ)} />
            <MetricRow label="Astronomical dusk" value={fmtClock(sun?.events.astro_dusk, TZ)} />
            {sun?.notes.map(n => <div key={n} className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>{n}</div>)}
          </CardBody>
        </Card>
      </div>

      <Planned title="Solar Position & Solar-Equivalent Time" needs="solar position and equation-of-time in the almanac API">
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader title="Solar Position (Now)" badge={<ProvenanceTag type="calculated" />} />
          <CardBody>
            <MetricRow label="Elevation" value="38.4°" />
            <MetricRow label="Azimuth" value="187.2°" />
            <MetricRow label="Apparent solar time" value="12:33:14" />
            <MetricRow label="Equation of time" value="−9.8 min" provenance="calculated" />
            <MetricRow label="Solar declination" value="+0.5°" provenance="calculated" />
            <ELI5 text="The equation of time is the difference between apparent solar time and mean solar time — how far ahead or behind the Sun runs compared to a regular clock." />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Solar-Equivalent Time Calculator" badge={<ProvenanceTag type="calculated" />} />
          <CardBody>
            <div className="text-[11px] mb-3" style={{ color:'var(--t2)' }}>
              Find what civil time on a different date corresponds to the same point in the solar day as a given time today.
            </div>
            <div className="p-3 bg-cyan-400/5 border border-cyan-400/15 rounded-sm">
              <div className="text-[10px] mb-1" style={{ color:'var(--t3)' }}>Equivalent civil time on target date (same solar phase)</div>
              <div className="mono text-lg" style={{ color:'var(--live)' }}>08:14:33</div>
            </div>
          </CardBody>
        </Card>
      </div>
      </Planned>

      <div className="grid grid-cols-2 gap-4">
        <Planned title="Solar Irradiance (Modeled)" needs="a clear-sky irradiance model in the almanac">
        <Card>
          <CardHeader title="Solar Irradiance (Modeled)" badge={<ProvenanceTag type="modeled" />} />
          <CardBody>
            <div className="flex items-baseline gap-4 mb-3">
              <SciValueInline value="612" unit="W/m²" sub="current" />
              <SciValueInline value="5.4" unit="kWh/m²/day" sub="est. today" />
            </div>
            <SolarCurve data={irradData} />
            <div className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>Clear-sky model only — cloud cover not included.</div>
          </CardBody>
        </Card>
        </Planned>

        <Card>
          <CardHeader title="Moon" badge={<ProvenanceTag type="predicted" />} />
          <CardBody>
            <div className="flex items-start gap-4">
              {moon && <MoonPhaseIcon illumPct={moon.illum} waxing={/wax/i.test(moon.phase)} />}
              <div className="flex-1">
                <MetricRow label="Phase" value={moon?.phase ?? null} />
                <MetricRow label="Illumination" value={moon ? `${moon.illum.toFixed(0)}%` : null} />
                <MetricRow label="Age" value={moon?.age_days ?? null} unit="days" />
                <MetricRow label="Moonrise" value={fmtClock(moon?.rise, TZ, false)} />
                <MetricRow label="Lunar transit" value={fmtClock(moon?.transit, TZ, false)} />
                <MetricRow label="Moonset" value={fmtClock(moon?.set, TZ, false)} />
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader title="Sidereal Time" badge={<ProvenanceTag type="calculated" />} />
          <CardBody>
            <MetricRow label="Local Sidereal Time" value={core.data?.sidereal ?? null} />
            <div className="mt-2 text-[10px]" style={{ color:'var(--t3)' }}>
              From the station position; updates with each status poll. Unavailable when the astronomy layer or a position is missing.
            </div>
          </CardBody>
        </Card>
        <Planned title="Transit & Alignment Predictions" needs="satellite pass and transit predictions">
        <Card>
          <CardHeader title="Transit & Alignment Predictions" badge={<MaturityBadge level="experimental" />} />
          <CardBody>
            <div className="space-y-2">
              {[
                { event:'ISS transit (Sun)', time:'16:32:41', dur:'0.8s', note:'Requires safe solar equipment' },
                { event:'ISS transit (Moon)', time:'Tomorrow 02:14', dur:'1.2s', note:'Naked-eye feasible' },
              ].map(e => (
                <div key={e.event} className="p-2 rounded-sm text-[11px]" style={{ background:'var(--bg)', border:'1px solid var(--border)' }}>
                  <div className="flex justify-between"><span style={{ color:'var(--t2)' }}>{e.event}</span><span className="mono" style={{ color:'var(--live)' }}>{e.time}</span></div>
                  <div className="text-[10px]" style={{ color:'var(--t3)' }}>Duration: {e.dur} · {e.note}</div>
                </div>
              ))}
            </div>
            {!safetyAck ? (
              <div className="mt-3 p-2 bg-amber-400/8 border border-amber-400/20 rounded-sm">
                <div className="text-[10px] text-amber-400/80 mb-2">Solar transit predictions are disabled until you acknowledge safe observing requirements.</div>
                <button onClick={() => setSafetyAck(true)}
                  className="px-3 py-1 text-[10px] mono bg-amber-400/15 text-amber-400 border border-amber-400/30 rounded hover:bg-amber-400/25 transition-colors">
                  I understand the hazard and am responsible for safe equipment
                </button>
              </div>
            ) : (
              <div className="mt-2 text-[10px] text-green-400/60">Solar transit predictions enabled. You are responsible for safe equipment.</div>
            )}
          </CardBody>
        </Card>
        </Planned>
      </div>
    </div>
  );
}

function SciValueInline({ value, unit, sub }: { value: string; unit: string; sub: string }) {
  return (
    <div>
      <div className="flex items-baseline gap-1">
        <span className="mono text-xl" style={{ color:'var(--warn-text)' }}>{value}</span>
        <span className="text-[11px]" style={{ color:'var(--t3)' }}>{unit}</span>
      </div>
      <div className="text-[10px]" style={{ color:'var(--t3)' }}>{sub}</div>
    </div>
  );
}

// ─── Network & Devices ────────────────────────────────────────────────────────
export function Network() {
  const { core, chain, isDemo } = useStation();
  const clk = useBrowserClock();
  const q = core.data?.quality;
  const clients = core.data?.clients ?? [];
  const status = chain.data?.status;
  const fmtMs = (v: number | null) => (v === null ? null : `${v.toFixed(1)} ms`);
  return (
    <div className="space-y-4 page-enter">
      <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Network & Devices</h1>
      <ApiErrorNote error={core.error} />

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader title="NTP Server (chrony)" />
          <CardBody>
            <MetricRow label="Timing status" value={status?.headline ?? null} provenance="calculated" />
            <MetricRow label="Stratum" value={q?.stratum ?? null} />
            <MetricRow label="Reference" value={q?.reference ?? null} />
            <MetricRow label="Leap status" value={q?.leap ?? null} />
            <MetricRow label="Clients seen" value={ntpClientCount(core.data, chain.data)} provenance="observed" />
            {/* planned: needs chronyc serverstats parsing */}
            <MetricRow label="Request rate" value={isDemo ? `${ntpRequestRatePerMin} req/min` : null} muted={!isDemo} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Browser Connection Test" badge={<ProvenanceTag type="observed" />} />
          <CardBody>
            <ApiErrorNote error={clk.error} />
            <MetricRow label="RTT (current)" value={fmtMs(clk.last?.rttMs ?? null)} />
            <MetricRow label="RTT (minimum)" value={fmtMs(clk.minRttMs)} />
            <MetricRow label="RTT (median)" value={fmtMs(clk.medianRttMs)} />
            <MetricRow label="RTT (p95)" value={fmtMs(clk.p95RttMs)} />
            <MetricRow label="Jitter (RTT std. dev.)" value={fmtMs(clk.jitterMs)} provenance="calculated" />
            <MetricRow label="Est. browser Δt" value={clk.offsetMs === null ? null : `${(-clk.offsetMs).toFixed(1)} ms`} provenance="inferred" />
            <div className="text-[9px] mono mt-1" style={{ color:'var(--t4)' }}>{clk.samples.length} samples · positive = browser ahead of station</div>
            <ELI5 text="Using a four-timestamp exchange (like NTP), the browser's clock offset can be estimated. Accuracy is limited by asymmetric network paths and browser timer resolution." />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Offline Status" />
          <CardBody>
            <MetricRow label="Internet" value={null} />
            <MetricRow label="Local timing" value={status?.headline ?? null} />
            <MetricRow label="GNSS fix" value={core.data ? (core.data.gps.stale ? 'STALE' : core.data.gps.fix) : null} />
            <div className="mt-3 text-[10px]" style={{ color:'var(--t4)' }}>
              The station does not probe Internet connectivity, so it is shown as UNKNOWN. Timing does not depend on it.
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="NTP Clients" badge={<ProvenanceTag type="observed" />} />
        <CardBody className="p-0">
          <div className="px-4 py-2 text-[10px]" style={{ borderBottom:'1px solid var(--border-dim)', color:'var(--t3)' }}>
            From chronyc clients. Polling this server does not prove the client clock is accurate.
          </div>
          <table className="w-full text-[11px]">
            <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
              {['Host','NTP packets','Dropped','Last request'].map(h=>(
                <th key={h} className="text-left px-4 py-2 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {clients.map(c => (
                <tr key={c.host} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}>{c.host}</td>
                  <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>{c.ntp_packets.toLocaleString()}</td>
                  <td className="px-4 py-2 mono tabular" style={{ color:'var(--t3)' }}>{c.dropped}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{/^\d+$/.test(c.last) ? `${fmtDuration(Number(c.last))} ago` : c.last}</td>
                </tr>
              ))}
              {!clients.length && <tr><td colSpan={4} className="px-4 py-3 text-[10px]" style={{ color:'var(--t4)' }}>
                {!core.data ? 'Not loaded.' : ntpClientCount(core.data, chain.data) === null ? 'chronyc not available: client list UNKNOWN.' : 'No NTP clients reported.'}</td></tr>}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="chrony Sources" badge={<ProvenanceTag type="observed" />} />
        <CardBody className="p-0">
          <table className="w-full text-[11px]">
            <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
              {['Name','State','Stratum','Poll','Reach','Last rx','Last sample'].map(h=>(
                <th key={h} className="text-left px-4 py-2 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {(core.data?.sources ?? []).map(s => (
                <tr key={s.name} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}>{s.name}</td>
                  <td className="px-4 py-2 mono" style={{ color: s.state === '*' ? 'var(--good-text)' : 'var(--t3)' }}>{s.state} {s.state_label}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{s.stratum}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{2 ** s.poll} s</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{s.reach}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{s.lastrx}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}>{s.sample}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Aviation (planned) ───────────────────────────────────────────────────────
export function Aviation() {
  return (
    <div className="space-y-4 page-enter">
      <div className="flex items-baseline justify-between">
        <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Aviation — ADS-B / Mode-S</h1>
        <MaturityBadge level="planned" />
      </div>

      <Planned title="ADS-B / UAT" needs="dump1090 / dump978 integration">
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader title="1090 MHz ADS-B" badge={<StatusBadge variant="good" label="ACTIVE" />} />
          <CardBody>
            <MetricRow label="Messages/sec" value={adsbStats.msgsPerSec} />
            <MetricRow label="Aircraft in view" value={adsbStats.aircraftCount} />
            <MetricRow label="Max range" value={`${adsbStats.maxRangeKm} km`} provenance="observed" />
            <MetricRow label="MLAT status" value="ACTIVE" />
            <MetricRow label="MLAT peers" value={adsbStats.mlatPeers} />
            <MetricRow label="MLAT-derived positions" value={adsbStats.mlatPositions} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="978 MHz UAT" badge={<StatusBadge variant="good" label="ACTIVE" />} />
          <CardBody>
            <MetricRow label="Messages/sec" value="8" />
            <MetricRow label="Aircraft (UAT)" value="3" />
            <MetricRow label="Uplink messages" value="14" />
            <MetricRow label="FIS-B data" value="YES" />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Position Source" />
          <CardBody>
            <div className="space-y-2 text-[11px]">
              {[
                { label:'ADS-B Direct', color:'var(--live)', note:'Position broadcast by aircraft' },
                { label:'MLAT-derived', color:'var(--warn-text)', note:'Multi-lateration with peers' },
              ].map(s => (
                <div key={s.label} className="p-2 rounded-sm" style={{ background:'var(--bg)', border:'1px solid var(--border)' }}>
                  <div className="mono" style={{ color: s.color }}>{s.label}</div>
                  <div className="text-[10px]" style={{ color:'var(--t3)' }}>{s.note}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 text-[10px]" style={{ color:'var(--t3)' }}>Local station does not depend on any external proprietary service for position.</div>
          </CardBody>
        </Card>
      </div>
      </Planned>
    </div>
  );
}

// ─── Distributed Observations (research concept; no data, no network) ────────
export function Distributed() {
  const [reqState, setReqState] = useState<'idle'|'accepted'|'declined'>('idle');
  return (
    <div className="space-y-4 page-enter">
      <div className="flex items-baseline justify-between">
        <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Distributed Observations</h1>
        <MaturityBadge level="research" />
      </div>

      <div className="p-3 bg-purple-400/5 border border-purple-400/15 rounded-sm text-[11px] text-purple-400/80">
        This is a future research area. Features shown below are conceptual designs and are not yet implemented. No data is transmitted without explicit per-request consent.
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader title="Incoming Observation Request (concept)" badge={<MaturityBadge level="research" />} />
          <CardBody>
            {reqState === 'idle' && (
              <div>
                <div className="space-y-1 mb-4">
                  <MetricRow label="Type" value="WWV Doppler capture" />
                  <MetricRow label="Frequency" value="10.000 MHz" />
                  <MetricRow label="Duration" value="5 minutes" />
                  <MetricRow label="Purpose" value="Ionospheric propagation study" />
                  <MetricRow label="Requester" value="Example research group" />
                  <MetricRow label="Data product" value="IQ capture → derived Doppler" />
                </div>
                <div className="mb-3 p-2 rounded-sm text-[10px]" style={{ background:'var(--bg)', border:'1px solid var(--border)' }}>
                  <div className="font-medium mb-1.5" style={{ color:'var(--t3)' }}>Privacy settings for this request</div>
                  {['Share derived result (Doppler shift)', 'Use exact coordinates for solver', 'Raw IQ — local only, no upload'].map(p => (
                    <label key={p} className="flex items-center gap-2 py-0.5 cursor-pointer" style={{ color:'var(--t3)' }}>
                      <input type="checkbox" defaultChecked={p.includes('derived')} className="accent-cyan-400" />
                      {p}
                    </label>
                  ))}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => setReqState('accepted')} className="px-4 py-1.5 text-[11px] mono bg-green-400/15 text-green-400 border border-green-400/30 rounded hover:bg-green-400/25 transition-colors">ACCEPT</button>
                  <button onClick={() => setReqState('declined')} className="px-4 py-1.5 text-[11px] mono bg-red-400/10 text-red-400/70 border border-red-400/20 rounded hover:bg-red-400/20 transition-colors">DECLINE</button>
                </div>
              </div>
            )}
            {reqState !== 'idle' && (
              <div className="text-center py-6">
                <div className="text-[12px]" style={{ color:'var(--t2)' }}>
                  Concept only: nothing was scheduled or sent ({reqState}).
                </div>
                <button onClick={() => setReqState('idle')} className="mt-3 text-[10px] mono transition-colors" style={{ color:'var(--t3)' }}>Reset</button>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Observation Types (roadmap)" />
          <CardBody>
            <div className="space-y-1">
              {([
                ['RF capture (IQ)', 'research'], ['GNSS sky data', 'experimental'], ['WWV Doppler', 'research'],
                ['WSPR spots', 'planned'], ['ADS-B / Mode-S', 'planned'], ['Magnetometer', 'planned'],
                ['Lightning', 'planned'], ['Weather sensors', 'planned'], ['Acoustic', 'planned'], ['Timing test', 'research'],
              ] as const).map(([type, mat]) => (
                <div key={type} className="flex items-center justify-between py-1.5 last:border-b-0" style={{ borderBottom:'1px solid var(--border-dim)' }}>
                  <span className="text-[11px]" style={{ color:'var(--t2)' }}>{type}</span>
                  <MaturityBadge level={mat} />
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

// ─── Data & Logs ──────────────────────────────────────────────────────────────
export function DataLogs() {
  const { api, chain } = useStation();
  const sys = usePoll(() => api.system(), 10_000, [api]);
  const survey = usePoll(() => api.survey(), 30_000, [api]);
  const s = sys.data;
  const p = survey.data?.persistence;
  const events = allEvents(chain.data?.events.open, chain.data?.events.recent).slice(0, 8);
  return (
    <div className="space-y-4 page-enter">
      <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Data & Logs</h1>
      <ApiErrorNote error={sys.error ?? survey.error} />

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader title="Buffer & Storage" badge={<ProvenanceTag type="observed" />} />
          <CardBody>
            <MetricRow label="Tracking log" value={s?.ramlog ? (s.ramlog.in_ram ? 'in RAM' : 'on SD card') : null} />
            <MetricRow label="Tracking log size" value={s?.ramlog?.size_kb == null ? null : `${s.ramlog.size_kb.toFixed(1)} kB`} />
            <MetricRow label="Last SD flush" value={s?.ramlog?.flushed_age_s == null ? null : `${fmtDuration(s.ramlog.flushed_age_s)} ago`} />
            <MetricRow label="Config loaded from" value={p?.loaded_from ?? null} />
            <MetricRow label="Last config write" value={p ? (fmtUtc(p.last_write_utc) ?? 'none this session') : null} />
            <MetricRow label="Disk used" value={s?.disk ? `${(s.disk.total_gb - s.disk.free_gb).toFixed(1)} GB / ${s.disk.total_gb.toFixed(1)} GB` : null} />
            {p?.last_write_error && <div className="text-[10px] mt-1" style={{ color:'var(--err-text)' }}>Write error: {p.last_write_error}</div>}
            {p?.corrupt_moved_to && <div className="text-[10px] mt-1" style={{ color:'var(--warn-text)' }}>Unreadable config set aside: {p.corrupt_moved_to}</div>}
          </CardBody>
        </Card>
        <Planned title="Long-term Rollups" needs="hourly/daily summary storage">
        <Card>
          <CardHeader title="Long-term Rollups" />
          <CardBody>
            <MetricRow label="Hourly rollups" value="8,640" />
            <MetricRow label="Daily rollups" value="360" />
            <MetricRow label="Oldest record" value="2023-09-01" />
            <MetricRow label="Data retention" value="2 years" />
          </CardBody>
        </Card>
        </Planned>
        <Card>
          <CardHeader title="Timing Events (recent)" />
          <CardBody className="p-0">
            {events.map(e => (
              <div key={e.id} className="px-3 py-2 text-[10px]" style={{ borderBottom:'1px solid var(--border-dim)' }}>
                <span className="mono" style={{ color:'var(--t3)' }}>{fmtUtc(e.start_utc)} </span>
                <span className="mono font-medium" style={{ color: e.open ? 'var(--err-text)' : 'var(--warn-text)' }}>{e.type}{e.open ? ' (open)' : ''} </span>
                <span style={{ color:'var(--t2)' }}>{fmtDuration(e.duration_s) ?? ''} · {e.classification ?? 'UNKNOWN'}</span>
              </div>
            ))}
            {!events.length && <div className="px-3 py-3 text-[10px]" style={{ color:'var(--t4)' }}>{chain.data ? 'No events recorded.' : 'Not loaded.'}</div>}
          </CardBody>
        </Card>
      </div>

      <Planned title="Offline Data Packs" needs="a data-pack manifest endpoint">
      <Card>
        <CardHeader title="Offline Data Packs" />
        <CardBody className="p-0">
          <table className="w-full text-[11px]">
            <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
              {['Pack','Version','Size','Installed','Valid Through','State'].map(h=>(
                <th key={h} className="text-left px-4 py-2 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {dataPacks.map(p => (
                <tr key={p.name} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                  <td className="px-4 py-2" style={{ color:'var(--t2)' }}>{p.name}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{p.version}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{p.size}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{p.installed}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{p.validThru}</td>
                  <td className="px-4 py-2">
                    {p.state==='current' && <StatusBadge variant="good" label="current" dot={false} className="text-[9px]"/>}
                    {p.state==='unavail' && <StatusBadge variant="muted" label="network required" dot={false} className="text-[9px]"/>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
      </Planned>
    </div>
  );
}

// ─── Administration ───────────────────────────────────────────────────────────
export function Admin() {
  const { api, core } = useStation();
  const sys = usePoll(() => api.system(), 5_000, [api]);
  const s = sys.data;
  const v = core.data?.versions;
  const mode = core.data?.location.mode;
  const [msg, setMsg] = useState<string | null>(null);
  const auth = usePoll(() => api.auth(), 0, [api]);
  const canWrite = !!auth.data && (auth.data.authenticated || !auth.data.auth_required);
  const setMode = async (m: LocationMode) => {
    try {
      const r = await api.setLocationDisplay(m);
      setMsg(r.ok ? `Location display set to ${m}.` : 'The station rejected the setting.');
      core.refresh();
    } catch (e) { setMsg((e as Error).message); auth.refresh(); }
  };
  // Local-time display zone (lib/localtime.ts). Display only; the station keeps UTC.
  const stationZone = core.data?.timezone;
  const shownZone = resolveZone(stationZone);
  const [tzInput, setTzInput] = useState('');
  const [tzMsg, setTzMsg] = useState<string | null>(null);
  const saveZone = async (tz: string | null) => {
    if (tz !== null && !isValidZone(tz)) { setTzMsg(`"${tz}" is not a time zone this browser knows.`); return; }
    try {
      const r = await api.setTimezone(tz);
      setTzMsg(r.ok ? (tz ? `Local time is shown in ${tz}.` : 'Local time zone is automatic again.') : 'The station rejected the time zone.');
      if (r.ok) setTzInput('');
      core.refresh();
    } catch (e) { setTzMsg((e as Error).message); auth.refresh(); }
  };
  const throttledNow = s?.throttled?.flags.filter(f => f.now && f.active).map(f => f.label) ?? [];
  const throttledEver = s?.throttled?.flags.filter(f => !f.now && f.active).map(f => f.label) ?? [];
  return (
    <div className="space-y-4 page-enter">
      <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Administration / System</h1>
      <ApiErrorNote error={sys.error} />

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader title="System" badge={<ProvenanceTag type="observed" />} />
          <CardBody>
            <MetricRow label="Model" value={s?.model ?? null} />
            <MetricRow label="Kernel" value={s?.kernel ?? null} />
            <MetricRow label="Uptime" value={fmtDuration(s?.uptime_s)} />
            <MetricRow label="CPU temp." value={core.data?.cpu_temp_c ?? null} unit="°C" provenance="observed" />
            <MetricRow label="CPU clock" value={s?.cpu_mhz ?? null} unit="MHz" />
            <MetricRow label="Load avg." value={s?.load ? s.load.map(x => x.toFixed(2)).join(' / ') : null} />
            <MetricRow label="Memory" value={s?.mem ? `${s.mem.total_mb - s.mem.available_mb} MB / ${s.mem.total_mb} MB` : null} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Software" />
          <CardBody>
            <MetricRow label="GPS Time" value={v?.app ?? null} />
            <MetricRow label="chrony" value={v?.chrony ?? null} />
            <MetricRow label="gpsd" value={v?.gpsd ?? null} />
            <MetricRow label="Receiver" value={v?.receiver ? [v.receiver.driver, v.receiver.firmware].filter(Boolean).join(' · ') || null : null} />
            <MetricRow label="Receiver path" value={v?.receiver?.path ?? null} />
            <MetricRow label="Python" value={v?.python ?? null} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Power" badge={<ProvenanceTag type="observed" />} />
          <CardBody>
            <MetricRow label="Core voltage" value={s?.core_volts ?? null} />
            <MetricRow label="Input power" value={s?.power ? s.power.watts : null} unit="W" />
            <MetricRow label="Throttled now" value={s?.throttled ? (throttledNow.join(', ') || 'no') : null} />
            <MetricRow label="Since boot" value={s?.throttled ? (throttledEver.join(', ') || 'no') : null} />
            {s?.power_note && <div className="text-[10px] mt-1" style={{ color:'var(--t4)' }}>{s.power_note}</div>}
          </CardBody>
        </Card>
      </div>

      <AdminAccess auth={auth} />

      <Card>
        <CardHeader title="Location privacy" />
        <CardBody>
          <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>
            Controls what the station exposes in every page, API response and diagnostic snapshot.
          </div>
          <div className="flex gap-1">
            {(['exact', 'rounded', 'hidden'] as LocationMode[]).map(m => (
              <button key={m} onClick={() => setMode(m)} disabled={!core.data || !canWrite}
                className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
                style={mode === m
                  ? { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }
                  : { border:'1px solid var(--border)', color:'var(--t3)' }}>
                {m === 'rounded' ? 'rounded (~11 km)' : m}
              </button>
            ))}
          </div>
          {!canWrite && auth.data && (
            <div className="text-[10px] mt-2" style={{ color:'var(--t4)' }}>Changing this needs the admin token (Admin access, above).</div>
          )}
          {msg && <div className="text-[10px] mono mt-2" style={{ color:'var(--t3)' }}>{msg}</div>}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Local time zone" badge={shownZone.source === 'position' ? <ProvenanceTag type="calculated" /> : undefined} />
        <CardBody>
          <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>
            The zone the main clock shows local time in. Display only: the station's clock, logs and API stay on UTC.
          </div>
          <MetricRow label="Shown in" value={core.data ? shownZone.tz : null} />
          <MetricRow label="Source" value={core.data ? shownZone.label : null} />
          {stationZone && !stationZone.source && (
            <div className="text-[10px] mt-1" style={{ color:'var(--t4)' }}>Station: {stationZone.note}.</div>
          )}
          <div className="flex gap-1 mt-3">
            <input value={tzInput} onChange={e => setTzInput(e.target.value.trim())} list="gtp-zones" placeholder="e.g. America/New_York"
              aria-label="Time zone override (IANA name)" disabled={!canWrite}
              className="px-2 py-[5px] text-[10px] mono rounded-[2px] flex-1"
              style={{ background:'transparent', border:'1px solid var(--border)', color:'var(--t1)' }} />
            <datalist id="gtp-zones">{zoneNames().map(z => <option key={z} value={z} />)}</datalist>
            <button onClick={() => saveZone(tzInput)} disabled={!canWrite || !tzInput}
              className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={{ border:'1px solid var(--border)', color:'var(--t2)' }}>
              set override
            </button>
            <button onClick={() => saveZone(null)} disabled={!canWrite || stationZone?.source !== 'override'}
              className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={{ border:'1px solid var(--border)', color:'var(--t3)' }}>
              automatic
            </button>
          </div>
          <div className="text-[10px] mt-2" style={{ color:'var(--t4)' }}>
            Automatic: the zone is found offline from the station's position. With the location hidden it is not derived from the position;
            the override, or each browser's own zone, is used instead.
          </div>
          {!canWrite && auth.data && (
            <div className="text-[10px] mt-1" style={{ color:'var(--t4)' }}>Changing this needs the admin token (Admin access, above).</div>
          )}
          {tzMsg && <div className="text-[10px] mono mt-2" style={{ color:'var(--t3)' }}>{tzMsg}</div>}
        </CardBody>
      </Card>

      <Planned title="Services & Network" needs="service and interface status endpoints">
      <Card>
        <CardHeader title="Services" />
        <CardBody className="p-0">
          <table className="w-full text-[11px]">
            <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
              {['Service','Status','PID','Uptime','Restarts'].map(h=>(
                <th key={h} className="text-left px-4 py-2 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {[
                { name:'gpsd',         st:'running', pid:1842, up:'31d 7h', restarts:0 },
                { name:'chronyd',      st:'running', pid:1856, up:'31d 7h', restarts:0 },
                { name:'gps-time-pi',  st:'running', pid:2041, up:'31d 7h', restarts:0 },
              ].map(s => (
                <tr key={s.name} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}>{s.name}</td>
                  <td className="px-4 py-2"><StatusBadge variant="good" label={s.st} dot={false} className="text-[9px]"/></td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{s.pid}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{s.up}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{s.restarts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
      </Planned>

    </div>
  );
}

// ─── Admin access (admin token; review GPS-014) ──────────────────────────────
function AdminAccess({ auth }: { auth: Polled<AuthState> }) {
  const { api } = useStation();
  const [input, setInput] = useState('');
  const a = auth.data;
  const stored = !!api.token.get();
  const state = !a ? (auth.error ? 'UNKNOWN' : '…')
    : a.demo ? 'DEMO: no token needed; host actions are simulated'
    : !a.admin_configured ? 'DISABLED on this station'
    : a.authenticated ? 'TOKEN ACCEPTED (this tab)'
    : stored ? 'TOKEN NOT ACCEPTED' : 'NO TOKEN ENTERED';
  const variant = !a ? 'muted' : a.demo || a.authenticated ? 'good' : !a.admin_configured ? 'muted' : 'warn';
  const use = () => { api.token.set(input); setInput(''); auth.refresh(); };
  const forget = () => { api.token.set(null); auth.refresh(); };
  const btn = { border:'1px solid var(--border)', color:'var(--t2)' };
  return (
    <Card>
      <CardHeader title="Admin access" badge={<StatusBadge variant={variant as 'good' | 'warn' | 'muted'} label={state} dot={false} />} />
      <CardBody>
        <ApiErrorNote error={auth.error} />
        <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>
          Settings changes and service actions need the station's admin token, sent only to this station over POST.
          It is kept for this browser tab only. {a && !a.demo && !a.admin_configured &&
            <>Admin is off until a token exists: run <span className="mono">sudo python3 -m gps_time_pi.admin_token</span> on the station.</>}
        </div>
        {a && !a.demo && a.admin_configured && (
          <div className="flex gap-1.5 items-center">
            <input type="password" value={input} onChange={e => setInput(e.target.value)} placeholder="admin token"
              autoComplete="off" spellCheck={false} aria-label="Admin token"
              onKeyDown={e => { if (e.key === 'Enter' && input.trim()) use(); }}
              className="mono text-[11px] px-2 py-1 rounded-[2px] w-72" style={{ background:'var(--bg)', border:'1px solid var(--border)', color:'var(--t1)' }} />
            <button onClick={use} disabled={!input.trim()} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Use token</button>
            {stored && <button onClick={forget} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Forget</button>}
          </div>
        )}
        <div className="text-[10px] mt-2" style={{ color:'var(--t4)' }}>
          Service actions (flush logs, restart gpsd/chrony/web, reboot) and survey reset are on the legacy <a href="../admin" style={{ color:'var(--t3)' }}>/admin</a> page, which uses the same token.
        </div>
      </CardBody>
    </Card>
  );
}
