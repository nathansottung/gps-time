import type { Almanac, SolarDay } from '../api/types';
import { Card, CardHeader, CardBody, ProvenanceTag, StatusBadge } from './ui';
import { DATE_MAX, DATE_MIN, SKY_STATES, dayBar, isSupportedDate, nightView, shiftDate, timeOnDay } from '../lib/almanac';

const BTN = { border:'1px solid var(--border)', color:'var(--t2)' } as const;

/** ← date → and Today, within the station's ephemeris range. */
export function DateNav({ date, today, onChange }: { date: string; today: string; onChange: (d: string) => void }) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <button onClick={() => onChange(shiftDate(date, -1))} disabled={date <= DATE_MIN} aria-label="Previous day"
        className="px-2 py-[5px] text-[10px] mono rounded-[2px]" style={BTN}>←</button>
      <input type="date" value={date} min={DATE_MIN} max={DATE_MAX} aria-label="Almanac date"
        onChange={e => { if (isSupportedDate(e.target.value)) onChange(e.target.value); }}
        className="mono tabular text-[11px] px-2 py-1 rounded-[2px]" style={{ background:'var(--bg)', border:'1px solid var(--border)', color:'var(--t1)', colorScheme:'dark' }} />
      <button onClick={() => onChange(shiftDate(date, 1))} disabled={date >= DATE_MAX} aria-label="Next day"
        className="px-2 py-[5px] text-[10px] mono rounded-[2px]" style={BTN}>→</button>
      <button onClick={() => onChange(today)} disabled={date === today}
        className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={BTN}>Today</button>
      <span className="text-[9px] mono" style={{ color:'var(--t4)' }}>{DATE_MIN.slice(0, 4)}–{DATE_MAX.slice(0, 4)} (JPL DE440s)</span>
    </div>
  );
}

function Legend({ states }: { states: number[] }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2">
      {SKY_STATES.filter(s => states.includes(s.state)).map(s => (
        <span key={s.state} className="flex items-center gap-1 text-[9px]" style={{ color:'var(--t3)' }}>
          <span className="inline-block w-2.5 h-2.5 rounded-[1px]" style={{ background: s.color }} />{s.label}
        </span>
      ))}
    </div>
  );
}

/** The 24 h bar for the selected day: night, the three twilights and day, local midnight to midnight. */
export function DayBarCard({ sun, tz }: { sun: SolarDay | null; tz: string }) {
  const pieces = dayBar(sun?.bar);
  const ev = sun?.events ?? {};
  const t = (k: string) => timeOnDay(ev[k], sun?.date ?? '', tz);
  return (
    <Card>
      <CardHeader title="Day, midnight to midnight" badge={<ProvenanceTag type="predicted" />} />
      <CardBody>
        {!pieces.length ? <StatusBadge variant="muted" label="UNKNOWN" dot={false} /> : <>
          <div className="relative h-4 rounded-[2px] overflow-hidden" role="img"
            aria-label={pieces.map(p => `${p.label} ${p.width.toFixed(0)}%`).join(', ')}>
            {pieces.map((p, i) => (
              <div key={i} className="absolute top-0 h-full" title={`${p.label}${p.start ? ` from ${timeOnDay(p.start, sun?.date ?? '', tz)}` : ''}`}
                style={{ left:`${p.left}%`, width:`${p.width}%`, background: p.color }} />
            ))}
          </div>
          <div className="flex justify-between text-[9px] mono mt-1" style={{ color:'var(--t3)' }}>
            <span>00:00</span><span>{t('astro_dawn') ? `astro dawn ${t('astro_dawn')}` : ''}</span>
            <span>12:00</span><span>{t('astro_dusk') ? `astro dusk ${t('astro_dusk')}` : ''}</span><span>24:00</span>
          </div>
          <Legend states={[...new Set(pieces.map(p => p.state))].sort()} />
        </>}
        <div className="text-[9px] mt-2" style={{ color:'var(--t4)' }}>
          Standard refraction and a flat horizon; observed times vary with the atmosphere and the local horizon.
        </div>
      </CardBody>
    </Card>
  );
}

/** Sunset to the next sunrise: twilight stages, the moon above the horizon, moonless astronomical darkness. */
export function NightCard({ almanac, day, tz }: { almanac: Almanac | null; day: string; tz: string }) {
  const v = nightView(almanac?.night);
  return (
    <Card>
      <CardHeader title="Night, sunset to sunrise" badge={<ProvenanceTag type="predicted" />} />
      <CardBody>
        {v === null ? <StatusBadge variant="muted" label="UNKNOWN" dot={false} />
        : !v.defined ? <div className="text-[11px]" style={{ color:'var(--t3)' }}>{v.note}</div>
        : <>
          <div className="relative pt-4">
            {v.midnight && (
              <div className="absolute top-0 text-[9px] mono -translate-x-1/2 whitespace-nowrap" style={{ left:`${v.midnight.left}%`, color:'var(--t3)' }}>
                {v.midnight.label}
              </div>
            )}
            <div className="relative h-4 rounded-[2px] overflow-hidden" style={{ background:'var(--sky-night)' }} role="img"
              aria-label={`Night from ${timeOnDay(v.sunset, day, tz)} to ${timeOnDay(v.sunrise, day, tz)}; moonless darkness ${v.darkTotal}`}>
              {v.stages.map((s, i) => (
                <div key={i} className="absolute top-0 h-full" title={s.label} style={{ left:`${s.left}%`, width:`${s.width}%`, background: s.color }} />
              ))}
              {v.dark.map((d, i) => (
                <div key={`d${i}`} className="absolute top-0 h-full rounded-[2px]"
                  title={`Moonless astronomical darkness ${timeOnDay(d.start, day, tz)}–${timeOnDay(d.end, day, tz)}`}
                  style={{ left:`${d.left}%`, width:`${d.width}%`, boxShadow:'inset 0 0 0 2px var(--good-text)' }} />
              ))}
              {v.midnight && <div className="absolute top-0 h-full w-px" style={{ left:`${v.midnight.left}%`, background:'var(--t3)' }} />}
            </div>
            <div className="relative h-2 mt-[3px]" aria-hidden>
              {v.moonUp.map((m, i) => (
                <div key={i} className="absolute top-0 h-full rounded-[2px]" title="Moon above the horizon"
                  style={{ left:`${m.left}%`, width:`${m.width}%`, background:'var(--t3)', opacity:0.6 }} />
              ))}
            </div>
          </div>
          <div className="flex justify-between text-[9px] mono mt-1" style={{ color:'var(--t3)' }}>
            <span>sunset {timeOnDay(v.sunset, day, tz)}</span>
            <span>moon above the horizon: strip below</span>
            <span>sunrise {timeOnDay(v.sunrise, day, tz)}</span>
          </div>
          <Legend states={[...new Set(v.stages.map(s => s.stage))].sort()} />
          <div className="mt-3 text-[11px]" style={{ color:'var(--t2)' }}>
            {v.note
              ? <span style={{ color:'var(--t3)' }}>{v.note}</span>
              : <>Moonless astronomical darkness: <span className="mono tabular" style={{ color:'var(--t1)' }}>{v.darkTotal}</span>
                  <span className="mono text-[10px] ml-2" style={{ color:'var(--t3)' }}>
                    {v.dark.length ? v.dark.map(d => `${timeOnDay(d.start, day, tz)}–${timeOnDay(d.end, day, tz)}`).join(', ') : 'none'}
                  </span></>}
          </div>
        </>}
      </CardBody>
    </Card>
  );
}
