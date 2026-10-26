import { Card, CardHeader, CardBody, MetricRow, ProvenanceTag, StatusBadge, ELI5 } from './ui';
import { ApiErrorNote } from './planned';
import { useStationTime } from './clock';
import { useStation, usePoll, isPending } from '../api/station';
import { clockDiscipline } from '../lib/banner';
import { formatUtc } from '../lib/localtime';
import { fmtUtc } from '../lib/format';
import { fmtExpiry, fmtScaleOffset, fmtUt1, leapLabel, leapVariant, scaleValues } from '../lib/timescales';

// ─── Time scales (/api/timescales) ───────────────────────────────────────────
export function TimeScalesPanel() {
  const { api, core, chain } = useStation();
  const ts = usePoll(() => api.timescales(), 60_000, [api]);
  const t = useStationTime();
  const d = ts.data;
  const station = t.now.basis === 'station';
  const disc = clockDiscipline(chain.data, !chain.data && !!(chain.error || core.error));
  const v = scaleValues(t.now.at, d?.tai_utc_s.value);
  const leap = d?.leap_seconds;
  const hidden = core.data?.location.mode === 'hidden';
  const taiOffset = fmtScaleOffset(d?.tai_utc_s.value);
  const gpsOffset = fmtScaleOffset(v.gpsUtcS);

  return (
    <div className="space-y-4">
      <Card pending={isPending(ts)}>
        <CardHeader title="Time Scales" badge={<ProvenanceTag type="calculated" />} />
        <CardBody>
          <ApiErrorNote error={ts.error} />
          <div className="text-[9px] mono uppercase tracking-[0.12em] mb-2"
               style={{ color: station && disc.gps ? 'var(--good-text)' : 'var(--warn-text)' }}>
            {station ? disc.label : "THIS BROWSER'S CLOCK · STATION TIME NOT MEASURED YET"}
          </div>
          <MetricRow label="UTC" value={formatUtc(t.now.at)} />
          <MetricRow label={`Local time (${t.zone.tz})`} value={`${t.local.time} · ${t.local.offset}`} />
          <MetricRow label={taiOffset ? `TAI (${taiOffset})` : 'TAI'} value={v.tai} />
          <MetricRow label={gpsOffset ? `GPS time (${gpsOffset})` : 'GPS time'} value={v.gps} />
          <MetricRow label="GPS week" value={v.gpsWeek === null ? null : `${v.gpsWeek} (broadcast: ${v.gpsWeekMod1024})`} />
          <MetricRow label="GPS seconds of week" value={v.gpsSecondsOfWeek} unit="s" />
          <MetricRow label="Unix epoch" value={v.unix} unit="s" />
          <MetricRow label="Modified Julian Date (UTC)" value={v.mjd} />
          <MetricRow label="Julian Date (UTC)" value={v.jd} />
          {hidden
            ? <div className="flex items-baseline justify-between py-[5px] row-sep">
                <span className="text-[11px]" style={{ color:'var(--t2)' }}>Local sidereal time</span>
                <StatusBadge variant="muted" label="hidden by location privacy" dot={false} />
              </div>
            : <MetricRow label="Local sidereal time (at the last update)" value={core.data?.sidereal ?? null} />}
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>
            Every scale here is calculated from the station's UTC clock, so it is as good as that clock and no better.
            TAI and GPS time add whole seconds from the leap-second table below.
            {!d && ' The station has not reported its leap-second offset, so TAI and GPS time are not shown.'}
          </div>
          <ELI5 text="UTC occasionally inserts a leap second to stay close to the Earth's rotation. TAI and GPS time never do, so they run a whole number of seconds ahead of UTC. The Julian dates count days instead of calendar dates, which makes intervals easy to subtract." />
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
        <Card pending={isPending(ts)}>
          <CardHeader title="Leap-Second Table" badge={<ProvenanceTag type="external" />}
            action={<StatusBadge variant={leapVariant(leap?.status)} label={leapLabel(leap?.status)} dot={false} />} />
          <CardBody>
            {leap?.warning && <div className="text-[10px] mb-2" style={{ color: leap.status === 'EXPIRED' ? 'var(--err-text)' : 'var(--warn-text)' }}>{leap.warning}</div>}
            <MetricRow label="Source" value={leap?.source_label ?? null} />
            <MetricRow label="File" value={leap ? (leap.path ?? 'none') : null} />
            <MetricRow label="Table updated" value={leap ? (leap.updated_utc?.slice(0, 10) ?? 'not stated') : null} />
            <MetricRow label="Table expires" value={leap ? (fmtExpiry(leap.expires_utc, leap.days_to_expiry) ?? null) : null} />
            <MetricRow label="TAI − UTC" value={d?.tai_utc_s.value ?? null} unit="s" />
            <MetricRow label="Last leap second took effect" value={leap?.last ? leap.last.utc.slice(0, 10) : null} />
            <MetricRow label="Next scheduled leap second"
              value={leap ? (leap.next ? `${leap.next.utc.slice(0, 10)} (${leap.next.kind ?? 'change'}, TAI − UTC becomes ${leap.next.tai_utc_s} s)` : (leap.next_note ?? null)) : null} />
            <MetricRow label="chrony leap status" value={leap?.chrony_leap_status.value ?? null} provenance={leap?.chrony_leap_status.value ? 'observed' : undefined} />
            <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>
              The table is published by IERS and installed with the operating system (tzdata). The station warns
              {leap ? ` ${leap.warn_days} days` : ''} before it expires.
            </div>
          </CardBody>
        </Card>

        <Card pending={isPending(ts)}>
          <CardHeader title="UT1 − UTC" badge={<ProvenanceTag type="external" />} />
          <CardBody>
            {d?.ut1.available
              ? <>
                  <MetricRow label="UT1 − UTC" value={fmtUt1(d.ut1.ut1_utc_s)} provenance="external" />
                  <MetricRow label="Kind" value={d.ut1.kind} />
                  <MetricRow label="Cached file dated" value={fmtUtc(d.ut1.file_date_utc)} />
                  <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>{d.ut1.note}</div>
                </>
              : <div className="text-[10px] py-4" style={{ color:'var(--t3)' }}>
                  Not shown. {d ? d.ut1.reason : 'Time-scale data not loaded.'}
                  {d?.ut1.file_date_utc && <span> Cached file dated {fmtUtc(d.ut1.file_date_utc)}.</span>}
                </div>}
            <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>
              UT1 follows the Earth's rotation and can only come from IERS measurements. It is shown only from a file
              the operator has placed on the station.
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
