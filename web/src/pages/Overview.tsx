import { useState } from 'react';
import { Card, CardHeader, CardBody, MetricRow, StatusBadge, ELI5, ProvenanceTag, DemoBanner, MaturityBadge } from '../components/ui';
import { OffsetChart, SkyPlot, SolarCurve } from '../components/charts';
import { timing, holdover, satellites, offset1h, sunData, moonData, dataPacks, ppsStats } from '../data/demo';

const irradianceData = Array.from({ length: 24 }, (_, h) => ({
  h, w: Math.round(Math.max(0, 850 * Math.sin(Math.PI*(h-6)/13)) * (h>=6&&h<=19?1:0)),
}));

// ─── Timing Quality ───────────────────────────────────────────────────────────
function TimingWidget() {
  return (
    <Card>
      <CardHeader title="Timing Quality" badge={<StatusBadge variant="good" label="GPS PPS LOCKED" pulse />} />
      <CardBody>
        <div className="flex items-start gap-8 mb-3">
          {/* Primary reading — the one place we use the brightest live color */}
          <div className="flex-shrink-0">
            <div className="text-[9px] mono uppercase tracking-[0.15em] mb-1.5" style={{ color:'var(--t3)' }}>Current Δt</div>
            <div className="flex items-baseline gap-2">
              <span className="mono tabular font-semibold" style={{ fontSize:36, lineHeight:1, color:'var(--live-bright)', letterSpacing:'-0.01em' }}>+12.3</span>
              <div className="flex flex-col">
                <span className="mono text-base" style={{ color:'var(--t2)' }}>ns</span>
                <span className="mono text-[10px]" style={{ color:'var(--t3)' }}>± 4.1</span>
              </div>
            </div>
            <div className="text-[10px] mono mt-1" style={{ color:'var(--t4)' }}>≡ 3.69 m light-equivalent</div>
            <ELI5 text="This is how far ahead or behind the station clock is from GPS truth, in nanoseconds. 12 ns is the time light takes to travel 3.7 metres." />
          </div>

          {/* Offset history chart */}
          <div className="flex-1 min-w-0" style={{ borderLeft:'1px solid var(--border-dim)', paddingLeft:'1.5rem' }}>
            <div className="text-[9px] mono uppercase tracking-[0.15em] mb-1" style={{ color:'var(--t3)' }}>Δt — last 1 hour</div>
            <OffsetChart data={offset1h} range="1h" />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-x-6" style={{ borderTop:'1px solid var(--border-dim)', paddingTop:'0.75rem' }}>
          <div>
            <MetricRow label="24 h RMS Δt" value="18.7" unit="ns" provenance="observed" />
            <MetricRow label="Δf/f (frac. freq.)" value="−1.24×10⁻⁹" provenance="observed" />
          </div>
          <div>
            <MetricRow label="PPS lock duration" value="312h 24m" provenance="observed" />
            <MetricRow label="PPS availability (30d)" value="99.71 %" provenance="observed" />
          </div>
          <div>
            <MetricRow label="Reference source" value="GPS/PPS" />
            <MetricRow label="NTP stratum" value="1" />
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Holdover ─────────────────────────────────────────────────────────────────
function HoldoverWidget() {
  return (
    <Card>
      <CardHeader title="Holdover Characterization" />
      <CardBody>
        <div className="grid grid-cols-3 gap-3">
          {/* Raw */}
          <div className="rounded-[2px] p-3" style={{ background:'rgba(255,255,255,0.018)', border:'1px solid var(--border-dim)' }}>
            <div className="text-[9px] mono uppercase tracking-[0.12em] mb-2" style={{ color:'var(--t4)' }}>Raw Oscillator</div>
            <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>Free-running quartz, no discipline</div>
            <div className="text-[11px]" style={{ color:'var(--t2)' }}>1 s error in <span className="mono font-medium" style={{ color:'var(--warn-text)' }}>~1.4 days</span></div>
            <div className="text-[9px] mono mt-1" style={{ color:'var(--t4)' }}>±8.4 ppb/s drift</div>
          </div>

          {/* Trained */}
          <div className="rounded-[2px] p-3" style={{ background:'rgba(91,140,184,0.04)', border:'1px solid rgba(91,140,184,0.14)' }}>
            <div className="flex items-center gap-1.5 mb-2">
              <span className="text-[9px] mono uppercase tracking-[0.12em]" style={{ color:'var(--accent)' }}>Trained Holdover</span>
              <ProvenanceTag type="modeled" />
            </div>
            <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>72 h characterization window</div>
            <div className="text-[11px]" style={{ color:'var(--t2)' }}>1 s error in <span className="mono font-medium" style={{ color:'var(--live)' }}>~37 days</span></div>
            <div className="text-[9px] mono mt-1" style={{ color:'var(--t4)' }}>48 h validated confidence window</div>
            <ELI5 text="After learning GPS corrections for 72 hours, the system models oscillator drift. Projections beyond the validated window grow increasingly uncertain." />
          </div>

          {/* GPS-disciplined */}
          <div className="rounded-[2px] p-3" style={{ background:'var(--good-bg)', border:'1px solid var(--good-border)' }}>
            <div className="text-[9px] mono uppercase tracking-[0.12em] mb-2" style={{ color:'var(--good-text)' }}>GPS/PPS Disciplined</div>
            <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>Continuously corrected by PPS tick</div>
            <div className="text-[11px]" style={{ color:'var(--t2)' }}>Δt held within <span className="mono font-medium" style={{ color:'var(--good-text)' }}>~50 ns</span></div>
            <div className="text-[9px] mt-1" style={{ color:'var(--t4)' }}>No extrapolated long-term accuracy claimed</div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Sun ──────────────────────────────────────────────────────────────────────
function SunWidget() {
  const cols = [
    { label:'Yesterday', rise:'06:47:12', noon:'12:48:31', set:'18:49:43', dur:'12h 02m 31s', chg:'+3m 02.8s', plus:true },
    { label:'Today',     rise:'06:48:04', noon:'12:48:19', set:'18:48:24', dur:'12h 00m 20s', chg:'−2m 11.3s', plus:false },
    { label:'Tomorrow',  rise:'06:48:57', noon:'12:48:07', set:'18:47:05', dur:'11h 58m 08s', chg:'−2m 12.1s', plus:false },
  ];
  return (
    <Card>
      <CardHeader title="Sun & Daylight" badge={<ProvenanceTag type="calculated" />} />
      <CardBody>
        <div className="grid grid-cols-3 gap-2 text-[11px]">
          {cols.map(c => (
            <div key={c.label} className="rounded-[2px] p-2.5"
              style={c.label==='Today'
                ? { background:'rgba(176,120,16,0.05)', border:'1px solid rgba(176,120,16,0.14)' }
                : { background:'rgba(255,255,255,0.015)', border:'1px solid var(--border-dim)' }}>
              <div className="text-[9px] mono uppercase tracking-[0.12em] mb-2"
                style={{ color: c.label==='Today' ? 'var(--warn-text)' : 'var(--t4)' }}>{c.label}</div>
              {[['Sunrise',c.rise],['Solar noon',c.noon],['Sunset',c.set]].map(([k,v])=>(
                <div key={k as string} className="flex justify-between py-[3px]">
                  <span style={{ color:'var(--t3)' }}>{k}</span>
                  <span className="mono" style={{ color:'var(--t1)' }}>{v}</span>
                </div>
              ))}
              <div className="flex justify-between py-[3px] mt-1" style={{ borderTop:'1px solid var(--border-dim)' }}>
                <span style={{ color:'var(--t3)' }}>Daylight</span>
                <span className="mono font-medium" style={{ color:'var(--t1)' }}>{c.dur}</span>
              </div>
              <div className="flex justify-between py-[2px]">
                <span style={{ color:'var(--t3)' }}>Change</span>
                <span className="mono text-[9px]" style={{ color: c.plus ? 'var(--good-text)' : 'var(--t3)' }}>{c.chg}</span>
              </div>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

// ─── GNSS Summary ─────────────────────────────────────────────────────────────
function GNSSWidget() {
  const used   = satellites.filter(s=>s.state==='used').length;
  const total  = satellites.length;
  const bestCn0 = Math.max(...satellites.map(s=>s.cn0));
  const cn0s   = [...satellites.map(s=>s.cn0)].sort((a,b)=>a-b);
  const medCn0 = cn0s[Math.floor(cn0s.length/2)];
  return (
    <Card>
      <CardHeader title="GNSS" badge={<StatusBadge variant="good" label="3D FIX" />} />
      <CardBody>
        {/* Count row */}
        <div className="flex gap-0 mb-3" style={{ borderBottom:'1px solid var(--border-dim)', paddingBottom:'0.75rem' }}>
          {[
            { v:total,  l:'In view' },
            { v:total,  l:'Tracked' },
            { v:used,   l:'Used', accent:true },
          ].map(({v,l,accent}) => (
            <div key={l} className="flex-1 text-center">
              <div className="mono text-xl font-medium tabular" style={{ color: accent ? 'var(--live)' : 'var(--t1)' }}>{v}</div>
              <div className="text-[9px]" style={{ color:'var(--t4)' }}>{l}</div>
            </div>
          ))}
        </div>
        <MetricRow label="Best C/N₀" value={`${bestCn0}`} unit="dB-Hz" provenance="observed" />
        <MetricRow label="Median C/N₀" value={`${medCn0}`} unit="dB-Hz" provenance="observed" />
        <MetricRow label="PDOP" value="1.4" provenance="observed" />
        <ELI5 text="C/N₀ (carrier-to-noise-density) measures how clearly each satellite is heard above background noise. Higher is better." />
        <div className="mt-3 flex justify-center">
          <SkyPlot sats={satellites} />
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Network ──────────────────────────────────────────────────────────────────
function NetworkWidget() {
  return (
    <Card>
      <CardHeader title="Network & NTP" />
      <CardBody>
        <MetricRow label="NTP clients" value="7" />
        <MetricRow label="Request rate" value="23" unit="req/min" />
        <MetricRow label="Browser RTT" value="2.3" unit="ms" provenance="observed" />
        <MetricRow label="Est. browser Δt" value="−1.2" unit="ms" provenance="inferred" />
        <MetricRow label="Offline status" value="OFFLINE READY" />
        <div className="mt-3 text-[10px] px-2 py-1.5 rounded-[2px]"
          style={{ background:'rgba(255,255,255,0.02)', border:'1px solid var(--border-dim)', color:'var(--t4)' }}>
          Polling this server does not confirm client clock accuracy.
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Solar ────────────────────────────────────────────────────────────────────
function SolarWidget() {
  return (
    <Card>
      <CardHeader title="Solar Irradiance" badge={<ProvenanceTag type="modeled" />} />
      <CardBody>
        <div className="flex items-baseline gap-5 mb-3">
          <div>
            <div className="mono tabular font-medium text-lg" style={{ color:'var(--warn-text)' }}>612</div>
            <div className="text-[9px]" style={{ color:'var(--t4)' }}>W/m² now</div>
          </div>
          <div style={{ borderLeft:'1px solid var(--border-dim)', paddingLeft:'1.25rem' }}>
            <div className="mono tabular font-medium text-lg" style={{ color:'var(--warn-text)', opacity:0.7 }}>5.4</div>
            <div className="text-[9px]" style={{ color:'var(--t4)' }}>kWh/m²/day est.</div>
          </div>
        </div>
        <SolarCurve data={irradianceData} />
        <div className="text-[9px] mt-1.5" style={{ color:'var(--t4)' }}>Clear-sky model — actual varies with cloud cover.</div>
      </CardBody>
    </Card>
  );
}

// ─── Data Packs ───────────────────────────────────────────────────────────────
function DataPackWidget() {
  const allOk = dataPacks.filter(p=>p.state!=='unavail').every(p=>p.state==='current');
  return (
    <Card>
      <CardHeader title="Offline Readiness" badge={allOk ? <StatusBadge variant="good" label="OFFLINE READY" /> : <StatusBadge variant="warn" label="INCOMPLETE" />} />
      <CardBody>
        {dataPacks.map(p => (
          <div key={p.name} className="flex items-center justify-between py-[5px] row-sep">
            <span className="text-[11px]" style={{ color:'var(--t2)' }}>{p.name}</span>
            <div className="flex items-center gap-2">
              {p.state==='current'  && <StatusBadge variant="good"  label="current" dot={false} className="text-[8px]"/>}
              {p.state==='unavail'  && <StatusBadge variant="muted" label="network req." dot={false} className="text-[8px]"/>}
              {p.version!=='—' && <span className="mono text-[9px]" style={{ color:'var(--t4)' }}>{p.version}</span>}
            </div>
          </div>
        ))}
      </CardBody>
    </Card>
  );
}

// ─── Moon ─────────────────────────────────────────────────────────────────────
function MoonWidget() {
  const illum = moonData.illumination;
  return (
    <Card>
      <CardHeader title="Moon & Night Sky" />
      <CardBody>
        <div className="flex items-start gap-4">
          {/* Phase graphic */}
          <svg width="44" height="44" viewBox="0 0 44 44" className="flex-shrink-0">
            <circle cx="22" cy="22" r="19" fill="var(--border)" stroke="var(--border-em)" strokeWidth="0.75"/>
            <ellipse cx="22" cy="22" rx={Math.abs(19*Math.cos(moonData.age/29.5*Math.PI))} ry="19"
              fill={moonData.age > 14.75 ? 'var(--t2)' : 'var(--bg)'}/>
            <circle cx="22" cy="22" r="19" fill="none" stroke="var(--t2)" strokeWidth="0.5" strokeOpacity={0.2}/>
          </svg>
          <div className="flex-1">
            <MetricRow label="Phase" value={moonData.phase} />
            <MetricRow label="Illumination" value={`${(illum*100).toFixed(0)}%`} />
            <MetricRow label="Rise / Transit / Set" value={`${moonData.rise} / ${moonData.transit} / ${moonData.set}`} />
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Variant A: Scientific Observatory (default) ──────────────────────────────
function VariantA() {
  return (
    <div className="space-y-3 page-enter">
      <TimingWidget />
      <HoldoverWidget />
      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-5"><SunWidget /></div>
        <div className="col-span-3"><GNSSWidget /></div>
        <div className="col-span-4 space-y-3">
          <NetworkWidget />
          <DataPackWidget />
        </div>
      </div>
      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-4"><SolarWidget /></div>
        <div className="col-span-8"><MoonWidget /></div>
      </div>
    </div>
  );
}

// ─── Variant B: Dense Engineering Console ────────────────────────────────────
function VariantB() {
  const rows: [string, string, string?][] = [
    ['Δt current',          '+12.3 ns',    '± 4.1 ns'],
    ['Δt 24h RMS',          '18.7 ns',     undefined],
    ['Δf/f',                '−1.24×10⁻⁹', undefined],
    ['Light-dist. equiv.',  '3.69 m',      undefined],
    ['PPS state',           'LOCKED',      undefined],
    ['PPS avail. (30d)',    '99.71 %',     undefined],
    ['Lock streak',         '312h 24m',    undefined],
    ['Stratum',             '1',           undefined],
    ['Reference',           'GPS/PPS',     undefined],
    ['SVs used / in view',  `${satellites.filter(s=>s.state==='used').length} / ${satellites.length}`, undefined],
    ['Best C/N₀',           `${Math.max(...satellites.map(s=>s.cn0))} dB-Hz`, undefined],
    ['PDOP',                '1.4',         undefined],
    ['NTP clients',         '7',           undefined],
    ['Solar irrad.',        '612 W/m²',    'modeled'],
    ['Sunrise',             sunData.today.rise, undefined],
    ['Sunset',              sunData.today.set,  undefined],
    ['Daylight',            sunData.today.duration, undefined],
    ['Moon phase',          moonData.phase, undefined],
  ];
  return (
    <div className="page-enter">
      <div className="rounded-[2px] p-4" style={{ background:'var(--card)', border:'1px solid var(--border)', boxShadow:'inset 0 1px 0 rgba(255,255,255,0.04)' }}>
        <div className="mono text-[9px] mb-3 uppercase tracking-[0.15em]" style={{ color:'var(--t4)' }}>
          ATLAS-01 — Engineering Console — {new Date().toISOString().replace('T',' ').slice(0,-5)} UTC
        </div>
        <div className="grid grid-cols-2 gap-x-10">
          {rows.map(([k,v,s]) => (
            <div key={k} className="flex items-baseline justify-between py-[5px] row-sep">
              <span className="mono text-[10px]" style={{ color:'var(--t3)' }}>{k}</span>
              <div className="flex items-baseline gap-2">
                <span className="mono tabular text-[11px] font-medium" style={{ color:'var(--t1)' }}>{v}</span>
                {s && <span className="text-[9px]" style={{ color:'var(--t4)' }}>{s}</span>}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <div className="mono text-[9px] mb-1.5 uppercase tracking-[0.12em]" style={{ color:'var(--t3)' }}>Δt — last 1 hour</div>
          <OffsetChart data={offset1h} range="1h" />
        </div>
        <div className="mt-3 grid grid-cols-2 gap-6">
          <div>
            <div className="mono text-[9px] mb-1 uppercase tracking-[0.12em]" style={{ color:'var(--t4)' }}>PPS Loss Events (30d)</div>
            {[{d:'Sep 10',s:1387},{d:'Sep 13',s:161},{d:'Sep 15',s:58},{d:'Sep 19',s:72},{d:'Sep 22',s:34}].map(e=>(
              <div key={e.d} className="flex justify-between py-[4px] row-sep">
                <span className="mono text-[10px]" style={{ color:'var(--t3)' }}>{e.d}</span>
                <span className="mono tabular text-[10px]" style={{ color:'var(--warn-text)' }}>{e.s}s</span>
              </div>
            ))}
          </div>
          <div>
            <div className="mono text-[9px] mb-1 uppercase tracking-[0.12em]" style={{ color:'var(--t4)' }}>Sky Plot</div>
            <SkyPlot sats={satellites} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Variant C: Minimal Precision ─────────────────────────────────────────────
function VariantC() {
  return (
    <div className="page-enter" style={{ maxWidth:640, margin:'0 auto', paddingTop:'2rem' }}>
      <div className="text-center mb-10">
        <div className="mono text-[9px] uppercase tracking-[0.22em] mb-3" style={{ color:'var(--t4)' }}>Current time offset</div>
        <div className="flex items-baseline justify-center gap-3">
          <span className="mono tabular font-light" style={{ fontSize:72, lineHeight:1, color:'var(--live-bright)', letterSpacing:'-0.02em' }}>+12.3</span>
          <div className="flex flex-col items-start gap-1">
            <span className="mono text-2xl font-light" style={{ color:'var(--t2)' }}>ns</span>
            <span className="mono text-sm" style={{ color:'var(--t4)' }}>± 4.1</span>
          </div>
        </div>
        <div className="mono text-[10px] mt-2" style={{ color:'var(--t4)' }}>≡ 3.69 m · GPS/PPS LOCKED · Stratum 1</div>
      </div>

      <div className="mb-8">
        <OffsetChart data={offset1h} range="1h" />
        <div className="text-center mono text-[9px] mt-1" style={{ color:'var(--t4)' }}>Δt — last 60 minutes</div>
      </div>

      <div style={{ borderTop:'1px solid var(--border-dim)' }}>
        {[
          ['24 h RMS',             '18.7 ns'],
          ['PPS lock streak',      '312h 24m continuous'],
          ['PPS availability',     '99.71 %'],
          ['Fractional freq. offset','−1.24 × 10⁻⁹'],
          ['Satellites used / in view', `${satellites.filter(s=>s.state==='used').length} / ${satellites.length}`],
          ['NTP stratum',          '1'],
          ['NTP clients',          '7'],
          ['Sunrise / Sunset',     `${sunData.today.rise} / ${sunData.today.set}`],
          ['Moon',                 `${moonData.phase} · ${(moonData.illumination*100).toFixed(0)}% illuminated`],
        ].map(([k,v]) => (
          <div key={k} className="flex justify-between py-2.5 row-sep">
            <span className="text-[12px]" style={{ color:'var(--t3)' }}>{k}</span>
            <span className="mono tabular text-[12px]" style={{ color:'var(--t1)' }}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Overview page ────────────────────────────────────────────────────────────
const VARIANTS = [
  { key:'A', label:'A — Scientific Observatory' },
  { key:'B', label:'B — Engineering Console' },
  { key:'C', label:'C — Minimal Precision' },
];

export default function Overview() {
  const [variant, setVariant] = useState('A');
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-[13px] font-semibold" style={{ color:'var(--t1)' }}>Overview</h1>
          <p className="text-[10px] mt-0.5" style={{ color:'var(--t3)' }}>Station at-a-glance · three display variants</p>
        </div>
        <div className="flex gap-1">
          {VARIANTS.map(v => (
            <button key={v.key} onClick={() => setVariant(v.key)}
              className="px-3 py-[5px] text-[10px] mono rounded-[2px] transition-colors"
              style={variant===v.key
                ? { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }
                : { border:'1px solid var(--border)', color:'var(--t3)' }}>
              {v.label.split(' — ')[0]}
            </button>
          ))}
        </div>
      </div>

      {variant==='A' && <VariantA />}
      {variant==='B' && <VariantB />}
      {variant==='C' && <VariantC />}
    </div>
  );
}
