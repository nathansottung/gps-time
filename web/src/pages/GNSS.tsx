import { useState } from 'react';
import { Card, CardHeader, CardBody, MetricRow, StatusBadge, ELI5, Tabs, ProvenanceTag, SectionHeader } from '../components/ui';
import { SkyPlot } from '../components/charts';
import { Planned, ApiErrorNote } from '../components/planned';
import { useStation, usePoll } from '../api/station';
import type { Survey } from '../api/types';
import { ConvergenceCard, IngestCard, ScatterCard } from '../components/survey';
import { toSkySats, plottable, cn0Stats, satCounts } from '../api/view';

const SYSCOLORS: Record<string,string> = {
  GPS:'var(--live)', GLONASS:'var(--warn-text)', GALILEO:'var(--mod-text)', BEIDOU:'var(--good-text)',
};
const SYSDOT: Record<string,string> = {
  GPS:'bg-cyan-400', GLONASS:'bg-amber-400', GALILEO:'bg-purple-400', BEIDOU:'bg-green-400',
};

// Simulated obstruction heatmap cells (preview of a planned feature; demo only)
const obstructionCells = Array.from({ length: 36 }, (_, ai) =>
  Array.from({ length: 6 }, (_, ei) => ({
    az: ai * 10,
    el: ei * 15,
    quality: ai >= 24 && ai <= 32 && ei <= 2 ? 0.15 : 0.75 + ((ai * 7 + ei * 13) % 20) / 100,
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

// Calibration section (planned)
function CalibrationPanel() {
  return (
    <Planned title="Antenna & Calibration" needs="stored antenna, cable and receiver delay records">
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
    </Planned>
  );
}

const PROV_LABEL: Record<string, string> = {
  live: 'live fix', stored: 'stored site (no live fix)', none: 'no position', demo: 'demo',
};

export default function GNSS() {
  const [tab, setTab] = useState('Satellites');
  const { api, core } = useStation();
  // /api/survey only while the Survey tab is open (parity 14, 15).
  const surveyTab = tab === 'Survey';
  const surveyPoll = usePoll<Survey | null>(() => surveyTab ? api.survey() : Promise.resolve(null), surveyTab ? 30_000 : 0, [api, surveyTab]);
  const gps = core.data?.gps;
  const loc = core.data?.location;
  const survey = core.data?.survey;
  const sats = gps?.sky_stale ? [] : toSkySats(gps?.sats ?? []);   // a stale sky report is not shown as current
  const counts = satCounts(gps);
  const c = cn0Stats(sats);
  const fixLabel = !gps ? 'UNKNOWN' : gps.stale ? 'STALE' : gps.fix ? `${gps.fix} FIX` : 'NO FIX';

  // Heights: h from the receiver (observed), H as gpsd reports it, N = h − H (calculated).
  // Only values the privacy mode lets through are used.
  const h = loc?.alt_hae ?? null;
  const H = loc?.alt_msl ?? null;
  const N = h !== null && H !== null ? h - H : null;
  const privacy = loc?.mode === 'hidden' ? 'Location hidden by the station privacy setting.'
    : loc?.mode === 'rounded' ? 'Location rounded by the station privacy setting (~11 km).' : null;

  return (
    <div className="space-y-4 page-enter">
      <div className="flex items-baseline justify-between">
        <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>GNSS & Site</h1>
        <div className="flex gap-2">
          <StatusBadge variant={!gps ? 'muted' : gps.stale || gps.fix !== '3D' ? 'warn' : 'good'} label={fixLabel} />
          <StatusBadge variant="info" label={`${counts.used ?? '—'} SVs USED`} dot={false} />
        </div>
      </div>

      <ApiErrorNote error={core.error} />

      <Tabs tabs={['Satellites','Sky Plot','Sky Obstruction','Position','Survey','Geodesy','Calibration']} active={tab} onChange={setTab} />

      {surveyTab && (
        <div className="space-y-4">
          <ApiErrorNote error={surveyPoll.error} />
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2"><ConvergenceCard survey={surveyPoll.data} /></div>
            <IngestCard survey={surveyPoll.data} />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <ScatterCard survey={surveyPoll.data} />
          </div>
        </div>
      )}

      {tab === 'Satellites' && (
        <Card>
          <CardHeader title="Satellite Table" badge={<ProvenanceTag type="observed" />} />
          <CardBody className="p-0">
            <table className="w-full text-[11px]">
              <thead>
                <tr style={{ borderBottom:'1px solid var(--border)' }}>
                  {['System','SVID','Az °','El °','C/N₀ dB-Hz','State'].map(h => (
                    <th key={h} className="text-left px-4 py-2 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sats.map(s => (
                  <tr key={s.sys + s.svid} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                    <td className="px-4 py-2">
                      <span className="font-mono text-[10px]" style={{ color: SYSCOLORS[s.sys] || 'var(--t2)' }}>{s.sys}</span>
                    </td>
                    <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}>{s.svid}</td>
                    <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>{Number.isFinite(s.az) ? s.az : '—'}</td>
                    <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>{Number.isFinite(s.el) ? s.el : '—'}</td>
                    <td className="px-4 py-2">
                      {Number.isFinite(s.cn0) ? (
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 rounded-full overflow-hidden max-w-[60px]" style={{ background:'var(--bg)' }}>
                            <div className={`h-full rounded-full ${s.cn0>44?'bg-green-400/70':s.cn0>35?'bg-cyan-400/70':'bg-amber-400/70'}`}
                              style={{ width:`${Math.min(100, (s.cn0/55)*100)}%`}}/>
                          </div>
                          <span className="mono tabular" style={{ color:'var(--t1)' }}>{s.cn0}</span>
                        </div>
                      ) : <span className="mono" style={{ color:'var(--t4)' }}>—</span>}
                    </td>
                    <td className="px-4 py-2">
                      {s.state === 'used'    && <StatusBadge variant="good" label="USED" dot={false} className="text-[9px]" />}
                      {s.state === 'tracked' && <StatusBadge variant="info" label="TRACKED" dot={false} className="text-[9px]" />}
                    </td>
                  </tr>
                ))}
                {!sats.length && <tr><td colSpan={6} className="px-4 py-3 text-[10px]" style={{ color:'var(--t4)' }}>
                  {gps ? (gps.sky_stale ? 'Sky data is stale.' : 'No satellites reported.') : 'GNSS data not loaded.'}</td></tr>}
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
              <SkyPlot sats={plottable(sats)} hiddenNote={loc?.mode === 'hidden' ? 'positions hidden (privacy)' : undefined} />
              <div className="flex gap-4 mt-3 text-[10px]">
                {Object.entries(SYSCOLORS).map(([sys, colorVar]) => (
                  <span key={sys} className="flex items-center gap-1">
                    <span className={`w-2 h-2 rounded-full ${SYSDOT[sys]} inline-block`}/>
                    <span style={{ color: colorVar }}>{sys}</span>
                  </span>
                ))}
              </div>
              <div className="mt-2 text-[10px]" style={{ color:'var(--t3)' }}>
                {loc?.mode === 'hidden' ? "Sky positions hidden by the station's privacy setting. Azimuth and elevation would reveal the station's position."
                  : 'Filled = used in solution · Dim = tracked only'}
              </div>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Legend & Statistics" />
            <CardBody>
              {['GPS','GLONASS','GALILEO','BEIDOU'].map(sys => (
                <MetricRow key={sys} label={sys === 'GPS' ? 'GPS satellites' : sys[0] + sys.slice(1).toLowerCase()}
                  value={counts.visible === null ? null : sats.filter(s => s.sys === sys).length} />
              ))}
              <div className="mt-2 pt-2" style={{ borderTop:'1px solid var(--border)' }}>
                <MetricRow label="Mean C/N₀" value={c.mean === null ? null : c.mean.toFixed(1)} unit="dB-Hz" provenance="calculated" />
                <MetricRow label="Best C/N₀" value={c.best} unit="dB-Hz" provenance="observed" />
                <MetricRow label="TDOP" value={gps?.tdop ?? null} provenance="observed" />
                <MetricRow label="HDOP" value={gps?.hdop ?? null} provenance="observed" />
              </div>
              <ELI5 text="The sky plot shows where each satellite is in the sky. Satellites near the outer edge are close to the horizon. A good spread across the sky means better geometry and timing." />
            </CardBody>
          </Card>
        </div>
      )}

      {tab === 'Sky Obstruction' && (
        <Planned title="Learned Sky Obstruction" needs="long-term C/N₀ and tracking statistics per sky sector">
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
                Lower C/N₀ and tracking success in the western sky (240–310° azimuth, below 30° elevation). The evidence does not establish what is blocking the signal.
              </div>
              <MetricRow label="Satellite loss events W-sector" value="143" />
              <MetricRow label="Avg. C/N₀ west vs east" value="31 vs 44 dB-Hz" />
              <MetricRow label="Tracking success W sector" value="54%" />
              <MetricRow label="Tracking success overall" value="91%" />
            </CardBody>
          </Card>
        </div>
        </Planned>
      )}

      {tab === 'Position' && (
        <div className="space-y-4">
          <Card>
            <CardHeader title="Position — Station Survey" />
            <CardBody>
              {privacy && <div className="text-[10px] mb-3" style={{ color:'var(--t3)' }}>{privacy}</div>}
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-sm p-3" style={{ background:'var(--bg)', border:'1px solid var(--border)' }}>
                  <div className="text-[10px] mono uppercase mb-2" style={{ color:'var(--t3)' }}>
                    Position · {PROV_LABEL[core.data?.position_provenance ?? 'none'] ?? 'UNKNOWN'}
                  </div>
                  <MetricRow label="Lat" value={loc?.lat == null ? null : `${loc.lat}°`} provenance="observed" sensitive />
                  <MetricRow label="Lon" value={loc?.lon == null ? null : `${loc.lon}°`} provenance="observed" sensitive />
                  <MetricRow label="H (MSL)" value={H === null ? null : `${H} m`} provenance="observed" sensitive />
                  <MetricRow label="Fix" value={gps ? (gps.stale ? `stale (last ${gps.last_fix ?? '—'})` : gps.fix) : null} />
                  <MetricRow label="Data age" value={gps?.data_age_s == null ? null : `${gps.data_age_s.toFixed(1)} s`} provenance="calculated" />
                </div>
                <div className="rounded-sm p-3" style={{ background:'var(--bg)', border:'1px solid var(--border)' }}>
                  <div className="text-[10px] mono uppercase mb-2" style={{ color:'var(--t3)' }}>Survey statistics</div>
                  <MetricRow label="Accepted fixes" value={survey ? survey.n.toLocaleString() : null} />
                  <MetricRow label="Fresh / legacy" value={survey?.n_fresh == null ? null : `${survey.n_fresh.toLocaleString()} / ${(survey.n_legacy ?? 0).toLocaleString()}`} />
                  <MetricRow label="Horizontal SE of mean" value={survey?.se_horiz_m == null ? null : `±${survey.se_horiz_m.toFixed(2)} m`} provenance="calculated" />
                  <MetricRow label="Vertical SE of mean" value={survey?.se_alt_m == null ? null : `±${survey.se_alt_m.toFixed(2)} m`} provenance="calculated" />
                  <MetricRow label="Per-fix scatter (lat / lon / alt)"
                    value={survey?.sd_lat_m == null ? null : `${survey.sd_lat_m.toFixed(1)} / ${survey.sd_lon_m?.toFixed(1)} / ${survey.sd_alt_m?.toFixed(1)} m`} provenance="calculated" />
                  <div className="mt-2 text-[10px]" style={{ color:'var(--t3)' }}>Statistical convergence does not guarantee absolute surveyed accuracy.</div>
                </div>
              </div>
            </CardBody>
          </Card>
        </div>
      )}

      {tab === 'Geodesy' && (
        <Card>
          <CardHeader title="Geodesy" />
          <CardBody>
            {privacy && <div className="text-[10px] mb-3" style={{ color:'var(--t3)' }}>{privacy}</div>}
            <div className="grid grid-cols-2 gap-x-8">
              <div>
                <SectionHeader title="Geographic Coordinates" />
                <MetricRow label="Latitude" value={loc?.lat == null ? null : `${Math.abs(loc.lat)}° ${loc.lat >= 0 ? 'N' : 'S'}`} provenance="observed" sensitive />
                <MetricRow label="Longitude" value={loc?.lon == null ? null : `${Math.abs(loc.lon)}° ${loc.lon >= 0 ? 'E' : 'W'}`} provenance="observed" sensitive />
                <MetricRow label="Datum" value="WGS84" />
              </div>
              <div>
                <SectionHeader title="Heights" />
                <MetricRow label="Ellipsoidal height h" value={h === null ? null : `${h} m`} provenance="observed" sensitive />
                <MetricRow label="Orthometric height H (gpsd)" value={H === null ? null : `${H} m`} provenance="observed" sensitive />
                <MetricRow label="Geoid undulation N = h − H" value={N === null ? null : `${N.toFixed(1)} m`} provenance="calculated" sensitive />
                <MetricRow label="Geoid model" value={null} muted />
              </div>
            </div>
            <ELI5 text="Ellipsoidal height (h) is distance above the WGS84 mathematical ellipsoid. Orthometric height (H) is distance above the geoid — roughly mean sea level. The difference N is the geoid undulation. H here is what the receiver/gpsd reports; the geoid model it uses is not reported." />
          </CardBody>
        </Card>
      )}

      {tab === 'Calibration' && <CalibrationPanel />}
    </div>
  );
}
