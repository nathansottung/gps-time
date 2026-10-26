import { useStation } from '../api/station';
import { Card, CardHeader, CardBody, MaturityBadge, MetricRow, Toggle } from '../components/ui';
import { useModules, useTheme } from '../components/prefs';
import { OVERVIEW_CARDS, PAGE_MODULES, toggled } from '../lib/prefs';

// Configure: which modules this browser shows, and the theme (lib/prefs.ts). These replace the
// legacy saved-layout editor (owner decision 2026-10-19). Display only: nothing here changes the
// station, and other browsers keep their own choices.
const BTN = (active: boolean) => active
  ? { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }
  : { border:'1px solid var(--border)', color:'var(--t3)' };

function ModuleList({ items, hidden, onToggle, note }: {
  items: readonly { id: string; label: string }[]; hidden: string[]; onToggle: (id: string) => void; note: string;
}) {
  return (
    <>
      {items.map(it => (
        <div key={it.id} className="flex items-center justify-between py-[6px] row-sep">
          <span className="text-[11px]" style={{ color: hidden.includes(it.id) ? 'var(--t3)' : 'var(--t2)' }}>{it.label}</span>
          <Toggle on={!hidden.includes(it.id)} onChange={() => onToggle(it.id)} label={`Show ${it.label}`} />
        </div>
      ))}
      <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>{note}</div>
    </>
  );
}

export default function Configure() {
  const { api, isDemo, core } = useStation();
  const [modules, setModules] = useModules();
  const [theme, setTheme] = useTheme();
  const shown = PAGE_MODULES.length - modules.hiddenPages.length;
  return (
    <div className="space-y-4 page-enter">
      <div>
        <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Configure</h1>
        <p className="text-[10px] mt-0.5" style={{ color:'var(--t3)' }}>
          Display choices for this browser only. The station, its API and other browsers are not affected.
        </p>
      </div>

      <div className="grid grid-cols-1 @2xl:grid-cols-2 @5xl:grid-cols-3 gap-4">
        <Card>
          <CardHeader title={`Pages (${shown} of ${PAGE_MODULES.length} shown)`} />
          <CardBody>
            <ModuleList items={PAGE_MODULES} hidden={modules.hiddenPages}
              onToggle={id => setModules({ ...modules, hiddenPages: toggled(modules.hiddenPages, id) })}
              note="Hidden pages leave the sidebar; their data is still collected. Overview, Configure and Administration always show." />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Overview cards" />
          <CardBody>
            <ModuleList items={OVERVIEW_CARDS} hidden={modules.hiddenCards}
              onToggle={id => setModules({ ...modules, hiddenCards: toggled(modules.hiddenCards, id) })}
              note="Applies to the Overview's default layout (A). The timing chain, the clock and timing quality always show." />
          </CardBody>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Theme" />
            <CardBody>
              <div className="flex gap-1">
                {(['dark', 'night'] as const).map(t => (
                  <button key={t} onClick={() => setTheme(t)} aria-pressed={theme === t}
                    className="px-3 py-[5px] text-[10px] mono rounded-[2px]" style={BTN(theme === t)}>
                    {t === 'night' ? 'night (red)' : 'dark'}
                  </button>
                ))}
              </div>
              <div className="text-[9px] mt-2" style={{ color:'var(--t3)' }}>
                Night shows only red light, dimmed, to keep dark adaptation while observing. Also in the header (Night). Shared with the legacy pages in this browser.
              </div>
            </CardBody>
          </Card>

          <button onClick={() => { setModules({ hiddenPages: [], hiddenCards: [] }); setTheme('dark'); }}
            className="w-full px-3 py-2 text-[10px] mono rounded-[2px]" style={{ border:'1px solid var(--border)', color:'var(--t2)' }}>
            Show everything, dark theme
          </button>

          <Card>
            <CardHeader title="Data Source" badge={isDemo ? <MaturityBadge level="demo" /> : undefined} />
            <CardBody>
              <div className="text-[11px] mb-3" style={{ color:'var(--t3)' }}>
                {api.source === 'demo'
                  ? 'Client-side demo adapter: synthetic data, no station contacted. Remove ?source=demo to use the station.'
                  : isDemo
                    ? 'Station API in server demo mode (GTP_DEMO): synthetic data.'
                    : 'Station API (same origin). Values are what the station reports.'}
              </div>
              <MetricRow label="Mode" value={isDemo ? 'DEMO' : 'LIVE'} />
              <MetricRow label="Client adapter" value={api.source === 'demo' ? 'demo (src/api/demo.ts)' : 'http (src/api/client.ts)'} />
              <MetricRow label="Station reachable" value={api.source === 'demo' ? 'n/a' : core.data ? 'yes' : core.error ? 'no' : null} />
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
