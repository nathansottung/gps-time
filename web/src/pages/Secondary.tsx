import { useState } from 'react';
import { Card, CardHeader, CardBody, MetricRow, StatusBadge, MaturityBadge, ELI5, ProvenanceTag } from '../components/ui';
import { ntpClients, sunData, moonData, adsbStats, dataPacks } from '../data/demo';
import { SolarCurve } from '../components/charts';

// ─── Sun & Astronomy ──────────────────────────────────────────────────────────
export function SunAstronomy() {
  const [safetyAck, setSafetyAck] = useState(false);

  const irradData = Array.from({ length: 24 }, (_, h) => ({
    h, w: Math.round(Math.max(0, 850 * Math.sin(Math.PI * (h - 6) / 13)) * (h>=6&&h<=19?1:0)),
  }));

  return (
    <div className="space-y-4 page-enter">
      <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Sun & Astronomy</h1>

      <div className="grid grid-cols-2 gap-4">
        {/* Sun / Daylight */}
        <Card>
          <CardHeader title="Sun / Daylight — Yesterday / Today / Tomorrow" badge={<ProvenanceTag type="calculated" />} />
          <CardBody>
            <div className="grid grid-cols-3 gap-3 text-[11px]">
              {[
                { label:'Yesterday', data:{ rise:'06:47:12', noon:'12:48:31', set:'18:49:43', dur:'12h 02m 31s' }, chg:'+3m 02.8s', sign:'+' },
                { label:'Today',     data:{ rise:'06:48:04', noon:'12:48:19', set:'18:48:24', dur:'12h 00m 20s' }, chg:'−2m 11.3s', sign:'-' },
                { label:'Tomorrow',  data:{ rise:'06:48:57', noon:'12:48:07', set:'18:47:05', dur:'11h 58m 08s' }, chg:'−2m 12.1s', sign:'-' },
              ].map(({ label, data, chg, sign }) => (
                <div key={label} className={`rounded-sm p-2.5 ${label==='Today'?'bg-amber-400/5 border border-amber-400/15':''}`} style={label!=='Today'?{ background:'var(--bg)', border:'1px solid var(--border)' }:{}}>
                  <div className="text-[10px] mono uppercase mb-2" style={{ color: label==='Today' ? 'var(--warn-text)' : 'var(--t3)' }}>{label}</div>
                  {[['Sunrise',data.rise],['Solar noon',data.noon],['Sunset',data.set]].map(([k,v])=>(
                    <div key={k} className="flex justify-between py-0.5"><span style={{ color:'var(--t3)' }}>{k}</span><span className="mono">{v}</span></div>
                  ))}
                  <div className="flex justify-between py-0.5 mt-1" style={{ borderTop:'1px solid var(--border)' }}><span style={{ color:'var(--t3)' }}>Daylight</span><span className="mono font-medium">{data.dur}</span></div>
                  <div className="flex justify-between py-0.5"><span style={{ color:'var(--t3)' }}>Change</span><span className={`mono text-[10px] ${sign==='+'?'text-green-400/70':'text-amber-400/70'}`}>{chg}</span></div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>

        {/* Solar Position */}
        <Card>
          <CardHeader title="Solar Position (Now)" badge={<ProvenanceTag type="calculated" />} />
          <CardBody>
            <MetricRow label="Elevation" value="38.4°" />
            <MetricRow label="Azimuth" value="187.2°" />
            <MetricRow label="Apparent solar time" value="12:33:14" />
            <MetricRow label="Equation of time" value="−9.8 min" provenance="calculated" />
            <MetricRow label="Time to sunset" value="5h 41m" />
            <MetricRow label="Solar declination" value="+0.5°" provenance="calculated" />
            <ELI5 text="The equation of time is the difference between apparent solar time and mean solar time — how far ahead or behind the Sun runs compared to a regular clock." />
          </CardBody>
        </Card>
      </div>

      {/* Solar Phase Calculator */}
      <Card>
        <CardHeader title="Solar-Equivalent Time Calculator" badge={<ProvenanceTag type="calculated" />} />
        <CardBody>
          <div className="text-[11px] mb-3" style={{ color:'var(--t2)' }}>
            Find what civil time on a different date corresponds to the same point in the solar day as a given time today. Useful for solar-based event comparison.
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-[10px] block mb-1" style={{ color:'var(--t3)' }}>Reference date</label>
              <input type="date" defaultValue="2024-09-28" className="w-full rounded px-2 py-1.5 text-[11px] mono outline-none focus:border-cyan-400/40" style={{ background:'var(--bg)', border:'1px solid var(--border)', color:'var(--t2)' }}/>
            </div>
            <div>
              <label className="text-[10px] block mb-1" style={{ color:'var(--t3)' }}>Reference time</label>
              <input type="time" defaultValue="07:30:00" className="w-full rounded px-2 py-1.5 text-[11px] mono outline-none focus:border-cyan-400/40" style={{ background:'var(--bg)', border:'1px solid var(--border)', color:'var(--t2)' }}/>
            </div>
            <div>
              <label className="text-[10px] block mb-1" style={{ color:'var(--t3)' }}>Target date</label>
              <input type="date" defaultValue="2024-12-21" className="w-full rounded px-2 py-1.5 text-[11px] mono outline-none focus:border-cyan-400/40" style={{ background:'var(--bg)', border:'1px solid var(--border)', color:'var(--t2)' }}/>
            </div>
          </div>
          <div className="mt-3 p-3 bg-cyan-400/5 border border-cyan-400/15 rounded-sm">
            <div className="text-[10px] mb-1" style={{ color:'var(--t3)' }}>Equivalent civil time on target date (same solar phase)</div>
            <div className="mono text-lg" style={{ color:'var(--live)' }}>08:14:33</div>
            <div className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>Solar phase 27.3% through the day · Sun elevation at ref: 28.1°</div>
          </div>
        </CardBody>
      </Card>

      {/* Solar irradiance */}
      <div className="grid grid-cols-2 gap-4">
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

        <Card>
          <CardHeader title="Moon & Night Sky" />
          <CardBody>
            <MetricRow label="Phase" value={moonData.phase} />
            <MetricRow label="Illumination" value={`${(moonData.illumination*100).toFixed(0)}%`} />
            <MetricRow label="Age" value={`${moonData.age}`} unit="days" />
            <MetricRow label="Moonrise" value={moonData.rise} />
            <MetricRow label="Lunar transit" value={moonData.transit} />
            <MetricRow label="Moonset" value={moonData.set} />
            <div className="mt-2 pt-2" style={{ borderTop:'1px solid var(--border)' }}>
              <MetricRow label="Astronomical twilight end" value="20:42" />
              <MetricRow label="Moonless darkness" value="0h 0m" muted />
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Sidereal & Transit predictions */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader title="Sidereal Time" badge={<ProvenanceTag type="calculated" />} />
          <CardBody>
            <MetricRow label="Local Sidereal Time" value="14h 32m 19.4s" />
            <MetricRow label="Greenwich Sidereal Time" value="23h 54m 11.2s" />
            <div className="mt-2 text-[10px]" style={{ color:'var(--t3)' }}>Sidereal time is astronomically independent of solar-equivalent time tools above.</div>
          </CardBody>
        </Card>
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
  const stateColor = { active:'var(--good-text)', recent:'var(--warn-text)', stale:'var(--t3)' };
  return (
    <div className="space-y-4 page-enter">
      <div className="flex items-baseline justify-between">
        <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Network & Devices</h1>
        <StatusBadge variant="good" label="NTP SERVING" />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader title="NTP Server" />
          <CardBody>
            <MetricRow label="State" value="ACTIVE" />
            <MetricRow label="Stratum" value="1" />
            <MetricRow label="Source" value="GPS/PPS" />
            <MetricRow label="Allowed networks" value="LAN only" />
            <MetricRow label="Request rate" value="23 req/min" />
            <MetricRow label="Clients" value="7" />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Browser Connection Test" badge={<ProvenanceTag type="observed" />} />
          <CardBody>
            <MetricRow label="RTT (current)" value="2.3 ms" />
            <MetricRow label="RTT (minimum)" value="1.9 ms" />
            <MetricRow label="RTT (median)" value="2.1 ms" />
            <MetricRow label="RTT (p95)" value="3.4 ms" />
            <MetricRow label="Jitter" value="0.4 ms" />
            <MetricRow label="Est. browser Δt" value="−1.2 ms" provenance="inferred" />
            <ELI5 text="Using four-timestamp exchange (like NTP), the browser's clock offset can be estimated. Accuracy is limited by asymmetric network paths and browser timer resolution." />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Offline Status" />
          <CardBody>
            <MetricRow label="Internet" value="NOT CONNECTED" />
            <MetricRow label="Local timing" value="OPERATIONAL" />
            <MetricRow label="NTP server" value="SERVING" />
            <MetricRow label="GNSS" value="LOCKED" />
            <div className="mt-3 p-2 bg-green-400/5 border border-green-400/15 rounded-sm text-[10px] text-green-400/70">
              Station is fully operational without internet access.
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="NTP Clients" />
        <CardBody className="p-0">
          <div className="px-4 py-2 text-[10px]" style={{ borderBottom:'1px solid var(--border-dim)', color:'var(--t3)' }}>
            Polling this server does not prove the client clock is accurate.
          </div>
          <table className="w-full text-[11px]">
            <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
              {['IP Address','First Seen','Last Poll','Requests','Interval','State'].map(h=>(
                <th key={h} className="text-left px-4 py-2 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {ntpClients.map(c => (
                <tr key={c.ip} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}>{c.ip}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{c.firstSeen}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}>{c.lastPoll}</td>
                  <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>{c.count.toLocaleString()}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{c.interval}</td>
                  <td className="px-4 py-2">
                    <span className="mono text-[10px]" style={{ color: stateColor[c.state as keyof typeof stateColor] }}>{c.state.toUpperCase()}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Aviation ─────────────────────────────────────────────────────────────────
export function Aviation() {
  return (
    <div className="space-y-4 page-enter">
      <div className="flex items-baseline justify-between">
        <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Aviation — ADS-B / Mode-S</h1>
        <StatusBadge variant="good" label="1090 ACTIVE" />
      </div>

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

      {/* Placeholder aircraft list */}
      <Card>
        <CardHeader title="Aircraft in View (Demo)" badge={<MaturityBadge level="demo" />} />
        <CardBody className="p-0">
          <table className="w-full text-[11px]">
            <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
              {['ICAO','Callsign','Alt (ft)','GS (kts)','Hdg','Dist (km)','Source'].map(h=>(
                <th key={h} className="text-left px-4 py-2 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {[
                { icao:'A1B2C3', cs:'UAL123', alt:37000, gs:482, hdg:275, dist:41, src:'ADS-B' },
                { icao:'A3D4E5', cs:'DAL456', alt:31000, gs:441, hdg:92, dist:78, src:'ADS-B' },
                { icao:'A7F8G9', cs:'SWA789', alt:24500, gs:388, hdg:181, dist:112, src:'MLAT' },
                { icao:'AABBCC', cs:'N14271', alt: 4500, gs:135, hdg:35,  dist:23, src:'ADS-B' },
              ].map(a => (
                <tr key={a.icao} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                  <td className="px-4 py-2 mono" style={{ color:'var(--live)' }}>{a.icao}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}>{a.cs}</td>
                  <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>{a.alt.toLocaleString()}</td>
                  <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>{a.gs}</td>
                  <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>{a.hdg}</td>
                  <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>{a.dist}</td>
                  <td className="px-4 py-2"><StatusBadge variant={a.src==='ADS-B'?'info':'warn'} label={a.src} dot={false} className="text-[9px]"/></td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Distributed Observations ─────────────────────────────────────────────────
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
        {/* Observation request */}
        <Card>
          <CardHeader title="Incoming Observation Request" badge={<MaturityBadge level="research" />} />
          <CardBody>
            {reqState === 'idle' && (
              <div>
                <div className="space-y-1 mb-4">
                  <MetricRow label="Type" value="WWV Doppler capture" />
                  <MetricRow label="UTC window" value="2024-09-29 02:00–02:05" />
                  <MetricRow label="Frequency" value="10.000 MHz" />
                  <MetricRow label="Duration" value="5 minutes" />
                  <MetricRow label="Purpose" value="Ionospheric propagation study" />
                  <MetricRow label="Requester" value="W1AW / ARRL Laboratory" />
                  <MetricRow label="Data product" value="IQ capture → derived Doppler" />
                </div>

                <div className="mb-3 p-2 rounded-sm text-[10px]" style={{ background:'var(--bg)', border:'1px solid var(--border)' }}>
                  <div className="font-medium mb-1.5" style={{ color:'var(--t3)' }}>Privacy settings for this request</div>
                  {[
                    'Share derived result (Doppler shift)',
                    'Use exact coordinates for solver',
                    'Raw IQ — local only, no upload',
                  ].map(p => (
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
            {reqState === 'accepted' && (
              <div className="text-center py-6">
                <div className="text-green-400 text-xl mb-2">✓</div>
                <div className="text-[12px]" style={{ color:'var(--t2)' }}>Request accepted. Observation scheduled for 02:00 UTC.</div>
                <button onClick={() => setReqState('idle')} className="mt-3 text-[10px] mono transition-colors" style={{ color:'var(--t3)' }}>Reset demo</button>
              </div>
            )}
            {reqState === 'declined' && (
              <div className="text-center py-6">
                <div className="text-red-400/70 text-xl mb-2">✗</div>
                <div className="text-[12px]" style={{ color:'var(--t3)' }}>Request declined. No data will be collected.</div>
                <button onClick={() => setReqState('idle')} className="mt-3 text-[10px] mono transition-colors" style={{ color:'var(--t3)' }}>Reset demo</button>
              </div>
            )}
          </CardBody>
        </Card>

        {/* Observation types */}
        <Card>
          <CardHeader title="Supported Observation Types" />
          <CardBody>
            <div className="space-y-1">
              {[
                { type:'RF capture (IQ)',  mat:'research' },
                { type:'GNSS sky data',    mat:'experimental' },
                { type:'WWV Doppler',      mat:'experimental' },
                { type:'WSPR spots',       mat:'experimental' },
                { type:'ADS-B / Mode-S',   mat:'supported' },
                { type:'Magnetometer',     mat:'planned' },
                { type:'Lightning',        mat:'planned' },
                { type:'Weather sensors',  mat:'planned' },
                { type:'Acoustic',         mat:'planned' },
                { type:'Timing test',      mat:'research' },
              ].map(({ type, mat }) => (
                <div key={type} className="flex items-center justify-between py-1.5 last:border-b-0" style={{ borderBottom:'1px solid var(--border-dim)' }}>
                  <span className="text-[11px]" style={{ color:'var(--t2)' }}>{type}</span>
                  <MaturityBadge level={mat as any} />
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
  return (
    <div className="space-y-4 page-enter">
      <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Data & Logs</h1>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader title="Buffer & Storage" />
          <CardBody>
            <MetricRow label="RAM buffer" value="47 MB / 256 MB" />
            <MetricRow label="Last checkpoint" value="4m 12s ago" />
            <MetricRow label="Pending data" value="~2.1 MB" />
            <MetricRow label="Unsaved window" value="~4m" />
            <MetricRow label="Storage health" value="OK" />
            <MetricRow label="Disk used" value="14.2 GB / 64 GB" />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Long-term Rollups" />
          <CardBody>
            <MetricRow label="Hourly rollups" value="8,640" />
            <MetricRow label="Daily rollups" value="360" />
            <MetricRow label="Oldest record" value="2023-09-01" />
            <MetricRow label="Total events" value="1,247,819" />
            <MetricRow label="Data retention" value="2 years" />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Event Log (Recent)" />
          <CardBody className="p-0">
            <div className="divide-y divide-[#1a1e2e]">
              {[
                { ts:'09:41:02', level:'INFO', msg:'PPS lock acquired' },
                { ts:'09:40:28', level:'WARN', msg:'PPS signal lost' },
                { ts:'08:12:01', level:'INFO', msg:'NTP client 192.168.1.25 new' },
                { ts:'07:00:00', level:'INFO', msg:'Daily summary generated' },
                { ts:'06:48:04', level:'INFO', msg:'Sunrise computed: 06:48:04' },
              ].map(e => (
                <div key={e.ts} className="px-3 py-2 text-[10px]">
                  <span className="mono" style={{ color:'var(--t3)' }}>{e.ts} </span>
                  <span className="mono font-medium" style={{ color: e.level==='WARN' ? 'var(--warn-text)' : 'var(--live)' }}>{e.level} </span>
                  <span style={{ color:'var(--t2)' }}>{e.msg}</span>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>

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
                    {p.state==='unavail' && <StatusBadge variant="muted" label="offline" dot={false} className="text-[9px]"/>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Administration ───────────────────────────────────────────────────────────
export function Admin() {
  return (
    <div className="space-y-4 page-enter">
      <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Administration / System</h1>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader title="System" />
          <CardBody>
            <MetricRow label="Hostname" value="atlas-01.local" />
            <MetricRow label="OS" value="Raspberry Pi OS Bookworm" />
            <MetricRow label="Kernel" value="6.6.31-v8+" />
            <MetricRow label="Uptime" value="31d 7h 14m" />
            <MetricRow label="CPU temp." value="48.2 °C" provenance="observed" />
            <MetricRow label="Load avg." value="0.14 / 0.12 / 0.09" />
            <MetricRow label="Memory" value="812 MB / 4096 MB" />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="GPS Time Software" />
          <CardBody>
            <MetricRow label="Version" value="0.4.2-beta" />
            <MetricRow label="Build date" value="2024-09-20" />
            <MetricRow label="chrony" value="4.5" />
            <MetricRow label="gpsd" value="3.25" />
            <MetricRow label="LinuxPPS" value="kernel built-in" />
            <MetricRow label="dump1090" value="9.0 (fa)" />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Network" />
          <CardBody>
            <MetricRow label="Interface" value="eth0" />
            <MetricRow label="IP address" value="192.168.1.5" />
            <MetricRow label="Subnet" value="/24" />
            <MetricRow label="Gateway" value="192.168.1.1" />
            <MetricRow label="Internet" value="Not connected" />
            <MetricRow label="SSH" value="Enabled (port 22)" />
          </CardBody>
        </Card>
      </div>

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
                { name:'gpsd',           st:'running', pid:1842, up:'31d 7h', restarts:0 },
                { name:'chronyd',        st:'running', pid:1856, up:'31d 7h', restarts:0 },
                { name:'gpstime-server', st:'running', pid:2041, up:'31d 7h', restarts:0 },
                { name:'dump1090-fa',    st:'running', pid:2108, up:'31d 6h', restarts:1 },
                { name:'dump978-fa',     st:'running', pid:2115, up:'31d 6h', restarts:0 },
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
    </div>
  );
}
