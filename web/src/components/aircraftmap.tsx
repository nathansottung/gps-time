// Aviation → Live aircraft map: tar1090 on readsb's 1090 MHz data (GET /api/aircraft-map), served by
// the station at /tar1090/ on the LAN. Logic: lib/aircraftmap.ts.
import { Card, CardHeader, CardBody, MetricRow, StatusBadge } from './ui';
import { ApiErrorNote } from './planned';
import { useStation, usePoll } from '../api/station';
import { ageLine, mapState, markerLine } from '../lib/aircraftmap';

export function AircraftMapCard() {
  const { api, isDemo } = useStation();
  const m = usePoll(() => api.aircraftMap(), 10_000, [api]);
  const st = m.data;
  const state = st ? mapState(st) : null;
  return (
    <Card pending={!st && !m.error}>
      <CardHeader title="Live aircraft map (tar1090)"
        badge={state ? <StatusBadge variant={state.variant} label={state.label} /> : undefined} />
      <CardBody>
        <ApiErrorNote error={m.error} />
        {st && (
          <>
            {state?.text && <div className="text-[11px] mb-2" style={{ color: 'var(--t2)' }}>{state.text}</div>}
            <div className="grid grid-cols-1 @md:grid-cols-2 gap-x-6">
              <div>
                <MetricRow label="Aircraft in aircraft.json" value={st.aircraft} provenance="observed" />
                <MetricRow label="Data age" value={ageLine(st.aircraft_json_age_s)} provenance="observed" />
              </div>
              <div>
                <MetricRow label="Station marker" value={markerLine(st)} />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-1.5 mt-3">
              {st.installed && !isDemo
                ? <a href={st.url} target="_blank" rel="noreferrer" className="px-3 py-[5px] text-[10px] mono rounded-[2px]"
                     style={{ border: '1px solid var(--accent)', color: 'var(--accent)', background: 'var(--accent-dim)' }}>Open the map ↗</a>
                : <span className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={{ border: '1px solid var(--border-dim)', color: 'var(--t3)' }}>
                    Open the map ({isDemo ? 'demo: no map' : 'not installed'})</span>}
            </div>
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
