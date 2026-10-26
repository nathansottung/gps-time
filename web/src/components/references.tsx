import { useState } from 'react';
import { Card, CardHeader, CardBody, ProvenanceTag, StatusBadge, ELI5 } from './ui';
import { ScaleToggle, TimeSeriesChart } from './charts';
import { ApiErrorNote } from './planned';
import { useStation, usePoll, isPending } from '../api/station';
import { assessmentVariant, countsLine, fmtSigned, fmtSpan, historySeries, verdictVariant } from '../lib/references';
import { fmtUtc } from '../lib/format';

const TH = { color:'var(--t3)', fontWeight:400, fontFamily:'JetBrains Mono', fontSize:10, letterSpacing:'0.05em',
             padding:'6px 16px', borderBottom:'1px solid var(--border)' } as const;

/** Demo only: ?refs=disagree|unreachable|none picks a sample scenario; a live station ignores it. */
function demoScenario(): string | undefined {
  try { return new URLSearchParams(window.location.search).get('refs') || undefined; } catch { return undefined; }
}

// ─── Independent references (/api/references) ────────────────────────────────
export function ReferencesPanel() {
  const { api } = useStation();
  const scenario = demoScenario();
  const [picked, setPicked] = useState<string | null>(null);
  const rf = usePoll(() => api.references({ scenario, history: picked ?? undefined }), 15_000, [api, scenario, picked]);
  const d = rf.data;
  const v = d?.verdict;
  const refs = d?.references ?? [];
  const shown = refs.find(r => r.history.length > 0) ?? refs.find(r => r.name === picked) ?? null;
  const hist = historySeries(shown?.history);
  const limit = v ? fmtSpan(v.threshold_s) : null;

  return (
    <div className="space-y-4">
      <Card pending={isPending(rf)}>
        <CardHeader title="Independent References" badge={<ProvenanceTag type="calculated" />}
          action={<StatusBadge variant={verdictVariant(v?.code)} label={v?.headline ?? 'UNKNOWN'} dot={false} />} />
        <CardBody>
          <ApiErrorNote error={rf.error} />
          <div className="text-[11px]" style={{ color:'var(--t2)' }}>{v?.detail ?? 'Reference data not loaded.'}</div>
          <div className="text-[10px] mt-2" style={{ color:'var(--t3)' }}>
            {countsLine(v)}{countsLine(v) && limit ? ' · ' : ''}{limit ? `limit ${limit}` : ''}
            {d?.as_of_utc ? ` · chrony read ${fmtUtc(d.as_of_utc)}` : ''}
          </div>
          <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>
            An independent reference is a server chrony measures but is not using to set the clock. The comparison
            reports agreement or disagreement between clocks. It does not say which clock is wrong, or why.
          </div>
        </CardBody>
      </Card>

      <Card pending={isPending(rf)}>
        <CardHeader title="Servers" badge={<ProvenanceTag type="external" />} />
        <CardBody className="p-0">
          <div className="table-scroll"><table className="w-full text-[11px]">
            <thead><tr>
              {['Server', 'chrony state', 'Stratum', 'Offset', '± bound', 'Delay', 'Last rx', 'Comparison'].map((h, i) => (
                <th key={h} style={{ ...TH, textAlign: i >= 2 && i <= 6 ? 'right' : 'left' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {refs.map(r => (
                <tr key={r.name} className="row-sep">
                  <td className="px-4 py-2 mono tabular">
                    <button onClick={() => setPicked(r.name)} className="underline" style={{ color: shown?.name === r.name ? 'var(--t1)' : 'var(--t2)' }}
                      title="Show this server's history below">{r.name}</button>
                  </td>
                  <td className="px-4 py-2 mono" style={{ color:'var(--t3)' }}>{r.state} {r.state_label}{r.reachable ? '' : ' · no answer'}</td>
                  <td className="px-4 py-2 mono tabular text-right" style={{ color:'var(--t3)' }}>{r.stratum}</td>
                  <td className="px-4 py-2 mono tabular text-right whitespace-nowrap" style={{ color:'var(--t1)' }}>{fmtSigned(r.offset_s) ?? 'UNKNOWN'}</td>
                  <td className="px-4 py-2 mono tabular text-right whitespace-nowrap" style={{ color:'var(--t3)' }}>{fmtSpan(r.error_bound_s) ?? 'UNKNOWN'}</td>
                  <td className="px-4 py-2 mono tabular text-right whitespace-nowrap" style={{ color:'var(--t2)' }}>{fmtSpan(r.delay_s) ?? 'UNKNOWN'}</td>
                  <td className="px-4 py-2 mono tabular text-right" style={{ color:'var(--t3)' }}>{r.lastrx_s === null ? 'never' : `${r.lastrx_s} s`}</td>
                  <td className="px-4 py-2"><StatusBadge variant={assessmentVariant(r.assessment)} label={r.assessment} dot={false} className="text-[9px]" /></td>
                </tr>
              ))}
              {d && !refs.length && <tr><td colSpan={8} className="px-4 py-3 text-[10px]" style={{ color:'var(--t3)' }}>
                No independent servers. Add some with the installer (GTP_INDEPENDENT_REFS=1), or see the deploy guide.</td></tr>}
              {!d && <tr><td colSpan={8} className="px-4 py-3 text-[10px]" style={{ color:'var(--t3)' }}>Reference data not loaded.</td></tr>}
            </tbody>
          </table></div>
          <div className="px-4 py-2 text-[10px]" style={{ color:'var(--t3)' }}>
            Offset: positive means the station's clock is ahead of that server. The bound is chrony's error bound for the
            server, which includes half the network delay. {d?.delay_note}
          </div>
          {(d?.excluded.length ?? 0) > 0 && (
            <div className="px-4 pb-3 text-[10px]" style={{ color:'var(--t3)' }}>
              Not counted: {d!.excluded.map(e => `${e.name} (${e.why})`).join('; ')}.
            </div>
          )}
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 @3xl:grid-cols-2 gap-4">
        <Card pending={isPending(rf)}>
          <CardHeader title={`Offset History — ${shown?.name ?? 'no server'}`} badge={<ProvenanceTag type="external" />} action={<ScaleToggle chart="ref-offset" />} />
          <CardBody>
            {hist.offset.data.length
              ? <TimeSeriesChart series={hist.offset} range="24h" chart="ref-offset" />
              : <div className="text-[10px] py-10 text-center" style={{ color:'var(--t3)' }}>No measurements recorded yet.</div>}
          </CardBody>
        </Card>
        <Card pending={isPending(rf)}>
          <CardHeader title={`Delay History — ${shown?.name ?? 'no server'}`} badge={<ProvenanceTag type="external" />} action={<ScaleToggle chart="ref-delay" />} />
          <CardBody>
            {hist.delay.data.length
              ? <TimeSeriesChart series={hist.delay} range="24h" chart="ref-delay" />
              : <div className="text-[10px] py-10 text-center" style={{ color:'var(--t3)' }}>
                  {d && !d.delay_available ? 'Delay is UNKNOWN: the chrony helper service is not publishing it.' : 'No measurements recorded yet.'}
                </div>}
          </CardBody>
        </Card>
      </div>
      <div className="text-[9px]" style={{ color:'var(--t3)' }}>
        History: one point per new measurement, at most one a minute, up to {d?.history.max_points ?? 1440} points per server. {d?.history.storage}.
      </div>
      <ELI5 text="The station sets its clock from GPS. These are other clocks on the Internet that it only listens to. If the station and most of them tell a different time, something deserves a look — but the comparison alone can't tell you which side is off." />
    </div>
  );
}
