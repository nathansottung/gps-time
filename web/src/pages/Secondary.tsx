import { Fragment, useState } from 'react';
import { Card, CardHeader, CardBody, MetricRow, StatusBadge, MaturityBadge, ELI5, ProvenanceTag, Tabs, Toggle } from '../components/ui';
import { RateChart, SolarCurve } from '../components/charts';
import { ShadowPanel, SatellitesPanel } from '../components/shadow';
import { fmtCount, fmtPerMin, fmtShare, requestSeries, serviceLabel, serviceVariant } from '../lib/ntpservice';
import { Planned, ApiErrorNote } from '../components/planned';
import { Sensitive } from '../components/screenshot';
import { useStation, usePoll, useBrowserClock, isPending } from '../api/station';
import { allEvents, ntpClientCount } from '../api/view';
import type { AdminAction, AdminResult, AuthState, LocationMode, LunarDay, SettingResult, SolarDay, SurveyStats } from '../api/types';
import { ApiError } from '../api/client';
import { STATION_ACTIONS, actionInfo, actionOutcome, type ActionOutcome } from '../lib/admin';
import { RESET_WORD, resetConfirmed, resetOutcome, surveyLoss, type ResetOutcome } from '../lib/survey';
import { throttleRows, underVoltage } from '../lib/throttle';
import { canToggle, outputHeading, outputLines, permissionText, rowStatus, settingOutcome, switchConfirm, type Outcome as ModOutcome } from '../lib/modules';
import type { Polled } from '../api/station';
import { adsbStats, dataPacks } from '../api/previews';
import { ModuleReadiness, ModuleSettings, SdrReceivers } from '../components/sdr';
import { CapabilityCard } from '../components/skymap';
import { FeedersCard } from '../components/feeders';
import { SunDays, MoonPhaseIcon } from './Overview';
import { DateNav, DayBarCard, NightCard } from '../components/almanac';
import { timeOnDay, todayIn } from '../lib/almanac';
import { ObjectLookupCard, SkyMapCard } from '../components/sky';
import { atParam } from '../lib/sky';
import { browserTimeZone, fmtClock, fmtDuration, fmtUtc } from '../lib/format';
import { isValidZone, resolveZone, zoneNames } from '../lib/localtime';

const TZ = browserTimeZone();

// ─── Sun & Astronomy ──────────────────────────────────────────────────────────
export function SunAstronomy() {
  const [safetyAck, setSafetyAck] = useState(false);
  const [tab, setTab] = useState('Sun & Moon');
  const { api, core } = useStation();
  // Date navigation (parity 8): any date the ephemeris covers; times in the browser's zone.
  const today = todayIn(TZ);
  const [date, setDate] = useState(today);
  const isToday = date === today;
  // Sky map time (parity 11): now on today's date, else a chosen time (22:00 by default). The target is
  // this page's own lookup, sent with each request; the station keeps none (parity 12, GPS-030).
  const [useNow, setUseNow] = useState(true);
  const [skyTime, setSkyTime] = useState('22:00');
  const [target, setTarget] = useState('');
  const at = atParam(useNow && isToday, skyTime);
  const skyTab = tab === 'Sky & Objects';
  const alm = usePoll(() => api.almanac({ tz: TZ, date, at, target: target || undefined }),
    skyTab && at === 'now' ? 60_000 : 10 * 60_000, [api, date, at, target]);
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
      <Tabs tabs={['Sun & Moon', 'Sky & Objects', 'Earth Shadow', 'Satellites']} active={tab} onChange={setTab} />

      {skyTab && <>
        <div className="flex items-center gap-3 flex-wrap">
          <DateNav date={date} today={today} onChange={setDate} />
          <div className="flex items-center gap-1.5">
            <span className="text-[10px]" style={{ color:'var(--t3)' }}>Sky at</span>
            <input type="time" step={60} value={at === 'now' ? '' : skyTime} aria-label="Sky map time"
              onChange={e => { setSkyTime(e.target.value); setUseNow(false); }}
              className="mono tabular text-[11px] px-2 py-1 rounded-[2px]" style={{ background:'var(--bg)', border:'1px solid var(--border)', color:'var(--t1)', colorScheme:'dark' }} />
            <button onClick={() => { setDate(today); setUseNow(true); }} disabled={at === 'now'}
              className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={{ border:'1px solid var(--border)', color:'var(--t2)' }}>Now</button>
          </div>
        </div>
        <ApiErrorNote error={alm.error} />
        {unavailable && <div className="text-[11px]" style={{ color:'var(--t3)' }}>Almanac unavailable: {unavailable}</div>}
        <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
          <SkyMapCard sky={a?.sky} when={a?.sky_when ?? null} demo={a?.demo} />
          <ObjectLookupCard date={date} tz={TZ} at={at} onTarget={setTarget} />
        </div>
        {a?.location_display === 'rounded' && <div className="text-[9px]" style={{ color:'var(--t3)' }}>Computed for the rounded-[2px] site (~11 km), per the privacy setting.</div>}
      </>}
      {tab === 'Earth Shadow' && <ShadowPanel />}
      {tab === 'Satellites' && <SatellitesPanel />}

      {tab === 'Sun & Moon' && <>
      <DateNav date={date} today={today} onChange={setDate} />
      <ApiErrorNote error={alm.error} />
      {unavailable && <div className="text-[11px]" style={{ color:'var(--t3)' }}>Almanac unavailable: {unavailable}</div>}

      <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
        <Card>
          <CardHeader title={isToday ? 'Sun / Daylight — Yesterday / Today / Tomorrow' : `Sun / Daylight — around ${date}`} badge={<ProvenanceTag type="predicted" />} />
          <CardBody>
            <SunDays almanac={a} labels={isToday ? undefined : ['Day before', date, 'Day after']} />
            <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>
              Times in {TZ}.{a?.location_display === 'rounded' && ' Computed for the rounded-[2px] site (~11 km), per the privacy setting.'}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title={`Twilight (${isToday ? 'today' : date})`} badge={<ProvenanceTag type="predicted" />} />
          <CardBody>
            <MetricRow label="Astronomical dawn" value={fmtClock(sun?.events.astro_dawn, TZ)} />
            <MetricRow label="Nautical dawn" value={fmtClock(sun?.events.naut_dawn, TZ)} />
            <MetricRow label="Civil dawn" value={fmtClock(sun?.events.civil_dawn, TZ)} />
            <MetricRow label="Civil dusk" value={fmtClock(sun?.events.civil_dusk, TZ)} />
            <MetricRow label="Nautical dusk" value={fmtClock(sun?.events.naut_dusk, TZ)} />
            <MetricRow label="Astronomical dusk" value={fmtClock(sun?.events.astro_dusk, TZ)} />
            {sun?.notes.map(n => <div key={n} className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>{n}</div>)}
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
        <DayBarCard sun={sun} tz={TZ} />
        <NightCard almanac={a} day={date} tz={TZ} />
      </div>

      <Planned title="Solar Position & Solar-Equivalent Time" needs="solar position and equation-of-time in the almanac API">
      <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
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
            <div className="p-3 rounded-[2px]" style={{ background:'rgba(255,255,255,0.018)', border:'1px solid var(--border-dim)' }}>
              <div className="text-[10px] mb-1" style={{ color:'var(--t3)' }}>Equivalent civil time on target date (same solar phase)</div>
              <div className="mono tabular text-base" style={{ color:'var(--t1)' }}>08:14:33</div>
            </div>
          </CardBody>
        </Card>
      </div>
      </Planned>

      <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
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
                <MetricRow label="Moonrise" value={moon ? timeOnDay(moon.rise, date, TZ) ?? 'none this day' : null} />
                <MetricRow label="Lunar transit" value={moon ? timeOnDay(moon.transit, date, TZ) ?? 'none this day' : null} />
                <MetricRow label="Transit altitude" value={moon?.transit_alt == null ? null : `${moon.transit_alt.toFixed(1)}°`} />
                <MetricRow label="Moonset" value={moon ? timeOnDay(moon.set, date, TZ) ?? 'none this day' : null} />
                <MetricRow label="Above the horizon" value={moon?.up_s == null ? null : fmtDuration(moon.up_s)} />
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
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
                <div key={e.event} className="p-2 rounded-[2px] text-[11px]" style={{ background:'var(--bg)', border:'1px solid var(--border)' }}>
                  <div className="flex justify-between"><span style={{ color:'var(--t2)' }}>{e.event}</span><span className="mono" style={{ color:'var(--live)' }}>{e.time}</span></div>
                  <div className="text-[10px]" style={{ color:'var(--t3)' }}>Duration: {e.dur} · {e.note}</div>
                </div>
              ))}
            </div>
            {!safetyAck ? (
              <div className="mt-3 p-2 rounded-[2px]" style={{ background:'var(--warn-bg)', border:'1px solid var(--warn-border)', color:'var(--warn-text)' }}>
                <div className="text-[10px] mb-2">Solar transit predictions are disabled until you acknowledge safe observing requirements.</div>
                <button onClick={() => setSafetyAck(true)}
                  className="px-3 py-1 text-[10px] mono rounded-[2px]" style={{ border:'1px solid var(--warn-border)', color:'var(--warn-text)' }}>
                  I understand the hazard and am responsible for safe equipment
                </button>
              </div>
            ) : (
              <div className="mt-2 text-[10px]" style={{ color:'var(--good-text)' }}>Solar transit predictions enabled. You are responsible for safe equipment.</div>
            )}
          </CardBody>
        </Card>
        </Planned>
      </div>
      </>}
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
  const { api, core, chain } = useStation();
  const clk = useBrowserClock();
  const ntp = usePoll(() => api.ntpService(), 30_000, [api]);
  const svc = ntp.data;
  const reqSeries = requestSeries(svc?.history);
  const q = core.data?.quality;
  const clients = core.data?.clients ?? [];
  const status = chain.data?.status;
  const fmtMs = (v: number | null) => (v === null ? null : `${v.toFixed(1)} ms`);
  return (
    <div className="space-y-4 page-enter">
      <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Network & Devices</h1>
      <ApiErrorNote error={core.error} />

      <div className="grid grid-cols-1 @2xl:grid-cols-2 @5xl:grid-cols-3 gap-4">
        <Card>
          <CardHeader title="NTP Server (chrony)" />
          <CardBody>
            <MetricRow label="Timing status" value={status?.headline ?? null} provenance="calculated" />
            <MetricRow label="Stratum" value={q?.stratum ?? null} />
            <MetricRow label="Reference" value={q?.reference ?? null} />
            <MetricRow label="Leap status" value={q?.leap ?? null} />
            <MetricRow label="Clients seen" value={ntpClientCount(core.data, chain.data)} provenance="observed" />
            <MetricRow label="Request rate (last minute)" value={fmtPerMin(ntp.data?.rates?.last_minute.received_per_s.value)} provenance="calculated" />
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
            <div className="text-[9px] mono mt-1" style={{ color:'var(--t3)' }}>{clk.samples.length} samples · positive = browser ahead of station</div>
            <ELI5 text="Using a four-timestamp exchange (like NTP), the browser's clock offset can be estimated. Accuracy is limited by asymmetric network paths and browser timer resolution." />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Offline Status" />
          <CardBody>
            <MetricRow label="Internet" value={null} />
            <MetricRow label="Local timing" value={status?.headline ?? null} />
            <MetricRow label="GNSS fix" value={core.data ? (core.data.gps.stale ? 'STALE' : core.data.gps.fix) : null} />
            <div className="mt-3 text-[10px]" style={{ color:'var(--t3)' }}>
              The station does not probe Internet connectivity, so it is shown as UNKNOWN. Timing does not depend on it.
            </div>
          </CardBody>
        </Card>
      </div>

      <Card pending={isPending(ntp)}>
        <CardHeader title="NTP Service (chrony serverstats)" badge={<ProvenanceTag type="observed" />}
          action={<StatusBadge variant={serviceVariant(svc?.state)} label={serviceLabel(svc?.state)} dot={false} />} />
        <CardBody>
          <ApiErrorNote error={ntp.error} />
          {svc && !svc.available && <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>{svc.reason}</div>}
          <div className="grid grid-cols-1 @md:grid-cols-2 gap-6">
            <div>
              <MetricRow label="NTP packets received" value={fmtCount(svc?.ntp?.received.value)} provenance="observed" />
              <MetricRow label="Dropped (chrony rate limit)" value={fmtCount(svc?.ntp?.dropped.value)} provenance="observed" />
              <MetricRow label="Not dropped (received − dropped)" value={fmtCount(svc?.ntp?.not_dropped.value)} provenance="calculated" />
              <MetricRow label="Share dropped" value={fmtShare(svc?.ntp?.drop_fraction.value)} provenance="calculated" />
              <MetricRow label="Requests, last minute" value={fmtPerMin(svc?.rates?.last_minute.received_per_s.value)} provenance="calculated" />
              <MetricRow label="Requests, last hour" value={fmtPerMin(svc?.rates?.last_hour.received_per_s.value)} provenance="calculated" />
              <MetricRow label="Dropped, last hour" value={fmtPerMin(svc?.rates?.last_hour.dropped_per_s.value)} provenance="calculated" />
            </div>
            <div>
              <div className="text-[10px] mb-1" style={{ color:'var(--t3)' }}>Requests per minute</div>
              {reqSeries.length
                ? <RateChart data={reqSeries} range="24h" unit="/min" />
                : <div className="text-[10px] py-10 text-center" style={{ color:'var(--t3)' }}>
                    {svc?.available ? 'No history yet (one sample a minute).' : 'UNKNOWN'}
                  </div>}
            </div>
          </div>
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>
            Totals count from when chronyd started{svc?.counter_resets ? ` (it restarted ${svc.counter_resets} time(s) while the station was watching)` : ''}.
            chrony does not count the replies it sent, so "not dropped" is the nearest figure to requests served.
            {svc?.state_basis ? ` Status is judged ${svc.state_basis}.` : ''}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="NTP Clients" badge={<ProvenanceTag type="observed" />} />
        <CardBody className="p-0">
          <div className="px-4 py-2 text-[10px]" style={{ borderBottom:'1px solid var(--border-dim)', color:'var(--t3)' }}>
            From chronyc clients. Polling this server does not prove the client clock is accurate.
          </div>
          <div className="table-scroll"><table className="w-full text-[11px]">
            <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
              {['Host','NTP packets','Dropped','Last request'].map(h=>(
                <th key={h} className="text-left px-4 py-2 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {clients.map(c => (
                <tr key={c.host} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}><Sensitive>{c.host}</Sensitive></td>
                  <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>{c.ntp_packets.toLocaleString()}</td>
                  <td className="px-4 py-2 mono tabular" style={{ color:'var(--t3)' }}>{c.dropped}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{/^\d+$/.test(c.last) ? `${fmtDuration(Number(c.last))} ago` : c.last}</td>
                </tr>
              ))}
              {!clients.length && <tr><td colSpan={4} className="px-4 py-3 text-[10px]" style={{ color:'var(--t3)' }}>
                {!core.data ? (core.error ? 'Not available: the station did not answer.' : 'Loading…') : ntpClientCount(core.data, chain.data) === null ? 'chronyc not available: client list UNKNOWN.' : 'No NTP clients reported.'}</td></tr>}
            </tbody>
          </table></div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="chrony Sources" badge={<ProvenanceTag type="observed" />} />
        <CardBody className="p-0">
          <div className="table-scroll"><table className="w-full text-[11px]">
            <thead><tr style={{ borderBottom:'1px solid var(--border)' }}>
              {['Name','State','Stratum','Poll','Reach','Last rx','Last sample'].map(h=>(
                <th key={h} className="text-left px-4 py-2 font-normal" style={{ color:'var(--t3)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {(core.data?.sources ?? []).map(s => (
                <tr key={s.name} style={{ borderBottom:'1px solid var(--border-dim)' }}>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}>
                    {s.is_self ? <Sensitive>{s.name}</Sensitive> : s.name}
                    {s.is_self && <span style={{ color:'var(--warn-text)' }} title="chrony is polling this station's own address (usually from DHCP). It is not an external reference."> · THIS STATION</span>}
                  </td>
                  <td className="px-4 py-2 mono" style={{ color: s.state === '*' && !s.is_self ? 'var(--good-text)' : s.is_self ? 'var(--warn-text)' : 'var(--t3)' }}>{s.state} {s.state_label}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{s.stratum}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{2 ** s.poll} s</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{s.reach}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{s.lastrx}</td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t2)' }}>{s.sample}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
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
      <div className="grid grid-cols-1 @2xl:grid-cols-2 @5xl:grid-cols-3 gap-4">
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
                <div key={s.label} className="p-2 rounded-[2px]" style={{ background:'var(--bg)', border:'1px solid var(--border)' }}>
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

      <div className="p-3 rounded-[2px] text-[11px]" style={{ background:'var(--mod-bg)', border:'1px solid var(--mod-border)', color:'var(--mod-text)' }}>
        This is a future research area. Features shown below are conceptual designs and are not yet implemented. No data is transmitted without explicit per-request consent.
      </div>

      <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
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
                <div className="mb-3 p-2 rounded-[2px] text-[10px]" style={{ background:'var(--bg)', border:'1px solid var(--border)' }}>
                  <div className="font-medium mb-1.5" style={{ color:'var(--t3)' }}>Privacy settings for this request</div>
                  {['Share derived result (Doppler shift)', 'Use exact coordinates for solver', 'Raw IQ — local only, no upload'].map(p => (
                    <label key={p} className="flex items-center gap-2 py-0.5 cursor-pointer" style={{ color:'var(--t3)' }}>
                      <input type="checkbox" defaultChecked={p.includes('derived')} className="accent-cyan-400" />
                      {p}
                    </label>
                  ))}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => setReqState('accepted')} className="px-4 py-1.5 text-[11px] mono rounded-[2px]" style={{ background:'var(--good-bg)', border:'1px solid var(--good-border)', color:'var(--good-text)' }}>ACCEPT</button>
                  <button onClick={() => setReqState('declined')} className="px-4 py-1.5 text-[11px] mono rounded-[2px]" style={{ background:'var(--err-bg)', border:'1px solid var(--err-border)', color:'var(--err-text)' }}>DECLINE</button>
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

      <div className="grid grid-cols-1 @2xl:grid-cols-2 @5xl:grid-cols-3 gap-4">
        <Card pending={isPending(sys)}>
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
            {!events.length && <div className="px-3 py-3 text-[10px]" style={{ color:'var(--t3)' }}>{chain.data ? 'No events recorded.' : chain.error ? 'Not available: the station did not answer.' : 'Loading…'}</div>}
          </CardBody>
        </Card>
      </div>

      <Planned title="Offline Data Packs" needs="a data-pack manifest endpoint">
      <Card>
        <CardHeader title="Offline Data Packs" />
        <CardBody className="p-0">
          <div className="table-scroll"><table className="w-full text-[11px]">
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
          </table></div>
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
  const throttle = throttleRows(s?.throttled);
  const uv = underVoltage(throttle);
  return (
    <div className="space-y-4 page-enter">
      <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Administration / System</h1>
      <ApiErrorNote error={sys.error} />

      <div className="grid grid-cols-1 @2xl:grid-cols-2 @5xl:grid-cols-3 gap-4">
        <Card pending={isPending(sys)}>
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
        <Card pending={isPending(sys)}>
          <CardHeader title="Power" badge={<ProvenanceTag type="observed" />} />
          <CardBody>
            <MetricRow label="Core voltage" value={s?.core_volts ?? null} />
            <MetricRow label="Input power" value={s?.power ? s.power.watts : null} unit="W" />
            {/* get_throttled, decoded by the station (parity 21): every condition, now and since boot */}
            {!throttle ? <MetricRow label="Throttle flags" value={null} /> : <>
              <div className="table-scroll"><table className="w-full text-[11px] mt-2">
                <thead><tr>
                  {['Condition', 'Now', 'Since boot'].map((h, i) => (
                    <th key={h} className={`py-1 font-normal ${i ? 'text-right' : 'text-left'}`} style={{ color:'var(--t3)', fontSize:10 }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {throttle.map(r => (
                    <tr key={r.condition} className="row-sep">
                      <td className="py-1" style={{ color:'var(--t2)' }}>{r.condition}</td>
                      {[r.now, r.sinceBoot].map((v, i) => (
                        <td key={i} className="py-1 mono text-right"
                          style={{ color: v === null ? 'var(--t3)' : !v ? 'var(--t3)' : i === 0 ? 'var(--err-text)' : 'var(--warn-text)' }}>
                          {v === null ? '—' : v ? 'YES' : 'no'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <div className="text-[9px] mono mt-1" style={{ color:'var(--t3)' }}>get_throttled = {s?.throttled?.raw}</div>
              {uv?.ever && (
                <div className="text-[10px] mt-2 rounded-[2px] p-2" style={uv.now
                  ? { color:'var(--err-text)', background:'var(--err-bg)', border:'1px solid var(--err-border)' }
                  : { color:'var(--warn-text)', background:'var(--warn-bg)', border:'1px solid var(--warn-border)' }}>
                  {uv.now ? 'Under-voltage now.' : 'Under-voltage occurred since boot.'} An unsteady supply can disturb the
                  Pi's clock and the GNSS receiver; check the power supply and cable before reading timing results.
                </div>
              )}
            </>}
            {s?.power_note && <div className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>{s.power_note}</div>}
          </CardBody>
        </Card>
      </div>

      <AdminAccess auth={auth} />

      <StationActions canWrite={canWrite} authKnown={!!auth.data} onAuthError={auth.refresh} />

      <ExperimentalModules canWrite={canWrite} authKnown={!!auth.data} onAuthError={auth.refresh} />

      <SdrReceivers />
      <FeedersCard canWrite={canWrite} authKnown={!!auth.data} onAuthError={auth.refresh} />

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
            <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>Changing this needs the admin token (Admin access, above).</div>
          )}
          {msg && <div className="text-[10px] mono mt-2" style={{ color:'var(--t3)' }}>{msg}</div>}
        </CardBody>
      </Card>

      <CapabilityCard canWrite={canWrite} authKnown={!!auth.data} onAuthError={auth.refresh} />

      <Card>
        <CardHeader title="Local time zone" badge={shownZone.source === 'position' ? <ProvenanceTag type="calculated" /> : undefined} />
        <CardBody>
          <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>
            The zone the main clock shows local time in. Display only: the station's clock, logs and API stay on UTC.
          </div>
          <MetricRow label="Shown in" value={core.data ? shownZone.tz : null} />
          <MetricRow label="Source" value={core.data ? shownZone.label : null} />
          {stationZone && !stationZone.source && (
            <div className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>Station: {stationZone.note}.</div>
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
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>
            Automatic: the zone is found offline from the station's position. With the location hidden it is not derived from the position;
            the override, or each browser's own zone, is used instead.
          </div>
          {!canWrite && auth.data && (
            <div className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>Changing this needs the admin token (Admin access, above).</div>
          )}
          {tzMsg && <div className="text-[10px] mono mt-2" style={{ color:'var(--t3)' }}>{tzMsg}</div>}
        </CardBody>
      </Card>

      <SurveyReset survey={core.data?.survey} canWrite={canWrite} authKnown={!!auth.data}
        onDone={core.refresh} onAuthError={auth.refresh} />

      <Planned title="Services & Network" needs="service and interface status endpoints">
      <Card>
        <CardHeader title="Services" />
        <CardBody className="p-0">
          <div className="table-scroll"><table className="w-full text-[11px]">
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
          </table></div>
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
      </CardBody>
    </Card>
  );
}

// ─── Station actions (POST /api/admin; lib/admin.ts) ──────────────────────────
const OUTCOME_COLOR: Record<ActionOutcome['variant'], string> = {
  good: 'var(--good-text)', warn: 'var(--warn-text)', error: 'var(--err-text)', muted: 'var(--t3)',
};

function StationActions({ canWrite, authKnown, onAuthError }: { canWrite: boolean; authKnown: boolean; onAuthError: () => void }) {
  const { api } = useStation();
  const [pending, setPending] = useState<AdminAction | null>(null);   // waiting for confirmation
  const [busy, setBusy] = useState<AdminAction | null>(null);
  const [outcome, setOutcome] = useState<ActionOutcome | null>(null);
  const run = async (a: AdminAction) => {
    setPending(null); setBusy(a); setOutcome(null);
    try {
      const r: AdminResult = await api.admin(a);
      setOutcome(actionOutcome(a, r));
    } catch (e) {
      const status = e instanceof ApiError ? e.status : null;
      setOutcome(actionOutcome(a, null, { message: (e as Error).message, status }));
      if (status === 401 || status === 403) onAuthError();
    } finally { setBusy(null); }
  };
  const click = (a: AdminAction) => { if (actionInfo(a).confirm) { setPending(a); setOutcome(null); } else run(a); };
  const btn = (active: boolean) => active
    ? { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }
    : { border:'1px solid var(--border)', color:'var(--t2)' };
  const p = pending ? actionInfo(pending) : null;
  return (
    <Card>
      <CardHeader title="Station actions" />
      <CardBody>
        <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>
          These run on the station immediately. Each is a fixed command; nothing typed here is passed to it.
        </div>
        <div className="flex flex-wrap gap-1.5">
          {STATION_ACTIONS.map(a => (
            <button key={a.action} onClick={() => click(a.action)} disabled={!canWrite || busy !== null}
              title={a.effect} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn(pending === a.action || busy === a.action)}>
              {busy === a.action ? `${a.label}…` : a.label}
            </button>
          ))}
        </div>
        {p && (
          <div role="alertdialog" aria-label={`Confirm: ${p.label}`} className="mt-3 rounded-[2px] p-3"
            style={{ background:'var(--warn-bg)', border:'1px solid var(--warn-border)' }}>
            <div className="text-[11px] mb-2" style={{ color:'var(--t1)' }}>{p.confirm}</div>
            <div className="flex gap-1.5">
              <button onClick={() => run(p.action)} className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
                style={{ border:'1px solid var(--warn-border)', color:'var(--warn-text)' }}>Confirm: {p.label}</button>
              <button onClick={() => setPending(null)} autoFocus className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn(false)}>Cancel</button>
            </div>
          </div>
        )}
        {outcome && <div className="text-[10px] mono mt-2" role="status" style={{ color: OUTCOME_COLOR[outcome.variant] }}>{outcome.text}</div>}
        {!canWrite && authKnown && (
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>These need the admin token (Admin access, above).</div>
        )}
        <div className="mt-3 space-y-[2px]">
          {STATION_ACTIONS.map(a => (
            <div key={a.action} className="text-[10px]" style={{ color:'var(--t3)' }}>
              <span style={{ color:'var(--t3)' }}>{a.label}:</span> {a.effect}
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Experimental modules (GET /api/modules, POST /api/setting; lib/modules.ts) ─
const MOD_COLOR: Record<ModOutcome['variant'], string> = {
  good: 'var(--good-text)', warn: 'var(--warn-text)', error: 'var(--err-text)', muted: 'var(--t3)',
};

function ExperimentalModules({ canWrite, authKnown, onAuthError }: { canWrite: boolean; authKnown: boolean; onAuthError: () => void }) {
  const { api } = useStation();
  const mods = usePoll(() => api.modules(), 10_000, [api]);
  const s = mods.data;
  const [pending, setPending] = useState<boolean | null>(null);   // the switch value waiting for confirmation
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<ModOutcome | null>(null);
  const send = async (what: string, call: () => Promise<SettingResult>) => {
    setBusy(true); setOutcome(null);
    try {
      setOutcome(settingOutcome(what, await call()));
    } catch (e) {
      const status = e instanceof ApiError ? e.status : null;
      setOutcome(settingOutcome(what, null, { message: (e as Error).message, status }));
      if (status === 401 || status === 403) onAuthError();
    } finally { setBusy(false); mods.refresh(); }
  };
  const flip = (on: boolean) => {
    setPending(null);
    send(on ? 'Experimental modules on' : 'Experimental modules off', () => api.setModulesExperimental(on));
  };
  const btn = { border:'1px solid var(--border)', color:'var(--t2)' };
  return (
    <Card>
      <CardHeader title="Experimental modules" badge={<MaturityBadge level="experimental" />} />
      <CardBody>
        <ApiErrorNote error={mods.error} />
        <div className="text-[10px] mb-3" style={{ color:'var(--t3)' }}>
          Optional modules (sensors, reference signals, analyses) run outside the timing core, each in its own sandboxed process.
          They are off by default. Turning this switch on starts none of them: each module stays off until it is turned on by itself below.
        </div>
        <div className="flex items-center gap-3">
          <Toggle on={!!s?.experimental} label="Experimental modules" disabled={!s || !canWrite || busy}
            onChange={v => { setPending(v); setOutcome(null); }} />
          <span className="text-[11px]" style={{ color:'var(--t2)' }}>
            {!s ? (mods.error ? 'UNKNOWN' : '…') : s.experimental ? 'On: a module runs once it is turned on below' : 'Off: no module runs'}
          </span>
        </div>
        {pending !== null && (
          <div role="alertdialog" aria-label="Confirm experimental modules switch" className="mt-3 rounded-[2px] p-3"
            style={{ background:'var(--warn-bg)', border:'1px solid var(--warn-border)' }}>
            <div className="text-[11px] mb-2" style={{ color:'var(--t1)' }}>{switchConfirm(pending)}</div>
            <div className="flex gap-1.5">
              <button onClick={() => flip(pending)} className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
                style={{ border:'1px solid var(--warn-border)', color:'var(--warn-text)' }}>Confirm: turn {pending ? 'on' : 'off'}</button>
              <button onClick={() => setPending(null)} autoFocus className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Cancel</button>
            </div>
          </div>
        )}
        {s && s.modules.length === 0 && (
          <div className="text-[10px] mt-3" style={{ color:'var(--t3)' }}>
            No modules are installed on this station. install.sh copies the bundled ones to /opt/gps-time-pi/modules; adding another: docs/modules/README.md.
          </div>
        )}
        {s && s.modules.length > 0 && (
          <div className="table-scroll"><table className="w-full text-[11px] mt-3">
            <thead><tr>
              {['Module', 'Maturity', 'Needs', 'Status', 'On'].map((h, i) => (
                <th key={h} className={`py-1 font-normal ${i === 4 ? 'text-right' : 'text-left'}`} style={{ color:'var(--t3)', fontSize:10 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {s.modules.map(r => {
                const st = rowStatus(r, s);
                return (
                  <Fragment key={r.name}>
                  <tr className="row-sep align-top">
                    <td className="py-1.5 pr-2">
                      <div className="mono" style={{ color:'var(--t1)' }}>{r.name}{r.version && <span style={{ color:'var(--t3)' }}> {r.version}</span>}</div>
                      {r.summary && <div className="text-[10px]" style={{ color:'var(--t3)' }}>{r.summary}</div>}
                      {r.errors.map(e => <div key={e} className="text-[10px] mono" style={{ color:'var(--err-text)' }}>{e}</div>)}
                      {r.reason && <div className="text-[10px] mono" style={{ color:'var(--t3)' }}>{r.reason}</div>}
                    </td>
                    <td className="py-1.5 pr-2">{r.maturity ? <MaturityBadge level={r.maturity} /> : <span style={{ color:'var(--t3)' }}>—</span>}</td>
                    <td className="py-1.5 pr-2 text-[10px]" style={{ color:'var(--t3)' }}>{permissionText(r)}</td>
                    <td className="py-1.5 pr-2"><StatusBadge variant={st.variant} label={st.label} dot={false} className="text-[9px]" /></td>
                    <td className="py-1.5 text-right">
                      <Toggle on={r.enabled} label={`Module ${r.name}`} disabled={busy || !canToggle(r, s, canWrite)}
                        onChange={v => send(`${r.name} ${v ? 'on' : 'off'}`, () => api.setModule(r.name, v))} />
                    </td>
                  </tr>
                  {(r.readiness?.length || Object.keys(r.config_schema ?? {}).length > 0) && (
                    <tr className="row-sep">
                      <td colSpan={5} className="pb-1">
                        <ModuleReadiness row={r} />
                        <ModuleSettings row={r} canWrite={canWrite} busy={busy} send={send} />
                      </td>
                    </tr>
                  )}
                  {r.latest && (
                    <tr className="row-sep">
                      <td colSpan={5} className="pb-2">
                        <div className="text-[10px] mb-1" style={{ color:'var(--t3)' }}>{outputHeading(r.latest)}</div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6" aria-label={`Latest output of ${r.name}`}>
                          {outputLines(r.latest).map(l => (
                            <div key={l.name} title={l.note}>
                              <MetricRow label={l.name} value={l.value} unit={l.unit} provenance={l.provenance} />
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                  </Fragment>
                );
              })}
            </tbody>
          </table></div>
        )}
        {outcome && <div className="text-[10px] mono mt-2" role="status" style={{ color: MOD_COLOR[outcome.variant] }}>{outcome.text}</div>}
        {s && (
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>
            Supervisor: {s.supervisor.detail}. {s.note} A module that needs a device or the network also needs a drop-in for gps-time-modules.service (GTP_SDR=1 adds the one for 127.0.0.1).
          </div>
        )}
        {!canWrite && authKnown && (
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>Changing these needs the admin token (Admin access, above).</div>
        )}
      </CardBody>
    </Card>
  );
}

// ─── Position survey reset (POST /api/setting {reset_site}; lib/survey.ts) ───
const RESET_COLOR: Record<ResetOutcome['variant'], string> = { good: 'var(--good-text)', warn: 'var(--warn-text)', error: 'var(--err-text)' };

function SurveyReset({ survey, canWrite, authKnown, onDone, onAuthError }: {
  survey: SurveyStats | undefined; canWrite: boolean; authKnown: boolean; onDone: () => void; onAuthError: () => void;
}) {
  const { api } = useStation();
  const [open, setOpen] = useState(false);
  const [word, setWord] = useState('');
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<ResetOutcome | null>(null);
  const close = () => { setOpen(false); setWord(''); };
  const reset = async () => {
    if (!resetConfirmed(word)) return;
    setBusy(true); setOutcome(null);
    try {
      setOutcome(resetOutcome(await api.resetSite()));
    } catch (e) {
      const status = e instanceof ApiError ? e.status : null;
      setOutcome(resetOutcome(null, { message: (e as Error).message, status }));
      if (status === 401 || status === 403) onAuthError();
    } finally { setBusy(false); close(); onDone(); }
  };
  const btn = { border:'1px solid var(--border)', color:'var(--t2)' };
  return (
    <Card>
      <CardHeader title="Position survey" />
      <CardBody>
        <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>
          The station averages its fixes into one surveyed position. Reset it only if the antenna has moved: the averaged fixes are discarded and cannot be restored from here.
        </div>
        <MetricRow label="Accepted fixes" value={survey ? survey.n.toLocaleString() : null} provenance="observed" />
        <MetricRow label="Horizontal SE of mean" value={survey?.se_horiz_m == null ? null : `±${survey.se_horiz_m.toFixed(2)} m`} provenance="calculated" />
        {!open && (
          <button onClick={() => { setOpen(true); setOutcome(null); }} disabled={!canWrite || busy}
            className="mt-3 px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Reset position survey…</button>
        )}
        {open && (
          <div role="alertdialog" aria-label="Confirm survey reset" className="mt-3 rounded-[2px] p-3"
            style={{ background:'var(--err-bg)', border:'1px solid var(--err-border)' }}>
            <div className="text-[11px] mb-2" style={{ color:'var(--t1)' }}>{surveyLoss(survey)}</div>
            <div className="text-[10px] mb-2" style={{ color:'var(--t3)' }}>Type <span className="mono" style={{ color:'var(--t1)' }}>{RESET_WORD}</span> to confirm.</div>
            <div className="flex gap-1.5 items-center">
              <input value={word} onChange={e => setWord(e.target.value)} autoFocus autoComplete="off" spellCheck={false}
                aria-label={`Type ${RESET_WORD} to confirm`} onKeyDown={e => { if (e.key === 'Enter') reset(); if (e.key === 'Escape') close(); }}
                className="mono text-[11px] px-2 py-1 rounded-[2px] w-28" style={{ background:'var(--bg)', border:'1px solid var(--border)', color:'var(--t1)' }} />
              <button onClick={reset} disabled={!resetConfirmed(word) || busy} className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
                style={{ border:'1px solid var(--err-border)', color:'var(--err-text)' }}>{busy ? 'Resetting…' : 'Reset survey'}</button>
              <button onClick={close} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>Cancel</button>
            </div>
          </div>
        )}
        {outcome && <div className="text-[10px] mono mt-2" role="status" style={{ color: RESET_COLOR[outcome.variant] }}>{outcome.text}</div>}
        {!canWrite && authKnown && (
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>This needs the admin token (Admin access, above).</div>
        )}
      </CardBody>
    </Card>
  );
}
