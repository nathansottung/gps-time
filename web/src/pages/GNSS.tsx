import { useState } from 'react';
import { Card, CardHeader, CardBody, MetricRow, StatusBadge, ELI5, Tabs, ProvenanceTag, SectionHeader } from '../components/ui';
import { SkyPlot } from '../components/charts';
import { satellites, STATION_LAT, STATION_LON, STATION_ALT_ELLIP, STATION_ALT_ORTHO, STATION_GEOID_N } from '../data/demo';

const SYSCOLORS: Record<string,string> = {
  GPS:'var(--live)', GLONASS:'var(--warn-text)', GALILEO:'var(--mod-text)', BEIDOU:'var(--good-text)',
};
const SYSDOT: Record<string,string> = {
  GPS:'bg-cyan-400', GLONASS:'bg-amber-400', GALILEO:'bg-purple-400', BEIDOU:'bg-green-400',
};

// Simulated obstruction heatmap cells (azimuth × elevation buckets)
const obstructionCells = Array.from({ length: 36 }, (_, ai) =>
  Array.from({ length: 6 }, (_, ei) => ({
    az: ai * 10,
    el: ei * 15,
    // Western sky mostly obstructed
    quality: ai >= 24 && ai <= 32 && ei <= 2 ? 0.15 : 0.75 + Math.random() * 0.2,
  }))
).flat();

function ObstructionHeatmap() {
  const size = 200;
  const cx = size/2, cy = size/2, r = size/2 - 14;
  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {obstructionCells.map(cell => {
          const azR = (cell.az - 90) * Math.PI / 180;
          const elR1 = (1 - cell.el/90) * r;
          const elR2 = (1 - (cell.el+15)/90) * r;
          const azR2 = ((cell.az + 10) - 90) * Math.PI / 180;
          const x1 = cx + elR1*Math.cos(azR), y1 = cy + elR1*Math.sin(azR);
          const x2 = cx + elR1*Math.cos(azR2), y2 = cy + elR1*Math.sin(azR2);
          const x3 = cx + elR2*Math.cos(azR2), y3 = cy + elR2*Math.sin(azR2);
          const x4 = cx + elR2*Math.cos(azR), y4 = cy + elR2*Math.sin(azR);
          const q = cell.quality;
          const fill = q > 0.6 ? `rgba(34,211,238,${q*0.4})` : `rgba(248,113,113,${(1-q)*0.6})`;
          return <polygon key={`${cell.az}-${cell.el}`} points={`${x1},${y1} ${x2},${y2} ${x3},${y3} ${x4},${y4}`} fill={fill} stroke="none"/>;
        })}
        {[0,30,60,90].map(el => (
          <circle key={el} cx={cx} cy={cy} r={(1-el/90)*r} fill="none" stroke="#1a2040" strokeWidth={0.5}/>
        ))}
        <text x={cx} y={9}  textAnchor="middle" fontSize="8" fill="#5a6480" fontFamily="JetBrains Mono">N</text>
        <text x={size-5} y={cy+3} textAnchor="end" fontSize="8" fill="#5a6480" fontFamily="JetBrains Mono">E</text>
        <text x={cx} y={size-3} textAnchor="middle" fontSize="8" fill="#5a6480" fontFamily="JetBrains Mono">S</text>
        <text x={7} y={cy+3} fontSize="8" fill="#5a6480" fontFamily="JetBrains Mono">W</text>
      </svg>
      <div className="flex gap-4 mt-1 text-[9px] mono" style={{ color:'var(--t3)' }}>
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-cyan-400/40 inline-block rounded-sm"/>Open sky</span>
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-red-400/50 inline-block rounded-sm"/>Obstructed</span>
      </div>
    </div>
  );
}

// Calibration section
function CalibrationPanel() {
  return (
    <Card>
      <CardHeader title="Antenna & Calibration" />
      <CardBody>
        <div className="grid grid-cols-2 gap-x-6">
          <div>
            <MetricRow label="Antenna model" value="u-blox ANN-MB-00" />
            <MetricRow label="Cable type" value="LMR-400" />
            <MetricRow label="Cable length" value="4.2 m" />
            <MetricRow label="Cable delay (est.)" value="14.8 ns" provenance="calculated" />
          </div>
          <div>
            <MetricRow label="Receiver model" value="u-blox ZED-F9T" />
            <MetricRow label="Receiver delay" value="~10 ns" provenance="inferred" />
            <MetricRow label="PPS user delay" value="0 ns" />
            <MetricRow label="Calibration state" value="PARTIAL" />
          </div>
        </div>
        <div className="mt-3 p-2 bg-amber-400/5 border border-amber-400/15 rounded-sm text-[10px] text-amber-400/80">
          Receiver internal delay has not been independently calibrated. Antenna cable correction applied.
        </div>
      </CardBody>
    </Card>
  );
}

export default function GNSS() {
  const [tab, setTab] = useState('Satellites');
  const used    = satellites.filter(s => s.state === 'used');
  const tracked = satellites.filter(s => s.state === 'tracked');

  return (
    <div className="space-y-4 page-enter">
      <div className="flex items-baseline justify-between">
        <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>GNSS & Site</h1>
        <div className="flex gap-2">
          <StatusBadge variant="good" label="3D FIXED" />
          <StatusBadge variant="info" label={`${used.length} SVs USED`} dot={false} />
        </div>
      </div>

      <Tabs tabs={['Satellites','Sky Plot','Sky Obstruction','Position','Geodesy','Calibration']} active={tab} onChange={setTab} />

      {tab === 'Satellites' && (
        <Card>
          <CardHeader title="Satellite Table" badge={<ProvenanceTag type="observed" />} />
          <CardBody className="p-0">
            <table className="w-full text-[11px]">
              <thead>
                <tr style={{ borderBottom:'1px solid var(--border)' }}>
                  {['System','SVID','Az °','El °','C/N₀ dB-Hz','State','Signal'].map(h => (
                    <th key={h} className="text-left px-4 py-2 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {satellites.map(s => (
                  <tr key={s.svid} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                    <td className="px-4 py-2">
                      <span className="font-mono text-[10px]" style={{ color: SYSCOLORS[s.sys] || 'var(--t2)' }}>{s.sys}</span>
                    </td>
                    <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}>{s.svid}</td>
                    <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>{s.az}</td>
                    <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>{s.el}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 rounded-full overflow-hidden max-w-[60px]" style={{ background:'var(--bg)' }}>
                          <div className={`h-full rounded-full ${s.cn0>44?'bg-green-400/70':s.cn0>35?'bg-cyan-400/70':'bg-amber-400/70'}`}
                            style={{ width:`${(s.cn0/55)*100}%`}}/>
                        </div>
                        <span className="mono tabular" style={{ color:'var(--t1)' }}>{s.cn0}</span>
                      </div>
                    </td>
                    <td className="px-4 py-2">
                      {s.state === 'used'    && <StatusBadge variant="good" label="USED" dot={false} className="text-[9px]" />}
                      {s.state === 'tracked' && <StatusBadge variant="info" label="TRACKED" dot={false} className="text-[9px]" />}
                    </td>
                    <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{s.sig}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}

      {tab === 'Sky Plot' && (
        <div className="grid grid-cols-2 gap-4">
          <Card>
            <CardHeader title="GNSS Sky Plot (Current)" badge={<ProvenanceTag type="observed" />} />
            <CardBody className="flex flex-col items-center py-4">
              <SkyPlot sats={satellites} />
              <div className="flex gap-4 mt-3 text-[10px]">
                {Object.entries(SYSCOLORS).map(([sys, colorVar]) => (
                  <span key={sys} className="flex items-center gap-1">
                    <span className={`w-2 h-2 rounded-full ${SYSDOT[sys]} inline-block`}/>
                    <span style={{ color: colorVar }}>{sys}</span>
                  </span>
                ))}
              </div>
              <div className="mt-2 text-[10px]" style={{ color:'var(--t3)' }}>Filled = used in solution · Dim = tracked only</div>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Legend & Statistics" />
            <CardBody>
              <MetricRow label="GPS satellites" value={`${satellites.filter(s=>s.sys==='GPS').length}`} />
              <MetricRow label="GLONASS" value={`${satellites.filter(s=>s.sys==='GLONASS').length}`} />
              <MetricRow label="Galileo" value={`${satellites.filter(s=>s.sys==='GALILEO').length}`} />
              <MetricRow label="BeiDou" value={`${satellites.filter(s=>s.sys==='BEIDOU').length}`} />
              <div className="mt-2 pt-2" style={{ borderTop:'1px solid var(--border)' }}>
                <MetricRow label="Mean C/N₀" value={`${(satellites.reduce((a,s)=>a+s.cn0,0)/satellites.length).toFixed(1)}`} unit="dB-Hz" />
                <MetricRow label="Best C/N₀" value={`${Math.max(...satellites.map(s=>s.cn0))}`} unit="dB-Hz" />
                <MetricRow label="PDOP" value="1.4" provenance="observed" />
                <MetricRow label="GDOP" value="1.7" provenance="observed" />
              </div>
              <ELI5 text="The sky plot shows where each satellite is in the sky. Satellites near the outer edge are close to the horizon. A good spread across the sky means better geometry and timing." />
            </CardBody>
          </Card>
        </div>
      )}

      {tab === 'Sky Obstruction' && (
        <div className="grid grid-cols-2 gap-4">
          <Card>
            <CardHeader title="Learned Sky Obstruction" badge={<ProvenanceTag type="inferred" />} />
            <CardBody className="flex flex-col items-center py-4">
              <ObstructionHeatmap />
              <div className="mt-3 w-full space-y-1">
                <MetricRow label="Open-sky estimate" value="78%" provenance="inferred" />
                <MetricRow label="Primary obstruction" value="W / WNW (240–310°)" provenance="inferred" />
                <MetricRow label="Observation window" value="47 days, 3h 12m" />
                <MetricRow label="Confidence" value="Medium" />
              </div>
              <div className="mt-3 p-2 rounded-sm text-[10px]" style={{ background:'var(--bg)', border:'1px solid var(--border)', color:'var(--t3)' }}>
                Derived from long-term C/N₀ and tracking success patterns. This is an RF/GNSS-derived horizon model, not a physical sky survey.
              </div>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Obstruction Analysis" />
            <CardBody>
              <div className="text-[11px] mb-3" style={{ color:'var(--t2)' }}>
                Station appears to have a significant obstruction in the western sky (240–310° azimuth, below 30° elevation). Consistent with a structure to the west-northwest.
              </div>
              <MetricRow label="Satellite loss events W-sector" value="143" />
              <MetricRow label="Avg. C/N₀ west vs east" value="31 vs 44 dB-Hz" />
              <MetricRow label="Tracking success W sector" value="54%" />
              <MetricRow label="Tracking success overall" value="91%" />
            </CardBody>
          </Card>
        </div>
      )}

      {tab === 'Position' && (
        <div className="space-y-4">
          <Card>
            <CardHeader title="Position — Station Survey" />
            <CardBody>
              <div className="grid grid-cols-3 gap-4">
                <div className="rounded-sm p-3" style={{ background:'var(--bg)', border:'1px solid var(--border)' }}>
                  <div className="text-[10px] mono uppercase mb-2" style={{ color:'var(--t3)' }}>Live Fix</div>
                  <MetricRow label="Lat" value={`${STATION_LAT.toFixed(6)}°`} provenance="observed" />
                  <MetricRow label="Lon" value={`${STATION_LON.toFixed(6)}°`} provenance="observed" />
                  <MetricRow label="h (ellip.)" value={`${STATION_ALT_ELLIP} m`} provenance="observed" />
                </div>
                <div className="bg-cyan-400/5 border border-cyan-400/15 rounded-sm p-3">
                  <div className="text-[10px] mono uppercase mb-2" style={{ color:'var(--live)', opacity:0.6 }}>Surveyed / Accepted</div>
                  <MetricRow label="Lat" value={`${STATION_LAT.toFixed(7)}°`} />
                  <MetricRow label="Lon" value={`${STATION_LON.toFixed(7)}°`} />
                  <MetricRow label="h (ellip.)" value={`${STATION_ALT_ELLIP} m`} />
                  <MetricRow label="Survey duration" value="72h 0m" />
                  <MetricRow label="Accepted obs." value="241,920" />
                </div>
                <div className="rounded-sm p-3" style={{ background:'var(--bg)', border:'1px solid var(--border)' }}>
                  <div className="text-[10px] mono uppercase mb-2" style={{ color:'var(--t3)' }}>Scatter Statistics</div>
                  <MetricRow label="Horiz. 2-sigma" value="0.8 m" provenance="observed" />
                  <MetricRow label="Vertical 2-sigma" value="1.6 m" provenance="observed" />
                  <MetricRow label="Rejected obs." value="412 (0.17%)" />
                  <div className="mt-2 text-[10px]" style={{ color:'var(--t3)' }}>Statistical convergence does not guarantee absolute surveyed accuracy.</div>
                </div>
              </div>
            </CardBody>
          </Card>
        </div>
      )}

      {tab === 'Geodesy' && (
        <Card>
          <CardHeader title="Geodesy" badge={<ProvenanceTag type="calculated" />} />
          <CardBody>
            <div className="grid grid-cols-2 gap-x-8">
              <div>
                <SectionHeader title="Geographic Coordinates" />
                <MetricRow label="Latitude" value={`${STATION_LAT.toFixed(7)}° N`} />
                <MetricRow label="Longitude" value={`${Math.abs(STATION_LON).toFixed(7)}° W`} />
                <MetricRow label="Datum" value="WGS84" />
              </div>
              <div>
                <SectionHeader title="Heights" />
                <MetricRow label="Ellipsoidal height h" value={`${STATION_ALT_ELLIP} m`} provenance="observed" />
                <MetricRow label="Orthometric height H" value={`${STATION_ALT_ORTHO} m`} provenance="calculated" />
                <MetricRow label="Geoid undulation N" value={`${STATION_GEOID_N} m`} provenance="modeled" />
                <MetricRow label="Geoid model" value="EGM2008" muted />
              </div>
            </div>
            <ELI5 text="Ellipsoidal height (h) is distance above the WGS84 mathematical ellipsoid. Orthometric height (H) is distance above the geoid — roughly mean sea level. The difference N is the geoid undulation." />
          </CardBody>
        </Card>
      )}

      {tab === 'Calibration' && <CalibrationPanel />}
    </div>
  );
}

