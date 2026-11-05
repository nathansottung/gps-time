// Aviation → the live aircraft maps (GET /api/aircraft-map, polled once for both): tar1090 on readsb's
// 1090 MHz data at /tar1090/, and skyaware978 on dump978-fa's 978 MHz UAT data at /skyaware978/, both
// served by the station on the LAN. Logic: lib/aircraftmap.ts.
import { Card, CardHeader, CardBody, MetricRow, StatusBadge } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll } from '../api/station';
import { ageLine, mapState, markerLine, uatState } from '../lib/aircraftmap';
import type { AircraftMapStatus } from '../api/types';

function OpenLink({ href, ready, isDemo, label }: { href: string; ready: boolean; isDemo: boolean; label: string }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-3">
      {ready && !isDemo
        ? <a href={href} target="_blank" rel="noreferrer" className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
             style={{ border: '1px solid var(--accent)', color: 'var(--accent)', background: 'var(--accent-dim)' }}>{label} ↗</a>
        : <span className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={{ border: '1px solid var(--border-dim)', color: 'var(--t3)' }}>
            {label} ({isDemo ? 'demo: no map' : 'not installed'})</span>}
    </div>
  );
}

export function AircraftMapCards() {
  const { api, isDemo } = useStation();
  const m = usePoll(() => api.aircraftMap(), 10_000, [api]);
  return (
    <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
      <AircraftMapCard st={m.data} error={m.error} isDemo={isDemo} />
      <UatMapCard st={m.data} error={m.error} isDemo={isDemo} />
    </div>
  );
}

function AircraftMapCard({ st, error, isDemo }: { st: AircraftMapStatus | null | undefined; error: string | null; isDemo: boolean }) {
  const state = st ? mapState(st) : null;
  return (
    <Card pending={!st && !error}>
      <CardHeader title="1090 MHz ADS-B map (tar1090)"
        badge={state ? <StatusBadge variant={state.variant} label={state.label} /> : undefined} />
      <CardBody>
        <ApiErrorNote error={error} />
        {st && (
          <>
            {state?.text && <div className="text-[11px] mb-2" style={{ color: 'var(--t2)' }}>{state.text}</div>}
            <MetricRow label="Aircraft in aircraft.json" value={st.aircraft} provenance="observed" />
            <MetricRow label="Data age" value={ageLine(st.aircraft_json_age_s)} provenance="observed" />
            <MetricRow label="Station marker" value={markerLine(st)} />
            <OpenLink href={st.url} ready={st.installed} isDemo={isDemo} label="Open the map" />
            {!st.installed && (
              <div className="text-[11px] mt-2" style={{ color: 'var(--t3)' }}>
                It comes with the SDR stack's 1090 MHz role: <span className="mono">sudo GTP_SDR=1 GTP_SDR_1090_SERIAL=… bash install.sh</span> (docs/deploy/sdr-stack.md).
              </div>
            )}
            <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>
              {st.note} On the LAN only, like the rest of this page. The aircraft it shows still say roughly where the station is.
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}

function UatMapCard({ st, error, isDemo }: { st: AircraftMapStatus | null | undefined; error: string | null; isDemo: boolean }) {
  const u = st?.uat;
  const state = st ? uatState(u) : null;
  return (
    <Card pending={!st && !error}>
      <CardHeader title="978 MHz UAT map (skyaware978)"
        badge={state ? <StatusBadge variant={state.variant} label={state.label} /> : undefined} />
      <CardBody>
        <ApiErrorNote error={error} />
        {st && (
          <>
            {state?.text && <div className="text-[11px] mb-2" style={{ color: 'var(--t2)' }}>{state.text}</div>}
            <MetricRow label="Aircraft in aircraft.json" value={u ? u.aircraft : null} provenance="observed" />
            <MetricRow label="Data age" value={u ? ageLine(u.aircraft_json_age_s) : null} provenance="observed" />
            <OpenLink href={u?.url ?? '/skyaware978/'} ready={!!u?.installed} isDemo={isDemo} label="Open the 978 MHz map" />
            {u && !u.installed && (
              <div className="text-[11px] mt-2" style={{ color: 'var(--t3)' }}>
                It comes with the SDR stack's 978 MHz role: <span className="mono">GTP_SDR_978_SERIAL=…</span> with a second dongle (docs/deploy/sdr-stack.md).
              </div>
            )}
            <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>
              UAT is used by US general aviation below 18,000 ft. skyaware978's own page, from the pinned dump978 commit; no position is given to the decoder.
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
