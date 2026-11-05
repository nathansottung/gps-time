// Radio & SDR → Aircraft decoders: readsb (1090 MHz) with tar1090, dump978-fa and skyaware978 (978 MHz)
// with its map, the dongle serial each one uses, messages per second and aircraft count
// (GET /api/sdr → aircraft). Read only. Logic: lib/aircraftstack.ts.
import { Card, CardHeader, CardBody, MaturityBadge, MetricRow, StatusBadge } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll } from '../api/station';
import type { SdrAircraftDecoder } from '../api/types';
import { decoderState, fmtRate, mapLine, rateLine, serialLine, unitsLine } from '../lib/aircraftstack';
import { ageLine } from '../lib/aircraftmap';

function Decoder({ d, isDemo }: { d: SdrAircraftDecoder; isDemo: boolean }) {
  const st = decoderState(d);
  const map = mapLine(d);
  return (
    <div className="p-3 rounded-[2px]" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
        <span className="text-[12px] font-medium" style={{ color: 'var(--t1)' }}>{d.band} MHz · {d.decoder}</span>
        <StatusBadge variant={st.variant} label={st.label} />
      </div>
      <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>{st.text}</div>
      <MetricRow label="Dongle serial" value={serialLine(d)} provenance="observed" />
      <MetricRow label="Units" value={unitsLine(d)} provenance="observed" />
      <MetricRow label="Messages" value={fmtRate(rateLine(d))} unit="msg/s" provenance="calculated" />
      <MetricRow label="Aircraft" value={d.feed?.aircraft.value} provenance="observed" />
      <MetricRow label="Data age" value={ageLine(d.feed?.age_s.value ?? null)} provenance="observed" />
      <div className="flex flex-wrap items-center gap-2 mt-2 text-[10px]">
        {map.link && !isDemo
          ? <a href={d.map.url} target="_blank" rel="noreferrer" className="px-3 py-[5px] mono rounded-[2px]"
               style={{ border: '1px solid var(--accent)', color: 'var(--accent)', background: 'var(--accent-dim)' }}>Open {d.map.name} ↗</a>
          : <span className="mono" style={{ color: 'var(--t3)' }}>{isDemo ? `${d.map.name} (demo: no map)` : map.text}</span>}
      </div>
    </div>
  );
}

export function AircraftStackCard() {
  const { api, isDemo } = useStation();
  const s = usePoll(() => api.sdr(), 10_000, [api]);
  const ac = s.data?.aircraft;
  return (
    <Card pending={!s.data && !s.error}>
      <CardHeader title="Aircraft decoders (1090 / 978 MHz)" action={<MaturityBadge level="experimental" />} />
      <CardBody>
        <ApiErrorNote error={s.error} />
        {s.data && !ac && (
          <div className="text-[11px]" style={{ color: 'var(--t3)' }}>UNKNOWN: this station's software predates the decoder report (v1.6.0-rc.8).</div>
        )}
        {ac && (
          <>
            <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-3">
              {ac.decoders.map(d => <Decoder key={d.band} d={d} isDemo={isDemo} />)}
            </div>
            <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>
              Each decoder opens its dongle by USB serial (/etc/default/gps-time-sdr), never by its place on the bus.
              {ac.websdr_serial ? ` The web SDR is pinned to ${ac.websdr_serial}` : ' The web SDR has no dongle set'}
              {ac.websdr_serial ? (ac.websdr_band ? `, the ${ac.websdr_band} MHz dongle: only that decoder pauses while it runs.` : ', a dongle with no other role: nothing pauses.') : '.'}
              {' '}Messages per second are calculated from the decoder's own counters; the aircraft count is what it last wrote.
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
