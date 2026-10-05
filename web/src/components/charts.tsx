import {
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  ScatterChart, Scatter, BarChart, Bar, Cell, ErrorBar,
  ResponsiveContainer,
} from 'recharts';
import { decadeTicks, fmtDeviation, fmtInterval, fmtTau, valueExtent, type StabilityMetric, type StabilityRow } from '../lib/stability';

// Shared tick style
const TICK = { fontSize: 9, fontFamily: 'JetBrains Mono', fill: 'var(--t3)' } as const;
const GRID = 'rgba(255,255,255,0.05)';
const AXIS = 'var(--border)';

function ChartTip({ active, payload, label, unit='ns' }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tip">
      <div style={{ color:'var(--t3)', marginBottom:2 }}>{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} style={{ color: p.color ?? 'var(--live)' }}>
          {typeof p.value === 'number' ? p.value.toFixed(1) : p.value} <span style={{ color:'var(--t3)' }}>{unit}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Time-offset area chart ───────────────────────────────────────────────────
export function OffsetChart({ data, range, unit='ns' }: { data: any[]; range: string; unit?: string }) {
  const fmtX = (ts: number) => {
    const d = new Date(ts);
    if (range === '1h' || range === '24h')
      return d.toLocaleTimeString('en-US', { hour:'2-digit', minute:'2-digit', hour12:false });
    return d.toLocaleDateString('en-US', { month:'short', day:'numeric' });
  };

  return (
    <ResponsiveContainer width="100%" height={160}>
      <AreaChart data={data} margin={{ top:8, right:4, left:0, bottom:0 }}>
        <defs>
          <linearGradient id="dtFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor="var(--live)" stopOpacity={0.18}/>
            <stop offset="100%" stopColor="var(--live)" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false}/>
        <XAxis dataKey="ts" tickFormatter={fmtX} tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} interval="preserveStartEnd"/>
        <YAxis tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} width={34} tickFormatter={(v:number)=>`${v.toFixed(0)}`}/>
        <Tooltip content={<ChartTip unit={unit}/>}/>
        <ReferenceLine y={0} stroke={AXIS} strokeDasharray="2 4" strokeOpacity={0.6}/>
        <Area type="monotone" dataKey="dt" stroke="var(--live)" strokeWidth={1.5} fill="url(#dtFill)" dot={false} activeDot={{ r:3, fill:'var(--live)', strokeWidth:0 }}/>
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ─── PPS availability timeline (SVG) ─────────────────────────────────────────
export function PPSTimeline({ events }: { events: { date: string; durationS: number }[] }) {
  const totalS = 86400;
  const outages = events.slice(0,4).map((e, i) => ({
    xPct: (i*8+2)/24*100,
    wPct: Math.max(0.3, e.durationS/totalS*100),
  }));
  return (
    <div className="w-full">
      <svg width="100%" height="24" viewBox="0 0 100 24" preserveAspectRatio="none">
        <rect x="0" y="6" width="100" height="10" fill="var(--good-bg)" rx="0.5"/>
        {outages.map((o,i) => (
          <rect key={i} x={o.xPct} y="6" width={o.wPct} height="10" fill="var(--err-text)" fillOpacity={0.45} rx="0.3"/>
        ))}
        {['00:00','06:00','12:00','18:00','24:00'].map((t,i)=>(
          <text key={t} x={i*25} y="23" fontSize="5" fill="var(--t4)" fontFamily="JetBrains Mono" textAnchor={i===4?"end":i===0?"start":"middle"}>{t}</text>
        ))}
      </svg>
      <div className="flex gap-4 mt-1">
        <span className="flex items-center gap-1 text-[9px] mono" style={{ color:'var(--t4)' }}>
          <span className="w-2.5 h-1 inline-block rounded-[1px]" style={{ background:'var(--good-bg)', border:'1px solid var(--good-border)' }}/>PPS LOCKED
        </span>
        <span className="flex items-center gap-1 text-[9px] mono" style={{ color:'var(--t4)' }}>
          <span className="w-2.5 h-1 inline-block rounded-[1px]" style={{ background:'var(--err-bg)', border:'1px solid var(--err-border)' }}/>OUTAGE
        </span>
      </div>
    </div>
  );
}

// ─── Holdover scatter ─────────────────────────────────────────────────────────
export function HoldoverScatter({ data }: { data: { durationS: number; errorNsOnRecovery: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={140}>
      <ScatterChart margin={{ top:8, right:4, left:0, bottom:16 }}>
        <CartesianGrid strokeDasharray="2 4" stroke={GRID}/>
        <XAxis dataKey="durationS" name="Duration" unit="s" tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }}
          label={{ value:'Outage duration (s)', position:'insideBottom', offset:-8, fontSize:8, fill:'var(--t3)', fontFamily:'JetBrains Mono' }}/>
        <YAxis dataKey="errorNsOnRecovery" name="Error" tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} width={36}
          label={{ value:'Error (ns)', angle:-90, position:'insideLeft', offset:12, fontSize:8, fill:'var(--t3)', fontFamily:'JetBrains Mono' }}/>
        <Tooltip cursor={{ stroke:'var(--border-em)' }} content={({ active, payload }) => {
          if (!active || !payload?.length) return null;
          const d = payload[0]?.payload;
          return (
            <div className="chart-tip">
              <div style={{ color:'var(--t3)' }}>{d.durationS}s outage</div>
              <div style={{ color:'var(--live)' }}>+{d.errorNsOnRecovery} ns recovered error</div>
            </div>
          );
        }}/>
        <Scatter data={data} fill="var(--live)" fillOpacity={0.7} r={4}/>
      </ScatterChart>
    </ResponsiveContainer>
  );
}

// ─── GNSS Sky Plot (SVG polar) ────────────────────────────────────────────────
const SYSCOLOR: Record<string,string> = {
  GPS:'var(--live)', GLONASS:'var(--warn-text)', GALILEO:'var(--mod-text)', BEIDOU:'var(--good-text)',
};
export function SkyPlot({ sats, hiddenNote }: { sats: { sys:string; svid:string; az:number; el:number; cn0:number; state:string }[]; hiddenNote?: string }) {
  const sz = 214, cx = sz/2, cy = sz/2, r = sz/2 - 18;
  const toXY = (az: number, el: number) => {
    const p = (1 - el/90) * r;
    const a = (az - 90) * Math.PI / 180;
    return { x: cx + p*Math.cos(a), y: cy + p*Math.sin(a) };
  };
  return (
    <svg width={sz} height={sz} viewBox={`0 0 ${sz} ${sz}`} style={{ maxWidth:'100%' }}>
      {/* Rings */}
      {[0,30,60,90].map(el => (
        <circle key={el} cx={cx} cy={cy} r={(1-el/90)*r}
          fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={el===0?1:0.5}/>
      ))}
      {/* Azimuth spokes */}
      {[0,45,90,135].map(a => {
        const rad = (a-90)*Math.PI/180;
        return <line key={a} x1={cx} y1={cy} x2={cx+r*Math.cos(rad)} y2={cy+r*Math.sin(rad)}
          stroke="rgba(255,255,255,0.05)" strokeWidth={0.5}/>;
      })}
      {/* Cardinals */}
      {[
        { l:'N', x:cx, y:11, a:'middle' },
        { l:'E', x:sz-8, y:cy+3, a:'end' },
        { l:'S', x:cx, y:sz-5, a:'middle' },
        { l:'W', x:9, y:cy+3, a:'start' },
      ].map(c => (
        <text key={c.l} x={c.x} y={c.y} textAnchor={c.a as any} fontSize="8" fill="var(--t4)" fontFamily="JetBrains Mono">{c.l}</text>
      ))}
      {/* Elevation labels */}
      <text x={cx+2} y={cy-r/3+2} fontSize="7" fill="var(--t4)" fontFamily="JetBrains Mono">60°</text>
      <text x={cx+2} y={cy-r*2/3+2} fontSize="7" fill="var(--t4)" fontFamily="JetBrains Mono">30°</text>
      {hiddenNote && <text x={cx} y={cy+3} textAnchor="middle" fontSize="7" fill="var(--t3)" fontFamily="JetBrains Mono">{hiddenNote}</text>}
      {/* Satellites */}
      {sats.map(s => {
        const { x, y } = toXY(s.az, s.el);
        const col = SYSCOLOR[s.sys] || 'var(--t2)';
        const used = s.state === 'used';
        return (
          <g key={s.sys + s.svid} opacity={used ? 1 : 0.35}>
            <circle cx={x} cy={y} r={used?5:4} fill={col} fillOpacity={0.2} stroke={col} strokeWidth={used?1:0.75}/>
            <text x={x} y={y-7} textAnchor="middle" fontSize="6.5" fill={col} fontFamily="JetBrains Mono">{s.svid}</text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Outage bar chart ─────────────────────────────────────────────────────────
export function OutageBarChart({ data }: { data: { date: string; durationS: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={96}>
      <BarChart data={data} margin={{ top:4, right:4, left:0, bottom:4 }}>
        <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false}/>
        <XAxis dataKey="date" tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }}/>
        <YAxis tick={TICK} tickLine={false} axisLine={false} width={30}/>
        <Tooltip content={({ active, payload }) => {
          if (!active || !payload?.length) return null;
          return (
            <div className="chart-tip">
              <div style={{ color:'var(--t3)' }}>{payload[0]?.payload.date}</div>
              <div style={{ color:'var(--warn-text)' }}>{payload[0]?.value}s</div>
            </div>
          );
        }}/>
        <Bar dataKey="durationS" radius={[2,2,0,0]}>
          {data.map((_,i) => <Cell key={i} fill="var(--warn-text)" fillOpacity={0.5}/>)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Solar irradiance curve ───────────────────────────────────────────────────
export function SolarCurve({ data }: { data: { h: number; w: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={96}>
      <AreaChart data={data} margin={{ top:4, right:4, left:0, bottom:0 }}>
        <defs>
          <linearGradient id="solFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor="var(--warn-text)" stopOpacity={0.25}/>
            <stop offset="100%" stopColor="var(--warn-text)" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false}/>
        <XAxis dataKey="h" tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} tickFormatter={(v:number)=>`${v}h`}/>
        <YAxis tick={TICK} tickLine={false} axisLine={false} width={34} tickFormatter={(v:number)=>`${v}W`}/>
        <Tooltip content={<ChartTip unit="W/m²"/>}/>
        <Area type="monotone" dataKey="w" stroke="var(--warn-text)" strokeWidth={1.5} fill="url(#solFill)" dot={false}/>
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ─── Stability (ADEV / MDEV / TDEV), log–log ─────────────────────────────────
const SUP: Record<string, string> = { '-':'⁻','0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹' };
const pow10 = (v: number) => `10${String(Math.round(Math.log10(v))).split('').map(c => SUP[c]).join('')}`;

function StabilityTip({ active, payload, metric }: any) {
  if (!active || !payload?.length) return null;
  const r: StabilityRow = payload[0].payload;
  const interval = metric === 'adev' ? fmtInterval(r.point) : null;
  return (
    <div className="chart-tip">
      <div style={{ color:'var(--t3)', marginBottom:2 }}>τ = {fmtTau(r.tau)}</div>
      <div style={{ color:'var(--live)' }}>{fmtDeviation(r.v, metric)}</div>
      {interval && <div style={{ color:'var(--t3)' }}>{interval}</div>}
    </div>
  );
}

export function StabilityChart({ rows, metric }: { rows: StabilityRow[]; metric: StabilityMetric }) {
  const extent = valueExtent(rows);
  if (!extent) return null;
  const yTicks = decadeTicks(extent[0], extent[1]);
  const xTicks = decadeTicks(rows[0].tau, rows[rows.length - 1].tau);
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={rows} margin={{ top:8, right:12, left:0, bottom:0 }}>
        <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false}/>
        <XAxis dataKey="tau" type="number" scale="log" domain={[xTicks[0], xTicks[xTicks.length - 1]]} ticks={xTicks}
               tickFormatter={fmtTau} tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} allowDataOverflow/>
        <YAxis type="number" scale="log" domain={[yTicks[0], yTicks[yTicks.length - 1]]} ticks={yTicks}
               tickFormatter={metric === 'tdev' ? (v: number) => fmtDeviation(v, 'tdev') ?? '' : pow10}
               tick={TICK} tickLine={false} axisLine={false} width={metric === 'tdev' ? 46 : 34} allowDataOverflow/>
        <Tooltip content={<StabilityTip metric={metric}/>}/>
        <Line type="linear" dataKey="v" stroke="var(--live)" strokeWidth={1.5} isAnimationActive={false}
              dot={{ r:2, fill:'var(--live)', strokeWidth:0 }} activeDot={{ r:3, fill:'var(--live)', strokeWidth:0 }}>
          {metric === 'adev' && <ErrorBar dataKey="err" direction="y" width={3} stroke="var(--t3)" strokeWidth={1}/>}
        </Line>
      </LineChart>
    </ResponsiveContainer>
  );
}
