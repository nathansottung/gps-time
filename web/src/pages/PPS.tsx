// PPS diagnostics page (CHG-PPS-HEALTH-DIAGNOSTICS: "PPS Diagnostic Card",
// "Diagnostic Snapshot", "Advanced Diagnostics", acceptance criteria 1–12).
// Read-only: every value comes from /api/timing-chain and /api/diagnostics.

import { useState, type ReactNode } from 'react';
import { Card, CardHeader, CardBody, MetricRow, StatusBadge, ProvenanceTag } from '../components/ui';
import { ApiErrorNote } from '../components/planned';
import { stageVariant, fmtAge, TimingChainCard } from '../components/timing';
import { useStation } from '../api/station';
import { allEvents } from '../api/view';
import type { Measured, TimingChain, TimingEvent } from '../api/types';
import { fmtDuration, fmtSeconds, fmtUtc } from '../lib/format';
import { copyText, downloadText, snapshotFilename } from '../lib/export';
import { nmeaCompare } from '../lib/ntpservice';

const val = <T,>(m: Measured<T> | null | undefined): T | null => (m ? m.value : null);
const sec = (s: number | null | undefined) => (s === null || s === undefined ? null : fmtSeconds(s, 3));
// chrony prints "+0ns[+0ns] +/- 0ns" for a refclock with no samples; that is not a measurement.
const noSamples = (ref: { reach: Measured<string> }) => val(ref.reach) === '0';
const signed = (s: number | null | undefined) => (s === null || s === undefined ? null : `${s >= 0 ? '+' : '−'}${fmtSeconds(s)}`);

function Section({ title, children, prov }: { title: string; children: ReactNode; prov?: Measured['provenance'] }) {
  return (
    <Card>
      <CardHeader title={title} badge={prov ? <ProvenanceTag type={prov} /> : undefined} />
      <CardBody>{children}</CardBody>
    </Card>
  );
}

// ─── Acceptance criteria: answerable from the web UI alone ───────────────────
function stage(c: TimingChain, id: string) { return c.stages.find(s => s.id === id); }

function answers(c: TimingChain): [string, string | null, 'good' | 'warn' | 'error' | 'muted' | 'info'][] {
  const g = c.gnss, p = c.pps, ch = c.chrony, open = c.events.open;
  const past = c.events.recent.filter(e => !e.open);
  const lastRec = past.find(e => e.recovery)?.recovery;
  const st = (id: string) => stage(c, id);
  const yesNo = (id: string): [string | null, ReturnType<typeof stageVariant>] => {
    const s = st(id);
    return [s ? `${s.status.replace(/_/g, ' ')} — ${s.summary}` : null, stageVariant(s?.status)];
  };
  const maxOpen = open?.evidence.max_abs_system_time_s;
  return [
    ['1. Is GNSS still being received?', g.healthy === null ? null
      : [g.healthy ? 'Yes' : 'No',
         val(g.satellites_used) != null ? `${val(g.satellites_used)} used of ${val(g.satellites_visible) ?? '—'} visible` : null,
         val(g.fix) ? `fix ${val(g.fix)}` : null,
         `receiver communication ${g.receiver_comms}`].filter(Boolean).join(' — '),
      g.healthy ? 'good' : g.healthy === false ? 'error' : 'muted'],
    ['2. Does /dev/pps0 exist?', val(p.device_present) === null ? null : `${val(p.device_present) ? 'Yes' : 'No'} — ${val(p.device)}`,
      val(p.device_present) ? 'good' : val(p.device_present) === false ? 'error' : 'muted'],
    ['3. Are PPS events reaching Linux?', ...yesNo('kernel_events')],
    ['4. When was the most recent PPS event?', val(p.last_event_utc) ? `${fmtUtc(val(p.last_event_utc))} (${fmtAge(val(p.age_s))})` : null,
      p.pulse_health === 'HEALTHY' ? 'good' : p.pulse_health === 'LOST' ? 'error' : 'warn'],
    ['5. Does chrony see PPS?', ...yesNo('chrony_pps_visible')],
    ['6. Does chrony accept PPS?', ...yesNo('chrony_pps_accepted')],
    ['7. Does chrony select PPS?', ...yesNo('chrony_pps_selected')],
    ['8. Which source disciplines the clock?', ch.selected ? `${ch.selected.name} (${ch.selected.kind}), stratum ${ch.tracking?.stratum ?? '—'}` : 'No source selected',
      ch.selected?.is_pps ? 'good' : ch.selected ? 'warn' : 'error'],
    ['9. How long has the station been in failover?', open ? `${fmtDuration(open.duration_s)}${open.start_bound ? ' (or longer)' : ''}` : 'Not in a PPS outage',
      open ? 'warn' : 'good'],
    ['10. When did the failure begin?', open ? `${fmtUtc(open.start_utc)}${open.start_bound ? ` or earlier (${open.start_bound.replace('_', ' ')})` : ''}` : '—',
      open ? 'warn' : 'muted'],
    ['11. Have similar failures happened before?', past.length
      ? `${past.length} earlier outage${past.length > 1 ? 's' : ''} recorded; last ${fmtUtc(past[0].start_utc)} for ${fmtDuration(past[0].duration_s)} (${past[0].classification ?? 'UNKNOWN'})`
      : 'None recorded (the station keeps the most recent events only)', past.length ? 'info' : 'muted'],
    ['12. What happened to clock accuracy during the outage?', open
      ? (maxOpen != null ? `Largest chrony correction so far ${fmtSeconds(maxOpen)} (chrony's estimate, not an independent measurement)` : null)
      : lastRec && val(lastRec.max_abs_system_time_s) != null
        ? `Last outage: largest chrony correction ${fmtSeconds(val(lastRec.max_abs_system_time_s))} (chrony's estimate)` : '—',
      open ? 'warn' : 'muted'],
  ];
}

function EventRow({ e }: { e: TimingEvent }) {
  const r = e.recovery;
  return (
    <div className="py-2" style={{ borderBottom: '1px solid var(--border-dim)' }}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[11px]">
        <StatusBadge variant={e.open ? 'error' : 'muted'} label={e.open ? 'OPEN' : 'CLOSED'} dot={false} className="text-[9px]" />
        <span className="mono" style={{ color: 'var(--t2)' }}>{fmtUtc(e.start_utc)}{e.start_bound ? ' (or earlier)' : ''}</span>
        <span className="mono" style={{ color: 'var(--warn-text)' }}>{fmtDuration(e.duration_s) ?? '—'}</span>
        <span style={{ color: 'var(--t1)' }}>{e.classification ?? 'UNKNOWN'}</span>
        <ProvenanceTag type={e.classification_provenance} />
        <span className="text-[10px]" style={{ color: 'var(--t3)' }}>confidence {e.confidence ?? '—'} · boundary: {e.boundary ?? '—'}</span>
      </div>
      <div className="grid grid-cols-2 @lg:grid-cols-4 gap-x-4 mt-1 text-[10px]">
        <span style={{ color: 'var(--t3)' }}>Fallback: <span className="mono" style={{ color: 'var(--t2)' }}>
          {(r?.fallback_sources ?? e.evidence.fallback_sources ?? []).join(', ') || 'none'}</span></span>
        <span style={{ color: 'var(--t3)' }}>Max |correction|: <span className="mono" style={{ color: 'var(--t2)' }}>
          {fmtSeconds(r ? val(r.max_abs_system_time_s) : e.evidence.max_abs_system_time_s) ?? '—'}</span></span>
        <span style={{ color: 'var(--t3)' }}>Accept / select after: <span className="mono" style={{ color: 'var(--t2)' }}>
          {r ? `${fmtDuration(val(r.time_to_accept_s)) ?? '—'} / ${fmtDuration(val(r.time_to_select_s)) ?? '—'}` : '—'}</span></span>
        <span style={{ color: 'var(--t3)' }}>Satellites used: <span className="mono" style={{ color: 'var(--t2)' }}>
          {e.evidence.satellites_used_range ? e.evidence.satellites_used_range.join('–') : '—'}</span></span>
      </div>
      {r?.network_ntp?.value === true && <div className="text-[10px] mt-1" style={{ color: 'var(--warn-text)' }}>
        chrony switched to network NTP during this outage ({(r.network_ntp_sources ?? []).join(', ')}): the clock was steered, so its error at recovery isn't holdover error and the holdover scorecard doesn't score it.</div>}
      {e.notes.length > 0 && <div className="text-[10px] mt-1" style={{ color: 'var(--t3)' }}>{e.notes.join(' ')}</div>}
      {r?.note && <div className="text-[10px] mt-1" style={{ color: 'var(--t3)' }}>{r.note}</div>}
    </div>
  );
}

function Raw({ title, text }: { title: string; text: string | undefined }) {
  return (
    <div>
      <div className="text-[9px] mono uppercase tracking-[0.12em] mb-1" style={{ color: 'var(--t3)' }}>{title}</div>
      <pre className="mono text-[10px] whitespace-pre overflow-x-auto p-2 rounded-[2px]"
        style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--t2)' }}>{text || '(not available)'}</pre>
    </div>
  );
}

// ─── Snapshot: COPY / DOWNLOAD ───────────────────────────────────────────────
function Snapshot() {
  const { api, scenario } = useStation();
  const [text, setText] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const fetchText = async () => {
    try {
      const t = await api.diagnostics({ scenario });
      setText(t); setErr(null);
      return t;
    } catch (e) { setErr((e as Error).message); return null; }
  };
  const onCopy = async () => {
    const t = await fetchText();
    if (t === null) return;
    setMsg(await copyText(t) ? 'Copied to clipboard.' : 'Copy was blocked by the browser: select the text below and copy it manually.');
  };
  const onDownload = async () => {
    const t = await fetchText();
    if (t === null) return;
    const name = snapshotFilename();
    downloadText(name, t);
    setMsg(`Saved as ${name}.`);
  };
  const btn = { border: '1px solid var(--accent)', color: 'var(--accent)', background: 'var(--accent-dim)' };
  return (
    <Card>
      <CardHeader title="Diagnostic snapshot" action={
        <div className="flex gap-1.5">
          <button onClick={onCopy} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>COPY DIAGNOSTICS</button>
          <button onClick={onDownload} className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={btn}>DOWNLOAD</button>
        </div>} />
      <CardBody>
        <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>
          Plain text for remote troubleshooting, fetched fresh from the station on each click. The station applies the location privacy mode.
          Nothing is sent anywhere: copy uses your clipboard, download saves a local .txt file.
        </div>
        <ApiErrorNote error={err} />
        {msg && <div className="text-[10px] mono mb-2" style={{ color: 'var(--t2)' }}>{msg}</div>}
        {text && <pre className="mono text-[10px] whitespace-pre-wrap p-2 rounded-[2px] max-h-96 overflow-auto"
          style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--t2)' }}>{text}</pre>}
      </CardBody>
    </Card>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────
export default function PPS() {
  const { chain, scenario, setScenario } = useStation();
  const c = chain.data;
  if (!c) {
    return (
      <div className="space-y-4 page-enter">
        <h1 className="text-sm font-semibold" style={{ color: 'var(--t1)' }}>PPS Diagnostics</h1>
        <ApiErrorNote error={chain.error} />
        {!chain.error && <div className="text-[11px]" style={{ color: 'var(--t3)' }}>Loading timing chain…</div>}
      </div>
    );
  }
  const p = c.pps, ch = c.chrony, ref = ch.pps, stats = val(p.interval_stats ?? null);
  const events = allEvents(c.events.open, c.events.recent);

  return (
    <div className="space-y-4 page-enter">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <h1 className="text-sm font-semibold" style={{ color: 'var(--t1)' }}>PPS Diagnostics</h1>
          <p className="text-[10px] mt-0.5" style={{ color: 'var(--t3)' }}>Read-only. Generated {fmtUtc(c.generated_utc) ?? '—'} by the station.</p>
        </div>
        {c.demo && (
          <label className="text-[10px] flex items-center gap-2" style={{ color: 'var(--t3)' }}>
            Demo scenario
            <select value={scenario ?? c.demo.scenario} onChange={e => setScenario(e.target.value)}
              className="mono text-[10px] px-1.5 py-1 rounded-[2px]" style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--t2)' }}>
              {c.demo.scenarios.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        )}
      </div>
      <ApiErrorNote error={chain.error} />

      <TimingChainCard />

      <Section title="Can the station's timing be diagnosed from here?">
        <div className="table-scroll"><table className="w-full text-[11px]">
          <tbody>
            {answers(c).map(([q, a, v]) => (
              <tr key={q} style={{ borderBottom: '1px solid var(--border-dim)' }}>
                <td className="py-1.5 pr-4 align-top" style={{ color: 'var(--t3)', width: '34%' }}>{q}</td>
                <td className="py-1.5 align-top">
                  {a === null ? <StatusBadge variant="muted" label="UNKNOWN" dot={false} />
                    : <span style={{ color: v === 'good' ? 'var(--good-text)' : v === 'error' ? 'var(--err-text)' : v === 'warn' ? 'var(--warn-text)' : 'var(--t1)' }}>{a}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </Section>

      {c.classification && (
        <Section title="Classification" prov="inferred">
          <MetricRow label="Classification" value={c.classification.classification} provenance="inferred" />
          <MetricRow label="Confidence" value={c.classification.confidence} />
          <MetricRow label="Boundary in the signal path" value={c.classification.boundary} />
          {c.classification.notes.map(n => <div key={n} className="text-[10px] mt-1" style={{ color: 'var(--t3)' }}>{n}</div>)}
          <div className="text-[10px] mt-1" style={{ color: 'var(--t3)' }}>A classification names where in the path the evidence points, not a cause.</div>
        </Section>
      )}

      <div className="grid grid-cols-1 @2xl:grid-cols-2 @5xl:grid-cols-3 gap-4">
        <Section title="Device" prov="observed">
          <MetricRow label="Expected device" value={val(p.device)} />
          <MetricRow label="Device present" value={val(p.device_present) === null ? null : val(p.device_present) ? 'yes' : 'no'} provenance="observed" />
          <MetricRow label="Kernel name" value={p.metadata?.name ?? null} />
          <MetricRow label="sysfs path" value={p.metadata?.path ?? null} />
          <MetricRow label="Configured GPIO" value={p.boot_config?.gpio ?? null} />
          <MetricRow label="Assert edge" value={p.boot_config?.assert_edge ?? null} />
          <div className="text-[10px] mt-1" style={{ color: 'var(--t3)' }}>GPIO and edge from {p.boot_config?.source ?? 'UNKNOWN'} (boot configuration, read-only).</div>
        </Section>

        <Section title="Live PPS (Linux kernel)" prov="observed">
          <div className="text-[10px] mb-1 px-2 py-1 rounded-[2px]" style={{ background: 'var(--bg)', border: '1px solid var(--border-dim)', color: 'var(--t3)' }}>
            Measurement layer: {p.measurement_layer}
          </div>
          <MetricRow label="Pulse health" value={p.pulse_health} provenance={p.pulse_health_provenance} />
          <MetricRow label="Latest event" value={fmtUtc(val(p.last_event_utc ?? null))} provenance="observed" />
          <MetricRow label="Age" value={fmtAge(val(p.age_s ?? null))} provenance="calculated" />
          <MetricRow label="Event rate" value={val(p.rate_hz ?? null) === null ? null : `${val(p.rate_hz ?? null)!.toFixed(6)} Hz`} provenance="calculated" />
          <MetricRow label="Consecutive pulses" value={val(p.consecutive_pulses ?? null)} provenance="calculated" />
          <MetricRow label="Missed pulses (never counted by the kernel)" value={val(p.missed_pulses ?? null)} provenance="calculated" />
          <MetricRow label="Unread pulses (counted by the kernel, not lost)" value={val(p.unread_pulses ?? null)} provenance="calculated" />
          <MetricRow label="Station polls / late / longest gap" value={p.poller ? `${p.poller.polls} / ${p.poller.late_polls} / ${p.poller.max_poll_gap_s ?? '—'} s` : null} muted />
          <MetricRow label="Sequence resets" value={p.sequence_resets ?? null} />
          <MetricRow label="Interval mean / min / max" value={stats ? `${sec(stats.mean)} / ${sec(stats.min)} / ${sec(stats.max)}` : null} provenance="calculated" />
          <MetricRow label="Interval std. dev." value={stats ? sec(stats.stdev) : null} provenance="calculated" />
          <MetricRow label="Thresholds degraded / lost" value={p.thresholds_s ? `${p.thresholds_s.degraded_after} s / ${p.thresholds_s.lost_after} s` : null} muted />
          <div className="text-[10px] mt-1" style={{ color: 'var(--t3)' }}>Interval statistics are kernel timestamp spacing, not receiver or electrical PPS jitter.</div>
        </Section>

        <Section title="chrony PPS refclock" prov="observed">
          <MetricRow label="Refclock (from chrony.conf)" value={ch.refclocks.pps} />
          <MetricRow label="PPS status" value={ch.pps_status.replace(/_/g, ' ')} provenance="calculated" />
          <MetricRow label="Mode" value={ref?.mode ?? null} />
          <MetricRow label="Status symbol" value={ref ? `${val(ref.state_symbol) ?? '?'} — ${ref.state_meaning}` : null} provenance="observed" />
          <MetricRow label="Reach (octal)" value={ref ? `${val(ref.reach)} (${val(ref.reach_successes_of_8) ?? '—'}/8)` : null} provenance="observed" />
          <MetricRow label="Last sample" value={ref ? (val(ref.last_rx_s) === null ? null : `${val(ref.last_rx_s)} s ago`) : null} />
          <MetricRow label="Poll interval" value={ref ? `${2 ** ref.poll_log2_s} s` : null} />
          <MetricRow label="Offset ± error bound" value={!ref ? null : noSamples(ref) ? 'no samples (reach 0)'
            : val(ref.offset_s) === null ? null : `${signed(val(ref.offset_s))} ± ${fmtSeconds(val(ref.error_bound_s)) ?? '—'}`} provenance="observed" />
          <MetricRow label="Frequency / skew" value={ref && val(ref.frequency_ppm) !== null ? `${val(ref.frequency_ppm)} / ${val(ref.skew_ppm)} ppm` : null} provenance="calculated" />
          <MetricRow label="Std. dev." value={ref ? fmtSeconds(val(ref.std_dev_s)) : null} provenance="calculated" />
          <MetricRow label="NMEA lock refclock" value={ch.refclocks.pps_lock ? `${ch.refclocks.pps_lock} — ${ch.nmea_status}` : null} />
          <MetricRow label="Selected source" value={ch.selected ? `${ch.selected.name} (${ch.selected.kind})` : 'none'} />
          <MetricRow label="System stratum / reference" value={ch.tracking ? `${ch.tracking.stratum ?? '—'} / ${ch.tracking.reference ?? '—'}` : null} />
          <div className="text-[10px] mt-1" style={{ color: 'var(--t3)' }}>chrony does not report why a source is rejected; no reason is inferred.</div>
        </Section>
      </div>

      <Section title="NMEA refclock offset" prov="calculated">
        {(() => {
          const cal = ch.nmea_calibration;
          if (!cal) return <div className="text-[11px]" style={{ color: 'var(--t3)' }}>Not reported by this station version.</div>;
          const cmp = nmeaCompare(cal);
          return (
            <>
              <div className="grid grid-cols-1 @md:grid-cols-2 gap-4 mb-2">
                <div className="px-3 py-2 rounded-[2px]" style={{ background: 'var(--bg)', border: '1px solid var(--border-dim)' }}>
                  <div className="text-[9px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--t3)' }}>Configured (chrony.conf)</div>
                  <div className="flex items-baseline gap-2 mt-1">
                    {cmp.configured
                      ? <span className="mono tabular text-base font-medium" style={{ color: 'var(--t1)' }}>{cmp.configured}</span>
                      : <StatusBadge variant="muted" label="UNKNOWN" dot={false} />}
                    <ProvenanceTag type="observed" />
                  </div>
                </div>
                <div className="px-3 py-2 rounded-[2px]" style={{ background: 'var(--bg)', border: '1px solid var(--border-dim)' }}>
                  <div className="text-[9px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--t3)' }}>Suggested (measured)</div>
                  <div className="flex items-baseline gap-2 mt-1">
                    {cmp.suggested
                      ? <>
                          <span className="mono tabular text-base font-medium" style={{ color: 'var(--t1)' }}>{cmp.suggested}</span>
                          <span className="mono tabular text-[11px]" style={{ color: cmp.same ? 'var(--t3)' : 'var(--warn-text)' }}>{cmp.same ? 'same' : cmp.difference}</span>
                        </>
                      : <StatusBadge variant="muted" label="UNKNOWN" dot={false} />}
                    <ProvenanceTag type="calculated" />
                  </div>
                  {!cmp.suggested && <div className="text-[10px] mt-1" style={{ color: 'var(--t3)' }}>{cmp.suggestedReason}</div>}
                </div>
              </div>
              {cal.available ? (
                <>
                  <MetricRow label="Residual vs PPS-disciplined clock" value={signed(val(cal.residual_s!))} provenance="observed" />
                  <MetricRow label="Std. dev. / samples" value={`${fmtSeconds(val(cal.std_dev_s!)) ?? '—'} / ${val(cal.samples!)}`} provenance="observed" />
                  <div className="text-[10px] mt-1" style={{ color: cal.change_worthwhile ? 'var(--t2)' : 'var(--t3)' }}>{cal.advice}</div>
                </>
              ) : null}
              <div className="text-[10px] mt-1" style={{ color: 'var(--t3)' }}>
                A positive residual means the serial time still arrives late. The station only reports this; it never edits chrony.conf.
                The PPS refclock uses NMEA to number its seconds, so NMEA needs to be right to a fraction of a second, not better.
              </div>
            </>
          );
        })()}
      </Section>

      <Section title="PPS outage events" prov="observed">
        {events.length ? events.map(e => <EventRow key={e.id} e={e} />)
          : <div className="text-[11px]" style={{ color: 'var(--t3)' }}>No PPS outages recorded.</div>}
        <div className="text-[10px] mt-2" style={{ color: 'var(--t3)' }}>
          Max |correction| is the largest remaining correction chrony reported during the outage: chrony's estimate, not an independent error measurement.
        </div>
      </Section>

      <Section title="Timing-chain stages" prov="calculated">
        <div className="table-scroll"><table className="w-full text-[11px]">
          <tbody>
            {c.stages.map(s => (
              <tr key={s.id} style={{ borderBottom: '1px solid var(--border-dim)' }}>
                <td className="py-1.5 pr-3" style={{ color: 'var(--t2)' }}>{s.label}</td>
                <td className="py-1.5 pr-3"><StatusBadge variant={stageVariant(s.status)} label={s.status.replace(/_/g, ' ')} dot={false} className="text-[9px]" /></td>
                <td className="py-1.5 text-[10px]" style={{ color: 'var(--t3)' }}>{s.summary}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </Section>

      <Section title="Advanced (read-only raw output)">
        <div className="text-[10px] mb-2" style={{ color: 'var(--t3)' }}>
          What the station read, verbatim. These are fixed read-only queries (<span className="mono">chronyc -n</span>, sysfs); the page cannot run commands.
        </div>
        <div className="space-y-3">
          <Raw title="chronyc -n tracking" text={c.raw.tracking} />
          <Raw title="chronyc -n sources" text={c.raw.sources} />
          <Raw title="chronyc -n sourcestats" text={c.raw.sourcestats} />
          <Raw title="PPS device (sysfs)" text={[
            `device: ${val(p.device) ?? 'UNKNOWN'} (${val(p.device_present) ? 'present' : val(p.device_present) === false ? 'missing' : 'UNKNOWN'})`,
            `name: ${p.metadata?.name ?? '—'}`, `path: ${p.metadata?.path ?? '—'}`,
            `last assert: ${val(p.last_event_utc ?? null) ?? '—'}  sequence: ${val(p.last_sequence ?? null) ?? '—'}`,
          ].join('\n')} />
        </div>
      </Section>

      <Snapshot />
    </div>
  );
}
