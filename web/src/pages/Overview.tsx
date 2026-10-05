import { useState } from 'react';
import { Card, CardHeader, CardBody, MetricRow, StatusBadge, ELI5, ProvenanceTag } from '../components/ui';
import { OffsetChart, SkyPlot, SolarCurve } from '../components/charts';
import { Planned, ApiErrorNote } from '../components/planned';
import { TimingChainCard } from '../components/timing';
import { StationClockCard } from '../components/clock';
import { useStation, usePoll, useBrowserClock } from '../api/station';
import { toSkySats, plottable, cn0Stats, toOffsetSeries, fracFreq, allEvents, satCounts, ntpClientCount } from '../api/view';
import type { Almanac, SolarDay, LunarDay } from '../api/types';
import { holdover, dataPacks } from '../api/previews';
import { fmtSci } from '../lib/units';
import { sunShifts, fmtShift, type SunEvent } from '../lib/sun';
import { fmtOffset, fmtSeconds, lightDistance, fmtClock, fmtDuration, fmtDelta, browserTimeZone } from '../lib/format';

// Clear-sky model curve for the irradiance preview (planned feature; demo only).
const irradianceData = Array.from({ length: 24 }, (_, h) => ({
  h, w: Math.round(Math.max(0, 850 * Math.sin(Math.PI*(h-6)/13)) * (h>=6&&h<=19?1:0)),
}));

const TZ = browserTimeZone();

function useAlmanac() {
  const { api } = useStation();
  return usePoll(() => api.almanac({ tz: TZ }), 10 * 60_000, [api]);
}
const sunOf  = (a: Almanac | { available: false } | null) => (a && a.available && a.sun.available ? a.sun as SolarDay : null);
const moonOf = (a: Almanac | { available: false } | null) => (a && a.available && a.moon.available ? a.moon as LunarDay : null);

function useHistory() {
  const { api } = useStation();
  return usePoll(() => api.history(), 30_000, [api]);
}

/** Live timing numbers shared by the variants. */
function useTiming() {
  const { core, chain } = useStation();
  const q = core.data?.quality;
  const dt = fmtOffset(q?.system_time_s);
  return {
    core, chain,
    dt,
    err: fmtSeconds(q?.root_dispersion_s),
    light: lightDistance(q?.system_time_s),
    rms: fmtSeconds(q?.rms_offset_s),
    frac: fracFreq(core.data),
    ref: q?.reference ?? null,
    stratum: q?.stratum ?? null,
    ppsState: chain.data?.pps_state.value ?? null,
    status: chain.data?.status ?? null,
  };
}

function statusBadge(code: string | undefined, label: string | undefined) {
  if (!code || !label) return <StatusBadge variant="muted" label="UNKNOWN" />;
  const v = code === 'GPS_PPS' ? 'good' : code === 'UNSYNCHRONIZED' ? 'error' : code === 'UNKNOWN' ? 'muted' : 'warn';
  return <StatusBadge variant={v} label={label} pulse={v === 'good'} />;
}

// ─── Timing Quality ───────────────────────────────────────────────────────────
function TimingWidget() {
  const t = useTiming();
  const hist = useHistory();
  const s1h = toOffsetSeries(hist.data?.points, 3600);
  return (
    <Card>
      <CardHeader title="Timing Quality" badge={statusBadge(t.status?.code, t.status?.banner)} />
      <CardBody>
        <ApiErrorNote error={t.core.error} />
        <div className="flex items-start gap-8 mb-3">
          {/* Primary reading — the one place we use the brightest live color */}
          <div className="flex-shrink-0">
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="text-[9px] mono uppercase tracking-[0.15em]" style={{ color:'var(--t3)' }}>System clock Δt (chrony)</span>
              <ProvenanceTag type="observed" />
            </div>
            {t.dt ? (
              <div className="flex items-baseline gap-2">
                <span className="mono tabular font-semibold" style={{ fontSize:36, lineHeight:1, color:'var(--live-bright)', letterSpacing:'-0.01em' }}>{t.dt.value}</span>
                <div className="flex flex-col">
                  <span className="mono text-base" style={{ color:'var(--t2)' }}>{t.dt.unit}</span>
                  {t.err && <span className="mono text-[10px]" style={{ color:'var(--t3)' }}>± {t.err}</span>}
                </div>
              </div>
            ) : <StatusBadge variant="muted" label="UNKNOWN" dot={false} />}
            {t.light && <div className="text-[10px] mono mt-1" style={{ color:'var(--t4)' }}>≡ {t.light} light-equivalent</div>}
            <ELI5 text="chrony's estimate of how far the system clock is from its reference right now (positive = fast). The ± is chrony's root dispersion. It is not an independent measurement against GPS." />
          </div>

          {/* Offset history chart */}
          <div className="flex-1 min-w-0" style={{ borderLeft:'1px solid var(--border-dim)', paddingLeft:'1.5rem' }}>
            <div className="text-[9px] mono uppercase tracking-[0.15em] mb-1" style={{ color:'var(--t3)' }}>Δt — last 1 hour ({s1h.unit})</div>
            {s1h.data.length
              ? <OffsetChart data={s1h.data} range="1h" unit={s1h.unit} />
              : <div className="text-[10px] py-8 text-center" style={{ color:'var(--t4)' }}>
                  {hist.data && !hist.data.available ? 'chrony tracking log not available' : 'No samples in the last hour'}
                </div>}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-x-6" style={{ borderTop:'1px solid var(--border-dim)', paddingTop:'0.75rem' }}>
          <div>
            <MetricRow label="RMS offset (chrony)" value={t.rms} provenance="calculated" />
            <MetricRow label="Δf/f (uncorrected clock)" value={t.frac === null ? null : fmtSci(t.frac)} provenance="calculated" />
          </div>
          <div>
            <MetricRow label="PPS state" value={t.ppsState} provenance="calculated" />
            <MetricRow label="Time since boot" value={fmtDuration(t.chain.data?.boot.since_boot_s.value)} provenance="calculated" />
          </div>
          <div>
            <MetricRow label="Reference" value={t.ref} />
            <MetricRow label="NTP stratum" value={t.stratum} />
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Holdover (planned) ───────────────────────────────────────────────────────
function HoldoverWidget() {
  return (
    <Planned title="Holdover Characterization" needs="an oscillator model trained on validated holdover runs">
    <Card>
      <CardHeader title="Holdover Characterization" />
      <CardBody>
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-[2px] p-3" style={{ background:'rgba(255,255,255,0.018)', border:'1px solid var(--border-dim)' }}>
            <div className="text-[9px] mono uppercase tracking-[0.12em] mb-2" style={{ color:'var(--t4)' }}>Raw Oscillator</div>
            <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>Free-running quartz, no discipline</div>
            <div className="text-[11px]" style={{ color:'var(--t2)' }}>1 s error in <span className="mono font-medium" style={{ color:'var(--warn-text)' }}>~{holdover.rawErrorIn1SecAfterDays} days</span></div>
            <div className="text-[9px] mono mt-1" style={{ color:'var(--t4)' }}>±{fmtSci(holdover.rawOscillatorDrift)} s⁻¹ drift</div>
          </div>
          <div className="rounded-[2px] p-3" style={{ background:'rgba(91,140,184,0.04)', border:'1px solid rgba(91,140,184,0.14)' }}>
            <div className="flex items-center gap-1.5 mb-2">
              <span className="text-[9px] mono uppercase tracking-[0.12em]" style={{ color:'var(--accent)' }}>Trained Holdover</span>
              <ProvenanceTag type="predicted" />
            </div>
            <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>{holdover.trainedValidatedHours} h characterization window</div>
            <div className="text-[11px]" style={{ color:'var(--t2)' }}>1 s error in <span className="mono font-medium" style={{ color:'var(--live)' }}>~{Math.round(holdover.trainedErrorIn1SecAfterDays)} days</span></div>
            <div className="text-[9px] mono mt-1" style={{ color:'var(--t4)' }}>{holdover.trainedConfidenceHours} h validated confidence window</div>
          </div>
          <div className="rounded-[2px] p-3" style={{ background:'var(--good-bg)', border:'1px solid var(--good-border)' }}>
            <div className="text-[9px] mono uppercase tracking-[0.12em] mb-2" style={{ color:'var(--good-text)' }}>GPS/PPS Disciplined</div>
            <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>Continuously corrected by PPS tick</div>
            <div className="text-[11px]" style={{ color:'var(--t2)' }}>Δt held within <span className="mono font-medium" style={{ color:'var(--good-text)' }}>~50 ns</span></div>
            <div className="text-[9px] mt-1" style={{ color:'var(--t4)' }}>No extrapolated long-term accuracy claimed</div>
          </div>
        </div>
      </CardBody>
    </Card>
    </Planned>
  );
}

// ─── Sun ──────────────────────────────────────────────────────────────────────
export function SunDays({ almanac }: { almanac: Almanac | null }) {
  const sun = sunOf(almanac);
  const nb = almanac?.available ? almanac.neighbors : null;
  const cols = [
    { label:'Yesterday', rise: nb?.yesterday.sunrise, noon: undefined, set: nb?.yesterday.sunset, dur: nb?.yesterday.daylight_s, chg: null },
    { label:'Today',     rise: sun?.events.sunrise,   noon: sun?.noon,  set: sun?.events.sunset,   dur: sun?.daylight_s,          chg: almanac?.available ? almanac.delta_yesterday : null },
    { label:'Tomorrow',  rise: nb?.tomorrow.sunrise,  noon: undefined, set: nb?.tomorrow.sunset,  dur: nb?.tomorrow.daylight_s,  chg: almanac?.available ? almanac.delta_tomorrow : null },
  ];
  return (
    <div>
      <div className="grid grid-cols-3 gap-2 text-[11px]">
      {cols.map(c => {
        const chg = fmtDelta(c.chg);   // daylight change vs the prior day (astro.daylight_deltas)
        return (
          <div key={c.label} className="rounded-[2px] p-2.5"
            style={c.label==='Today'
              ? { background:'rgba(176,120,16,0.05)', border:'1px solid rgba(176,120,16,0.14)' }
              : { background:'rgba(255,255,255,0.015)', border:'1px solid var(--border-dim)' }}>
            <div className="text-[9px] mono uppercase tracking-[0.12em] mb-2"
              style={{ color: c.label==='Today' ? 'var(--warn-text)' : 'var(--t4)' }}>{c.label}</div>
            {([['Sunrise', c.rise], ['Solar noon', c.noon], ['Sunset', c.set]] as const).map(([k, v]) => (
              c.label !== 'Today' && k === 'Solar noon' ? null :
              <div key={k} className="flex justify-between py-[3px]">
                <span style={{ color:'var(--t3)' }}>{k}</span>
                <span className="mono" style={{ color:'var(--t1)' }}>{fmtClock(v, TZ) ?? '—'}</span>
              </div>
            ))}
            <div className="flex justify-between py-[3px] mt-1" style={{ borderTop:'1px solid var(--border-dim)' }}>
              <span style={{ color:'var(--t3)' }}>Daylight</span>
              <span className="mono font-medium" style={{ color:'var(--t1)' }}>{fmtDuration(c.dur) ?? '—'}</span>
            </div>
            {chg && (
              <div className="flex justify-between py-[2px]">
                <span style={{ color:'var(--t3)' }}>vs prior day</span>
                <span className="mono text-[9px]" style={{ color: chg.startsWith('+') ? 'var(--good-text)' : 'var(--t3)' }}>{chg}</span>
              </div>
            )}
          </div>
        );
      })}
      </div>
      <SunShiftTable almanac={almanac} />
    </div>
  );
}

const SHIFT_ROWS: [SunEvent, string][] = [['sunrise', 'Sunrise'], ['noon', 'Solar noon'], ['sunset', 'Sunset'], ['daylight', 'Daylight']];
const TH = { color:'var(--t3)', fontWeight:400, fontFamily:'JetBrains Mono', fontSize:10, letterSpacing:'0.05em',
             padding:'6px 8px', borderBottom:'1px solid var(--border)' } as const;

/** Day-to-day shifts in signed seconds (lib/sun.ts), predicted like the times they come from. */
function SunShiftTable({ almanac }: { almanac: Almanac | null }) {
  const shifts = almanac ? sunShifts(almanac) : null;
  if (!shifts) return null;
  return (
    <div className="mt-3">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[9px] mono uppercase tracking-[0.12em]" style={{ color:'var(--t4)' }}>Shift per day</span>
        <ProvenanceTag type="predicted" />
      </div>
      <table className="w-full text-[11px]">
        <thead>
          <tr>
            <th style={{ ...TH, textAlign:'left' }}>Event</th>
            <th style={{ ...TH, textAlign:'right' }}>vs yesterday</th>
            <th style={{ ...TH, textAlign:'right' }}>to tomorrow</th>
          </tr>
        </thead>
        <tbody>
          {SHIFT_ROWS.map(([k, label]) => (
            <tr key={k} className="row-sep">
              <td className="px-2 py-1.5" style={{ color:'var(--t1)' }}>{label}</td>
              <td className="px-2 py-1.5 mono tabular text-right" style={{ color:'var(--t2)' }}>{fmtShift(shifts.rows[k].vsYesterday) ?? '—'}</td>
              <td className="px-2 py-1.5 mono tabular text-right" style={{ color:'var(--t2)' }}>{fmtShift(shifts.rows[k].toTomorrow) ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {shifts.clockChange && (
        <div className="text-[9px] mt-1" style={{ color:'var(--t4)' }}>
          The clock changes (DST) within these days; shifts exclude the hour.
        </div>
      )}
    </div>
  );
}

function SunWidget() {
  const alm = useAlmanac();
  const unavailable = alm.data && !alm.data.available ? alm.data.reason : null;
  return (
    <Card>
      <CardHeader title="Sun & Daylight" badge={<ProvenanceTag type="predicted" />} />
      <CardBody>
        <ApiErrorNote error={alm.error} />
        {unavailable
          ? <div className="text-[11px]" style={{ color:'var(--t3)' }}>Almanac unavailable: {unavailable}</div>
          : <SunDays almanac={alm.data && alm.data.available ? alm.data : null} />}
        <div className="text-[9px] mt-2" style={{ color:'var(--t4)' }}>
          Times in {TZ}.{alm.data?.available && alm.data.location_display === 'rounded' && ' Computed for the rounded site (~11 km), per the privacy setting.'}
        </div>
      </CardBody>
    </Card>
  );
}

// ─── GNSS Summary ─────────────────────────────────────────────────────────────
function GNSSWidget() {
  const { core } = useStation();
  const gps = core.data?.gps;
  const counts = satCounts(gps);
  const sats = gps?.sky_stale ? [] : toSkySats(gps?.sats ?? []);
  const c = cn0Stats(sats);
  const fixLabel = !gps ? 'UNKNOWN' : gps.stale ? 'STALE' : (gps.fix ?? 'NO FIX');
  return (
    <Card>
      <CardHeader title="GNSS" badge={<StatusBadge variant={!gps ? 'muted' : gps.stale || gps.fix !== '3D' ? 'warn' : 'good'} label={fixLabel === '3D' ? '3D FIX' : fixLabel} />} />
      <CardBody>
        <div className="flex gap-0 mb-3" style={{ borderBottom:'1px solid var(--border-dim)', paddingBottom:'0.75rem' }}>
          {[
            { v: counts.visible, l:'Visible' },
            { v: counts.used,    l:'Used', accent:true },
          ].map(({v,l,accent}) => (
            <div key={l} className="flex-1 text-center">
              <div className="mono text-xl font-medium tabular" style={{ color: accent ? 'var(--live)' : 'var(--t1)' }}>{v ?? '—'}</div>
              <div className="text-[9px]" style={{ color:'var(--t4)' }}>{l}</div>
            </div>
          ))}
        </div>
        <MetricRow label="Best C/N₀" value={c.best} unit="dB-Hz" provenance="observed" />
        <MetricRow label="Median C/N₀" value={c.median} unit="dB-Hz" provenance="calculated" />
        <MetricRow label="TDOP" value={gps?.tdop ?? null} provenance="observed" />
        <MetricRow label="Data age" value={gps?.data_age_s == null ? null : gps.data_age_s.toFixed(1)} unit="s" provenance="calculated" />
        <ELI5 text="C/N₀ (carrier-to-noise-density) measures how clearly each satellite is heard above background noise. Higher is better." />
        <div className="mt-3 flex justify-center">
          <SkyPlot sats={plottable(sats)} hiddenNote={core.data?.location.mode === 'hidden' ? 'positions hidden (privacy)' : undefined} />
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Network ──────────────────────────────────────────────────────────────────
function NetworkWidget() {
  const { core, chain } = useStation();
  const clk = useBrowserClock();
  return (
    <Card>
      <CardHeader title="Network & NTP" />
      <CardBody>
        <MetricRow label="NTP clients (chrony)" value={ntpClientCount(core.data, chain.data)} provenance="observed" />
        <MetricRow label="Browser RTT (median)" value={clk.medianRttMs === null ? null : clk.medianRttMs.toFixed(1)} unit="ms" provenance="observed" />
        <MetricRow label="Est. browser Δt" value={clk.offsetMs === null ? null : (-clk.offsetMs).toFixed(1)} unit="ms" provenance="inferred" />
        <div className="mt-3 text-[10px] px-2 py-1.5 rounded-[2px]"
          style={{ background:'rgba(255,255,255,0.02)', border:'1px solid var(--border-dim)', color:'var(--t4)' }}>
          Browser Δt is this browser's clock minus the station's, from a four-timestamp exchange; positive = browser ahead. Polling this server does not confirm client clock accuracy.
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Solar (planned) ──────────────────────────────────────────────────────────
function SolarWidget() {
  return (
    <Planned title="Solar Irradiance" needs="a clear-sky irradiance model in the almanac">
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
    </Planned>
  );
}

// ─── Data Packs (planned) ─────────────────────────────────────────────────────
function DataPackWidget() {
  const allOk = dataPacks.filter(p=>p.state!=='unavail').every(p=>p.state==='current');
  return (
    <Planned title="Offline Readiness" needs="a data-pack manifest endpoint">
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
    </Planned>
  );
}

// ─── Moon ─────────────────────────────────────────────────────────────────────
export function MoonPhaseIcon({ illumPct, waxing }: { illumPct: number; waxing: boolean }) {
  // Terminator ellipse from illuminated fraction k: rx = r·|1 − 2k|.
  const k = illumPct / 100;
  const rx = Math.abs(19 * (1 - 2 * k));
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" className="flex-shrink-0">
      <circle cx="22" cy="22" r="19" fill="var(--border)" stroke="var(--border-em)" strokeWidth="0.75"/>
      <path d={`M22 3 A19 19 0 0 ${waxing ? 1 : 0} 22 41 A${rx} 19 0 0 ${(k > 0.5) === waxing ? 1 : 0} 22 3`} fill="var(--t2)" fillOpacity={0.85}/>
      <circle cx="22" cy="22" r="19" fill="none" stroke="var(--t2)" strokeWidth="0.5" strokeOpacity={0.2}/>
    </svg>
  );
}

function MoonWidget() {
  const alm = useAlmanac();
  const moon = moonOf(alm.data);
  return (
    <Card>
      <CardHeader title="Moon" badge={<ProvenanceTag type="predicted" />} />
      <CardBody>
        <ApiErrorNote error={alm.error} />
        <div className="flex items-start gap-4">
          {moon && <MoonPhaseIcon illumPct={moon.illum} waxing={/wax/i.test(moon.phase)} />}
          <div className="flex-1">
            <MetricRow label="Phase" value={moon?.phase ?? null} />
            <MetricRow label="Illumination" value={moon ? `${moon.illum.toFixed(0)}%` : null} />
            <MetricRow label="Rise / Transit / Set"
              value={moon ? [moon.rise, moon.transit, moon.set].map(x => fmtClock(x, TZ, false) ?? '—').join(' / ') : null} />
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
  const t = useTiming();
  const hist = useHistory();
  const alm = useAlmanac();
  const sun = sunOf(alm.data);
  const moon = moonOf(alm.data);
  const gps = t.core.data?.gps;
  const counts = satCounts(gps);
  const sats = gps?.sky_stale ? [] : toSkySats(gps?.sats ?? []);
  const s1h = toOffsetSeries(hist.data?.points, 3600);
  const events = allEvents(t.chain.data?.events.open, t.chain.data?.events.recent).slice(0, 5);
  const rows: [string, string | null, string?][] = [
    ['Δt (chrony)',         t.dt ? `${t.dt.value} ${t.dt.unit}` : null, t.err ? `± ${t.err}` : undefined],
    ['RMS offset',          t.rms],
    ['Δf/f',                t.frac === null ? null : fmtSci(t.frac)],
    ['Light-dist. equiv.',  t.light],
    ['PPS state',           t.ppsState],
    ['Timing status',       t.status?.code ?? null],
    ['Stratum',             t.stratum],
    ['Reference',           t.ref],
    ['SVs used / visible',  counts.used === null ? null : `${counts.used} / ${counts.visible}`],
    ['Best C/N₀',           cn0Stats(sats).best === null ? null : `${cn0Stats(sats).best} dB-Hz`],
    ['TDOP',                gps?.tdop == null ? null : String(gps.tdop)],
    ['NTP clients',         ntpClientCount(t.core.data, t.chain.data)?.toString() ?? null],
    ['Sunrise',             fmtClock(sun?.events.sunrise, TZ)],
    ['Sunset',              fmtClock(sun?.events.sunset, TZ)],
    ['Daylight',            fmtDuration(sun?.daylight_s)],
    ['Moon phase',          moon?.phase ?? null],
  ];
  return (
    <div className="page-enter">
      <div className="rounded-[2px] p-4" style={{ background:'var(--card)', border:'1px solid var(--border)', boxShadow:'inset 0 1px 0 rgba(255,255,255,0.04)' }}>
        <div className="mono text-[9px] mb-3 uppercase tracking-[0.15em]" style={{ color:'var(--t4)' }}>
          {window.location.hostname} — Engineering Console — {new Date().toISOString().replace('T',' ').slice(0,-5)} UTC
        </div>
        <div className="grid grid-cols-2 gap-x-10">
          {rows.map(([k,v,s]) => (
            <div key={k} className="flex items-baseline justify-between py-[5px] row-sep">
              <span className="mono text-[10px]" style={{ color:'var(--t3)' }}>{k}</span>
              <div className="flex items-baseline gap-2">
                {v === null
                  ? <StatusBadge variant="muted" label="UNKNOWN" dot={false} />
                  : <span className="mono tabular text-[11px] font-medium" style={{ color:'var(--t1)' }}>{v}</span>}
                {s && <span className="text-[9px]" style={{ color:'var(--t4)' }}>{s}</span>}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <div className="mono text-[9px] mb-1.5 uppercase tracking-[0.12em]" style={{ color:'var(--t3)' }}>Δt — last 1 hour ({s1h.unit})</div>
          <OffsetChart data={s1h.data} range="1h" unit={s1h.unit} />
        </div>
        <div className="mt-3 grid grid-cols-2 gap-6">
          <div>
            <div className="mono text-[9px] mb-1 uppercase tracking-[0.12em]" style={{ color:'var(--t4)' }}>Recent PPS events</div>
            {events.length === 0 && <div className="mono text-[10px]" style={{ color:'var(--t4)' }}>none recorded</div>}
            {events.map(e => (
              <div key={e.id} className="flex justify-between py-[4px] row-sep">
                <span className="mono text-[10px]" style={{ color:'var(--t3)' }}>{e.start_utc.slice(0, 16).replace('T', ' ')}</span>
                <span className="mono tabular text-[10px]" style={{ color:'var(--warn-text)' }}>{e.open ? 'OPEN · ' : ''}{fmtDuration(e.duration_s) ?? '—'}</span>
              </div>
            ))}
          </div>
          <div>
            <div className="mono text-[9px] mb-1 uppercase tracking-[0.12em]" style={{ color:'var(--t4)' }}>Sky Plot</div>
            <SkyPlot sats={plottable(sats)} hiddenNote={t.core.data?.location.mode === 'hidden' ? 'positions hidden (privacy)' : undefined} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Variant C: Minimal Precision ─────────────────────────────────────────────
function VariantC() {
  const t = useTiming();
  const hist = useHistory();
  const alm = useAlmanac();
  const sun = sunOf(alm.data);
  const moon = moonOf(alm.data);
  const gps = t.core.data?.gps;
  const s1h = toOffsetSeries(hist.data?.points, 3600);
  return (
    <div className="page-enter" style={{ maxWidth:640, margin:'0 auto', paddingTop:'2rem' }}>
      <div className="text-center mb-10">
        <div className="mono text-[9px] uppercase tracking-[0.22em] mb-3" style={{ color:'var(--t4)' }}>System clock offset (chrony)</div>
        <div className="flex items-baseline justify-center gap-3">
          <span className="mono tabular font-light" style={{ fontSize:72, lineHeight:1, color:'var(--live-bright)', letterSpacing:'-0.02em' }}>{t.dt?.value ?? '—'}</span>
          <div className="flex flex-col items-start gap-1">
            <span className="mono text-2xl font-light" style={{ color:'var(--t2)' }}>{t.dt?.unit ?? ''}</span>
            {t.err && <span className="mono text-sm" style={{ color:'var(--t4)' }}>± {t.err}</span>}
          </div>
        </div>
        <div className="mono text-[10px] mt-2" style={{ color:'var(--t4)' }}>
          {[t.light && `≡ ${t.light}`, t.status?.banner].filter(Boolean).join(' · ') || 'UNKNOWN'}
        </div>
      </div>

      <div className="mb-8">
        <OffsetChart data={s1h.data} range="1h" unit={s1h.unit} />
        <div className="text-center mono text-[9px] mt-1" style={{ color:'var(--t4)' }}>Δt — last 60 minutes ({s1h.unit})</div>
      </div>

      <div style={{ borderTop:'1px solid var(--border-dim)' }}>
        {([
          ['RMS offset (chrony)', t.rms],
          ['PPS state', t.ppsState],
          ['Fractional freq. offset', t.frac === null ? null : fmtSci(t.frac)],
          ['Satellites used / visible', satCounts(gps).used === null ? null : `${satCounts(gps).used} / ${satCounts(gps).visible}`],
          ['NTP stratum', t.stratum],
          ['NTP clients', ntpClientCount(t.core.data, t.chain.data)?.toString() ?? null],
          ['Sunrise / Sunset', sun ? `${fmtClock(sun.events.sunrise, TZ) ?? '—'} / ${fmtClock(sun.events.sunset, TZ) ?? '—'}` : null],
          ['Moon', moon ? `${moon.phase} · ${moon.illum.toFixed(0)}% illuminated` : null],
        ] as [string, string | null][]).map(([k,v]) => (
          <div key={k} className="flex justify-between py-2.5 row-sep">
            <span className="text-[12px]" style={{ color:'var(--t3)' }}>{k}</span>
            {v === null
              ? <StatusBadge variant="muted" label="UNKNOWN" dot={false} />
              : <span className="mono tabular text-[12px]" style={{ color:'var(--t1)' }}>{v}</span>}
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

export default function Overview({ onNavigate }: { onNavigate?: (id: string) => void }) {
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

      {/* Timing source and PPS state first, in every variant (CHG "Dashboard Requirement") */}
      <div className="mb-3"><TimingChainCard onOpenDiagnostics={onNavigate ? () => onNavigate('pps') : undefined} /></div>
      {/* The main clock: station time in the local zone, UTC beneath */}
      <div className="mb-3"><StationClockCard /></div>
      {variant==='A' && <VariantA />}
      {variant==='B' && <VariantB />}
      {variant==='C' && <VariantC />}
    </div>
  );
}
