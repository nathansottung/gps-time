import {
  AreaChart, Area, LineChart, Line, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  ScatterChart, Scatter, ZAxis, BarChart, Bar, Cell, ErrorBar,
  ResponsiveContainer,
} from 'recharts';
import { decadeTicks, fmtDeviation, fmtInterval, fmtTau, valueExtent, type StabilityMetric, type StabilityRow } from '../lib/stability';
import { fmtSeconds as fmtSym, symDomain, symexp, symTicks, type OffsetRow } from '../lib/offset';
import { fmtDurationTick, fmtTime, linearTicks, logTicks, positiveOnly, symAxis, symlog, symThreshold, symTimeLabel, UNIT_S } from '../lib/timeaxis';
import { fmtSci } from '../lib/units';
import { useChartScale } from './prefs';
import type { ChartId } from '../lib/prefs';

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

// ─── Value-axis scale toggle (remembered per browser, lib/prefs.ts) ──────────
/** LIN | LOG for one chart's value axis. Every view of that chart follows the choice. */
export function ScaleToggle({ chart }: { chart: ChartId }) {
  const [scale, setScale] = useChartScale(chart);
  return (
    <div className="flex gap-1" role="group" aria-label="Value axis scale">
      {(['linear', 'log'] as const).map(v => (
        <button key={v} onClick={() => setScale(v)} aria-pressed={scale === v}
          title={v === 'linear' ? 'Linear value axis' : 'Logarithmic value axis (symmetric around zero for signed values)'}
          className="px-2 py-[3px] text-[9px] mono rounded-[2px] uppercase"
          style={scale === v
            ? { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }
            : { border:'1px solid var(--border)', color:'var(--t3)' }}>
          {v === 'linear' ? 'Lin' : 'Log'}
        </button>
      ))}
    </div>
  );
}

// ─── Time series (offsets, delays) with a linear or symmetric-log value axis ──
/** A series in a unit ('ns', 'µs', 'ms', 's'); drawn in seconds, every tick labelled with its own unit. */
export function TimeSeriesChart({ series, range, chart, height = 160 }: {
  series: { unit: string; data: { ts: number; dt: number }[] }; range: string; chart: ChartId; height?: number;
}) {
  const [scale] = useChartScale(chart);
  const k = UNIT_S[series.unit] ?? 1;
  const secs = series.data.map(d => d.dt * k);
  const lin = symThreshold(secs);
  const log = scale === 'log';
  const rows = series.data.map((d, i) => ({ ts: d.ts, s: secs[i], y: log ? symlog(secs[i], lin) : secs[i] }));
  const lt = log ? [] : linearTicks(Math.min(0, ...secs), Math.max(0, ...secs));
  const ax = log ? symAxis(secs, lin) : { domain: [lt[0], lt[lt.length - 1]] as [number, number], ticks: lt };
  const fmtX = (ts: number) => {
    const d = new Date(ts);
    return range === '1h' || range === '24h'
      ? d.toLocaleTimeString('en-GB', { hour:'2-digit', minute:'2-digit', hour12:false })
      : d.toLocaleDateString('en-GB', { month:'short', day:'numeric' });
  };
  const gid = `ts-fill-${chart}`;
  const xTicks = rows.length > 1 ? [0, 1, 2, 3, 4].map(i => rows[0].ts + (rows[rows.length - 1].ts - rows[0].ts) * i / 4) : [];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows} margin={{ top:8, right:4, left:0, bottom:0 }}>
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor="var(--live)" stopOpacity={0.18}/>
            <stop offset="100%" stopColor="var(--live)" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false}/>
        <XAxis dataKey="ts" type="number" scale="time" domain={['dataMin', 'dataMax']} ticks={xTicks} interval="preserveStartEnd" minTickGap={8}
          tickFormatter={fmtX} tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }}/>
        <YAxis domain={ax.domain} ticks={ax.ticks} allowDataOverflow tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} width={52}
          tickFormatter={(v: number) => log ? symTimeLabel(v, lin) : fmtTime(v)}/>
        <Tooltip content={({ active, payload }: any) => {
          if (!active || !payload?.length) return null;
          const r = payload[0].payload;
          return (
            <div className="chart-tip">
              <div style={{ color:'var(--t3)', marginBottom:2 }}>{fmtX(r.ts)}</div>
              <div style={{ color:'var(--live)' }}>{fmtTime(r.s)}</div>
            </div>
          );
        }}/>
        <ReferenceLine y={0} stroke={AXIS} strokeDasharray="2 4" strokeOpacity={0.6}/>
        <Area type="monotone" dataKey="y" baseValue={0} stroke="var(--live)" strokeWidth={1.5} fill={`url(#${gid})`} dot={false} isAnimationActive={false} activeDot={{ r:3, fill:'var(--live)', strokeWidth:0 }}/>
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ─── Linear area chart for other quantities (e.g. request rates) ──────────────
export function RateChart({ data, range, unit='ns' }: { data: any[]; range: string; unit?: string }) {
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
        <XAxis minTickGap={8} dataKey="ts" tickFormatter={fmtX} tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} interval="preserveStartEnd"/>
        <YAxis tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} width={34} tickFormatter={(v:number)=>`${v.toFixed(0)}`}/>
        <Tooltip content={<ChartTip unit={unit}/>}/>
        <ReferenceLine y={0} stroke={AXIS} strokeDasharray="2 4" strokeOpacity={0.6}/>
        <Area type="monotone" dataKey="dt" stroke="var(--live)" strokeWidth={1.5} fill="url(#dtFill)" dot={false} activeDot={{ r:3, fill:'var(--live)', strokeWidth:0 }}/>
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ─── Offset history with chrony's offset-SD band and max-error bound (lib/offset.ts) ──────────
function OffsetHistoryTip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const r: OffsetRow = payload[0].payload;
  return (
    <div className="chart-tip">
      <div style={{ color:'var(--t3)', marginBottom:2 }}>{new Date(r.ts).toLocaleString('en-GB', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false })}</div>
      <div style={{ color:'var(--live)' }}>offset {fmtSym(r.offset)}</div>
      <div style={{ color:'var(--t2)' }}>offset SD {r.sd === null ? '—' : fmtSym(r.sd)}</div>
      <div style={{ color:'var(--t3)' }}>max error {r.maxError === null ? '—' : fmtSym(r.maxError)}</div>
    </div>
  );
}

/** Offset chart: line = chrony's offset, band = ± its offset SD, dashed = ± max error.
 *  Log: the symmetric-log rows from lib/offset.ts (linear within ±1 µs). Linear: the same values in seconds. */
export function OffsetHistoryChart({ rows: symRows, range, showMaxErr }: { rows: OffsetRow[]; range: string; showMaxErr: boolean }) {
  const [scale] = useChartScale('offset-history');
  const log = scale === 'log';
  const rows: OffsetRow[] = log ? symRows : symRows.map(r => ({
    ...r, y: r.offset,
    band: r.sd === null || r.sd < 0 ? null : [r.offset - r.sd, r.offset + r.sd],
    maxErr: r.maxError === null || r.maxError < 0 ? null : [-r.maxError, r.maxError],
  }));
  const linVals = rows.flatMap(r => [r.y, ...(r.band ?? []), ...(showMaxErr && r.maxErr ? r.maxErr : [])]);
  const lt = log ? [] : linearTicks(Math.min(0, ...linVals), Math.max(0, ...linVals));
  const dom: [number, number] = log ? symDomain(rows, showMaxErr) : [lt[0], lt[lt.length - 1]];
  const xTicks = rows.length > 1 ? [0, 1, 2, 3, 4].map(i => rows[0].ts + (rows[rows.length - 1].ts - rows[0].ts) * i / 4) : [];
  const fmtX = (ts: number) => {
    const d = new Date(ts);
    return range === '1h' || range === '24h'
      ? d.toLocaleTimeString('en-GB', { hour:'2-digit', minute:'2-digit', hour12:false })
      : d.toLocaleDateString('en-GB', { month:'short', day:'numeric' });
  };
  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={rows} margin={{ top:8, right:4, left:0, bottom:0 }}>
        <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false}/>
        <XAxis interval="preserveStartEnd" minTickGap={8} dataKey="ts" type="number" scale="time" domain={['dataMin', 'dataMax']} ticks={xTicks} tickFormatter={fmtX} tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }}/>
        <YAxis domain={dom} ticks={log ? symTicks(dom) : lt} allowDataOverflow tickFormatter={(v: number) => log ? fmtSym(symexp(v)) : fmtTime(v)}
          tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} width={52}/>
        <Tooltip content={<OffsetHistoryTip/>}/>
        <ReferenceLine y={0} stroke={AXIS} strokeOpacity={0.8}/>
        <Area dataKey="band" stroke="none" fill="var(--good-text)" fillOpacity={0.16} connectNulls={false} isAnimationActive={false} activeDot={false}/>
        {showMaxErr && <Line dataKey={(r: OffsetRow) => r.maxErr?.[1] ?? null} stroke="var(--t3)" strokeDasharray="4 3" strokeWidth={1} dot={false} connectNulls={false} isAnimationActive={false} activeDot={false}/>}
        {showMaxErr && <Line dataKey={(r: OffsetRow) => r.maxErr?.[0] ?? null} stroke="var(--t3)" strokeDasharray="4 3" strokeWidth={1} dot={false} connectNulls={false} isAnimationActive={false} activeDot={false}/>}
        <Line dataKey="y" stroke="var(--live)" strokeWidth={1.5} dot={false} isAnimationActive={false} activeDot={{ r:3, fill:'var(--live)', strokeWidth:0 }}/>
      </ComposedChart>
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
      {/* The bar stretches to the width (preserveAspectRatio none); its hour labels are HTML so the
          text keeps its shape at every width. */}
      <svg width="100%" height="12" viewBox="0 0 100 12" preserveAspectRatio="none" aria-hidden="true">
        <rect x="0" y="1" width="100" height="10" fill="var(--good-bg)" rx="0.5"/>
        {outages.map((o,i) => (
          <rect key={i} x={o.xPct} y="1" width={o.wPct} height="10" fill="var(--err-text)" fillOpacity={0.45} rx="0.3"/>
        ))}
      </svg>
      <div className="flex justify-between text-[9px] mono mt-0.5" style={{ color:'var(--t3)' }}>
        {['00:00','06:00','12:00','18:00','24:00'].map(t => <span key={t}>{t}</span>)}
      </div>
      <div className="flex gap-4 mt-1">
        <span className="flex items-center gap-1 text-[9px] mono" style={{ color:'var(--t3)' }}>
          <span className="w-2.5 h-1 inline-block rounded-[1px]" style={{ background:'var(--good-bg)', border:'1px solid var(--good-border)' }}/>PPS LOCKED
        </span>
        <span className="flex items-center gap-1 text-[9px] mono" style={{ color:'var(--t3)' }}>
          <span className="w-2.5 h-1 inline-block rounded-[1px]" style={{ background:'var(--err-bg)', border:'1px solid var(--err-border)' }}/>OUTAGE
        </span>
      </div>
    </div>
  );
}

// ─── Holdover scatter ─────────────────────────────────────────────────────────
export function HoldoverScatter({ data }: { data: { durationS: number; errorNsOnRecovery: number }[] }) {
  const [scale] = useChartScale('holdover');
  const log = scale === 'log';
  const all = data.map(d => ({ ...d, err: d.errorNsOnRecovery * 1e-9 }));
  const rows = log ? positiveOnly(all, r => r.err).rows : all;
  const ticks = log ? logTicks(rows.map(r => r.err)) : linearTicks(0, Math.max(0, ...rows.map(r => r.err)));
  const dTicks = logTicks(rows.map(r => r.durationS));
  return (
    <ResponsiveContainer width="100%" height={140}>
      <ScatterChart margin={{ top:8, right:4, left:0, bottom:16 }}>
        <CartesianGrid strokeDasharray="2 4" stroke={GRID}/>
        {/* A numeric axis (a category axis put the outages in list order and dropped points at narrow
            widths); durations span decades, so it is logarithmic. */}
        <XAxis dataKey="durationS" name="Duration" type="number" scale="log" domain={[dTicks[0], dTicks[dTicks.length - 1]]}
          ticks={dTicks} allowDataOverflow tickFormatter={fmtDurationTick} tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }}
          label={{ value:'Outage duration', position:'insideBottom', offset:-8, fontSize:8, fill:'var(--t3)', fontFamily:'JetBrains Mono' }}/>
        <YAxis dataKey="err" name="Error" type="number" scale={log ? 'log' : 'linear'} domain={[ticks[0], ticks[ticks.length - 1]]} ticks={ticks}
          allowDataOverflow tickFormatter={fmtTime} tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} width={52}/>
        <Tooltip cursor={{ stroke:'var(--border-em)' }} content={({ active, payload }) => {
          if (!active || !payload?.length) return null;
          const d = payload[0]?.payload;
          return (
            <div className="chart-tip">
              <div style={{ color:'var(--t3)' }}>{d.durationS}s outage</div>
              <div style={{ color:'var(--live)' }}>+{fmtTime(d.err)} error at reacquisition</div>
            </div>
          );
        }}/>
        <ZAxis range={[50, 50]}/>
        <Scatter data={rows} fill="var(--live)" fillOpacity={0.7}/>
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
    <svg width={sz} height={sz} viewBox={`0 0 ${sz} ${sz}`} style={{ maxWidth:'100%', height:'auto' }} data-layout-ok="plot">
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
        <text key={c.l} x={c.x} y={c.y} textAnchor={c.a as any} fontSize="8" fill="var(--t3)" fontFamily="JetBrains Mono">{c.l}</text>
      ))}
      {/* Elevation labels */}
      <text x={cx+2} y={cy-r/3+2} fontSize="7" fill="var(--t3)" fontFamily="JetBrains Mono">60°</text>
      <text x={cx+2} y={cy-r*2/3+2} fontSize="7" fill="var(--t3)" fontFamily="JetBrains Mono">30°</text>
      {hiddenNote && <text x={cx} y={cy+3} textAnchor="middle" fontSize="7" fill="var(--t3)" fontFamily="JetBrains Mono">{hiddenNote}</text>}
      {/* Satellites */}
      {sats.map(s => {
        const { x, y } = toXY(s.az, s.el);
        const col = SYSCOLOR[s.sys] || 'var(--t2)';
        const used = s.state === 'used';
        return (
          <g key={s.sys + s.svid}>
            {/* tracked-only: a dimmer, smaller circle; the label stays legible (4.5:1) either way */}
            <circle cx={x} cy={y} r={used?5:4} fill={col} fillOpacity={used ? 0.2 : 0.07} stroke={col} strokeWidth={used?1:0.75} strokeOpacity={used ? 1 : 0.35}/>
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
        <XAxis interval="preserveStartEnd" minTickGap={8} dataKey="date" tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }}/>
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
        <XAxis interval="preserveStartEnd" minTickGap={8} dataKey="h" tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} tickFormatter={(v:number)=>`${v}h`}/>
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
  const [scale] = useChartScale('stability');
  const log = scale === 'log';
  const extent = valueExtent(rows);
  if (!extent) return null;
  // τ stays logarithmic; the toggle sets the value axis. TDEV is a time (ns/µs/ms); ADEV and MDEV are ×10⁻ⁿ.
  const yTicks = log ? decadeTicks(extent[0], extent[1]) : linearTicks(0, extent[1]);
  const yLabel = (v: number) => metric === 'tdev' ? (log ? fmtDeviation(v, 'tdev') ?? '' : fmtTime(v)) : log ? pow10(v) : (v === 0 ? '0' : fmtSci(v, 2));
  const xTicks = decadeTicks(rows[0].tau, rows[rows.length - 1].tau);
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={rows} margin={{ top:8, right:12, left:0, bottom:0 }}>
        <CartesianGrid strokeDasharray="2 4" stroke={GRID} vertical={false}/>
        <XAxis interval="preserveStartEnd" minTickGap={8} dataKey="tau" type="number" scale="log" domain={[xTicks[0], xTicks[xTicks.length - 1]]} ticks={xTicks}
               tickFormatter={fmtTau} tick={TICK} tickLine={false} axisLine={{ stroke:AXIS }} allowDataOverflow/>
        <YAxis type="number" scale={log ? 'log' : 'linear'} domain={[yTicks[0], yTicks[yTicks.length - 1]]} ticks={yTicks}
               tickFormatter={yLabel}
               tick={TICK} tickLine={false} axisLine={false} width={metric === 'tdev' || !log ? 64 : 34} allowDataOverflow/>
        <Tooltip content={<StabilityTip metric={metric}/>}/>
        <Line type="linear" dataKey="v" stroke="var(--live)" strokeWidth={1.5} isAnimationActive={false}
              dot={{ r:2, fill:'var(--live)', strokeWidth:0 }} activeDot={{ r:3, fill:'var(--live)', strokeWidth:0 }}>
          {metric === 'adev' && <ErrorBar dataKey="err" direction="y" width={3} stroke="var(--t3)" strokeWidth={1}/>}
        </Line>
      </LineChart>
    </ResponsiveContainer>
  );
}
