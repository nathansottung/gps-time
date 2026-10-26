// Station clock: the station's time (GPS/PPS-disciplined when the timing chain
// says so), shown in the local display zone with UTC beneath. Display only.
import { useEffect, useState } from 'react';
import { Card, CardBody, CardHeader, ProvenanceTag } from './ui';
import { useStation, useBrowserClock } from '../api/station';
import { clockDiscipline } from '../lib/banner';
import {
  formatLocal, formatUtc, loadHour12, resolveZone, saveHour12, stationInstant, unixSeconds,
  type LocalClock, type ResolvedZone, type StationInstant,
} from '../lib/localtime';

export interface StationTime {
  now: StationInstant;
  zone: ResolvedZone;
  local: LocalClock;
  hour12: boolean;
  toggleHour12: () => void;
}

const HOUR12_EVENT = 'gtp-hour12-changed';

/** Ticks once per station second. The 12/24-hour choice is shared by every clock on the page. */
export function useStationTime(): StationTime {
  const { core } = useStation();
  const clk = useBrowserClock();
  const [now, setNow] = useState<StationInstant>(() => stationInstant(Date.now(), clk.offsetMs));
  const [hour12, setHour12] = useState(() => loadHour12());
  useEffect(() => {
    const tick = () => setNow(prev => {
      const next = stationInstant(Date.now(), clk.offsetMs);
      return next.basis === prev.basis && Math.floor(next.at.getTime() / 1000) === Math.floor(prev.at.getTime() / 1000) ? prev : next;
    });
    tick();
    const id = setInterval(tick, 200);
    return () => clearInterval(id);
  }, [clk.offsetMs]);
  useEffect(() => {
    const sync = () => setHour12(loadHour12());
    window.addEventListener(HOUR12_EVENT, sync);
    return () => window.removeEventListener(HOUR12_EVENT, sync);
  }, []);
  const zone = resolveZone(core.data?.timezone);
  const toggleHour12 = () => { saveHour12(!hour12); setHour12(!hour12); window.dispatchEvent(new Event(HOUR12_EVENT)); };
  return { now, zone, local: formatLocal(now.at, zone.tz, hour12), hour12, toggleHour12 };
}

export function HourToggle({ t }: { t: StationTime }) {
  return (
    <button onClick={t.toggleHour12} aria-label={`Switch to ${t.hour12 ? '24' : '12'}-hour clock`}
      title={`Click for the ${t.hour12 ? '24' : '12'}-hour clock.`}
      className="px-1.5 py-[3px] text-[9px] mono rounded-[2px]"
      style={{ border:'1px solid var(--border)', color:'var(--t3)' }}>
      {t.hour12 ? '12H' : '24H'}
    </button>
  );
}

/** The big clock: local time from the station's clock, UTC and the Unix epoch beneath. */
export function StationClockCard() {
  const { chain, core } = useStation();
  const clk = useBrowserClock();
  const t = useStationTime();
  const station = t.now.basis === 'station';
  const disc = clockDiscipline(chain.data, !chain.data && !!(chain.error || core.error));
  const caption = station ? disc.label : "THIS BROWSER'S CLOCK · STATION TIME NOT MEASURED YET";
  const captionColor = station && disc.gps ? 'var(--good-text)' : 'var(--warn-text)';
  return (
    <Card>
      <CardHeader title="Local time" badge={station ? <ProvenanceTag type="inferred" /> : undefined} />
      <CardBody>
        <div className="flex items-end justify-between gap-6 flex-wrap">
          <div>
            <div className="text-[9px] mono uppercase tracking-[0.12em] mb-1" style={{ color: captionColor }}>{caption}</div>
            <div className="mono tabular font-medium leading-none" style={{ color:'var(--t1)', fontSize:'44px', letterSpacing:'0.01em' }}
              aria-label={`Local time ${t.local.time}`}>
              {t.local.time}
            </div>
            <div className="mono text-[12px] mt-2" style={{ color:'var(--t2)' }}>
              {t.local.date}
              {t.local.abbr && <span> · {t.local.abbr}</span>}
              <span> · {t.local.offset}</span>
              {t.local.dst && <span> · DST</span>}
            </div>
            <div className="mono tabular text-base mt-3" style={{ color:'var(--t1)' }}>
              <span style={{ color:'var(--t3)' }}>UTC</span> {formatUtc(t.now.at)}
            </div>
            <div className="mono tabular text-[11px] mt-1" style={{ color:'var(--t3)' }}>UNIX {unixSeconds(t.now.at)}</div>
          </div>
          <HourToggle t={t} />
        </div>
        <div className="text-[9px] mt-3" style={{ color:'var(--t3)' }}>
          {t.zone.tz} · {t.zone.label}. Local time is for display; the station keeps UTC.{' '}
          {station
            ? `The station's clock is read through this browser: offset ${clk.offsetMs! >= 0 ? '+' : '−'}${Math.abs(clk.offsetMs!).toFixed(1)} ms applied, ` +
              `best round trip ${clk.minRttMs === null ? 'unknown' : clk.minRttMs.toFixed(1) + ' ms'}. The display can be off by about half the round trip.`
            : 'No station clock offset has been measured, so this is not station time.'}
        </div>
      </CardBody>
    </Card>
  );
}
