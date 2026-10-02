import { useState } from 'react';
import { useStation } from '../api/station';
import { Card, CardHeader, CardBody, StatusBadge, MaturityBadge, MetricRow, Toggle } from '../components/ui';

type Widget = { id: string; title: string; enabled: boolean; size: 'normal'|'wide'; page: string; };
type Page   = { id: string; title: string; icon: string; };

const PRESETS = ['Timing Station','Ham Radio','Astronomy','Weather Station','RF Observatory','Everything','Start Blank'];

const defaultWidgets: Widget[] = [
  { id:'timing-quality',   title:'Timing Quality',           enabled:true,  size:'wide',   page:'Overview' },
  { id:'holdover',         title:'Holdover',                 enabled:true,  size:'wide',   page:'Overview' },
  { id:'gnss-summary',     title:'GNSS Summary',             enabled:true,  size:'normal', page:'Overview' },
  { id:'sun-daylight',     title:'Sun & Daylight',           enabled:true,  size:'normal', page:'Overview' },
  { id:'network-ntp',      title:'Network & NTP',            enabled:true,  size:'normal', page:'Overview' },
  { id:'solar-irradiance', title:'Solar Irradiance',         enabled:true,  size:'normal', page:'Overview' },
  { id:'data-packs',       title:'Data Packs / Offline',     enabled:true,  size:'normal', page:'Overview' },
  { id:'moon-night',       title:'Moon & Night Sky',         enabled:false, size:'normal', page:'Overview' },
  { id:'offset-history',   title:'Offset History Chart',     enabled:true,  size:'wide',   page:'Timing' },
  { id:'pps-timeline',     title:'PPS Availability Timeline',enabled:true,  size:'wide',   page:'Timing' },
  { id:'holdover-scatter', title:'Holdover Performance',     enabled:true,  size:'normal', page:'Timing' },
  { id:'error-thresholds', title:'Time-to-Error Thresholds', enabled:true,  size:'normal', page:'Timing' },
  { id:'error-budget',     title:'Timing Error Budget',      enabled:true,  size:'wide',   page:'Timing' },
  { id:'sat-table',        title:'Satellite Table',          enabled:true,  size:'wide',   page:'GNSS' },
  { id:'sky-plot',         title:'Sky Plot',                 enabled:true,  size:'normal', page:'GNSS' },
  { id:'sky-obstruction',  title:'Sky Obstruction Map',      enabled:true,  size:'normal', page:'GNSS' },
];

const defaultPages: Page[] = [
  { id:'overview',     title:'Overview',             icon:'○' },
  { id:'timing',       title:'Timing & Reliability', icon:'∿' },
  { id:'gnss',         title:'GNSS & Site',          icon:'◎' },
  { id:'sun',          title:'Sun & Astronomy',      icon:'☀' },
  { id:'network',      title:'Network & Devices',    icon:'⊕' },
  { id:'radio',        title:'Radio & SDR',          icon:'≋' },
  { id:'aviation',     title:'Aviation',             icon:'✈' },
  { id:'distributed',  title:'Distributed Obs.',     icon:'⊗' },
  { id:'data',         title:'Data & Logs',          icon:'▤' },
  { id:'configure',    title:'Configure',            icon:'⊞' },
];

// Shared styles
const btnBase = 'px-3 py-[5px] text-[10px] rounded-[2px] mono transition-colors';
const thStyle: React.CSSProperties = { color:'var(--t3)', fontWeight:400, textAlign:'left', padding:'6px 16px', fontSize:10, fontFamily:'JetBrains Mono', letterSpacing:'0.05em', borderBottom:'1px solid var(--border)' };
const tdBase = 'px-4 py-2';

export default function Configure() {
  const [widgets, setWidgets] = useState<Widget[]>(defaultWidgets);
  const [pages,   setPages]   = useState<Page[]>(defaultPages);
  const [eli5,     setEli5]   = useState(false);
  const [units,    setUnits]  = useState<'metric'|'imperial'>('metric');
  const [precision, setPrecision] = useState<'standard'|'high'|'scientific'>('standard');
  const [activePreset, setActivePreset] = useState('');
  const [editingPage, setEditingPage] = useState<string|null>(null);
  const [saved, setSaved] = useState(false);
  const [tab, setTab] = useState<'pages'|'widgets'|'global'>('widgets');

  const toggleWidget = (id: string) => setWidgets(ws => ws.map(w => w.id===id ? {...w,enabled:!w.enabled} : w));
  const setWidgetSize = (id: string, size: 'normal'|'wide') => setWidgets(ws => ws.map(w => w.id===id ? {...w,size} : w));

  // Preview only: the station's saved layout (GET/POST /api/dashboard) uses the
  // legacy widget model and is still edited on the legacy /configure page.
  const handleSave = () => { setSaved(true); setTimeout(()=>setSaved(false), 2000); };
  const { api, isDemo, core } = useStation();

  const handlePreset = (p: string) => {
    setActivePreset(p);
    const on = (ids: string[]) => setWidgets(ws => ws.map(w=>({...w,enabled:ids.includes(w.id)})));
    if (p==='Start Blank')      setWidgets(ws=>ws.map(w=>({...w,enabled:false})));
    else if (p==='Everything')  setWidgets(ws=>ws.map(w=>({...w,enabled:true})));
    else if (p==='Timing Station') on(['timing-quality','holdover','gnss-summary','network-ntp','data-packs','offset-history','pps-timeline','holdover-scatter','error-thresholds','error-budget']);
    else if (p==='Astronomy')   on(['timing-quality','gnss-summary','sun-daylight','moon-night','solar-irradiance']);
  };

  const widgetPages = [...new Set(widgets.map(w=>w.page))];

  return (
    <div className="space-y-4 page-enter">
      {/* Heading row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[13px] font-semibold" style={{ color:'var(--t1)' }}>Configure Dashboard</h1>
          <p className="text-[10px] mt-0.5" style={{ color:'var(--t3)' }}>Manage pages, widgets, and display preferences</p>
        </div>
        <div className="flex gap-2">
          {[['Import JSON',''], ['Export JSON','']].map(([label]) => (
            <button key={label} className={btnBase} disabled title="Not implemented yet"
              style={{ border:'1px solid var(--border)', color:'var(--t4)' }}>
              {label}
            </button>
          ))}
          <button onClick={handleSave} className={`${btnBase} font-medium`}
            style={saved
              ? { border:'1px solid var(--good-border)', color:'var(--good-text)', background:'var(--good-bg)' }
              : { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }}>
            {saved ? 'Applied (not saved)' : 'Apply preview'}
          </button>
        </div>
      </div>

      <div className="text-[10px] px-3 py-2 rounded-[2px]"
        style={{ background:'var(--warn-bg)', border:'1px solid var(--warn-border)', color:'var(--warn-text)' }}>
        Design preview: changes here are not saved to the station and do not change the other pages yet.
        The station&apos;s saved layout is edited on the legacy <a href="../configure" style={{ color:'inherit', textDecoration:'underline' }}>/configure</a> page.
      </div>

      {/* Presets */}
      <Card>
        <CardHeader title="Layout Presets" />
        <CardBody>
          <div className="flex flex-wrap gap-1.5">
            {PRESETS.map(p => (
              <button key={p} onClick={() => handlePreset(p)}
                className={btnBase}
                style={activePreset===p
                  ? { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }
                  : { border:'1px solid var(--border)', color:'var(--t3)' }}>
                {p}
              </button>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Tab bar */}
      <div className="flex gap-0" style={{ borderBottom:'1px solid var(--border)' }}>
        {(['widgets','pages','global'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-[10px] font-medium uppercase tracking-[0.1em] transition-colors ${tab===t ? 'tab-active' : 'tab-inactive'}`}>
            {t}
          </button>
        ))}
      </div>

      {/* ── Widgets tab ─────────────────────────────────────────────────────── */}
      {tab==='widgets' && (
        <div className="space-y-4">
          {widgetPages.map(page => (
            <Card key={page}>
              <CardHeader title={`${page} — Widgets`} />
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr>
                      <th style={{ ...thStyle, width:'60%' }}>Widget</th>
                      <th style={{ ...thStyle, textAlign:'center' }}>Visible</th>
                      <th style={{ ...thStyle, textAlign:'center' }}>Size</th>
                    </tr>
                  </thead>
                  <tbody>
                    {widgets.filter(w=>w.page===page).map(w => (
                      <tr key={w.id} className="row-sep">
                        <td className={`${tdBase} py-2.5`} style={{ color: w.enabled ? 'var(--t1)' : 'var(--t4)' }}>{w.title}</td>
                        <td className={`${tdBase} py-2.5`} style={{ textAlign:'center' }}>
                          <Toggle on={w.enabled} onChange={() => toggleWidget(w.id)} />
                        </td>
                        <td className={`${tdBase} py-2.5`} style={{ textAlign:'center' }}>
                          <div className="flex justify-center gap-1">
                            {(['normal','wide'] as const).map(s => (
                              <button key={s} onClick={() => setWidgetSize(w.id, s)}
                                className="px-2 py-[3px] text-[9px] mono rounded-[2px] transition-colors"
                                style={w.size===s
                                  ? { border:'1px solid var(--accent)', color:'var(--accent)' }
                                  : { border:'1px solid var(--border)', color:'var(--t4)' }}>
                                {s}
                              </button>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* ── Pages tab ───────────────────────────────────────────────────────── */}
      {tab==='pages' && (
        <Card>
          <CardHeader title="Page Management"
            action={
              <button className={`${btnBase}`} style={{ color:'var(--accent)', border:'none', background:'none' }}>
                + Add Page
              </button>
            }
          />
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr>
                  <th style={{ ...thStyle, width:32 }}>#</th>
                  <th style={thStyle}>Icon</th>
                  <th style={thStyle}>Page Title</th>
                  <th style={{ ...thStyle, textAlign:'center' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pages.map((p, i) => (
                  <tr key={p.id} className="row-sep">
                    <td className={`${tdBase} py-2.5 mono`} style={{ color:'var(--t4)' }}>{i+1}</td>
                    <td className={`${tdBase} py-2.5 mono text-base`} style={{ color:'var(--t2)' }}>{p.icon}</td>
                    <td className={`${tdBase} py-2.5`} style={{ color:'var(--t1)' }}>
                      {editingPage===p.id ? (
                        <input autoFocus defaultValue={p.title}
                          onBlur={e => { setPages(ps=>ps.map(pp=>pp.id===p.id?{...pp,title:e.target.value}:pp)); setEditingPage(null); }}
                          className="px-2 py-[3px] rounded-[2px] text-[11px] mono outline-none w-48"
                          style={{ background:'var(--card-hi)', border:'1px solid var(--accent)', color:'var(--live)' }}/>
                      ) : p.title}
                    </td>
                    <td className={`${tdBase} py-2.5`} style={{ textAlign:'center' }}>
                      <div className="flex justify-center gap-3">
                        <button onClick={()=>setEditingPage(p.id)} className="mono text-[10px] transition-colors" style={{ color:'var(--t3)' }}>rename</button>
                        {i>0          && <button onClick={()=>setPages(ps=>{const a=[...ps];[a[i],a[i-1]]=[a[i-1],a[i]];return a;})} className="mono text-[10px]" style={{ color:'var(--t3)' }}>↑</button>}
                        {i<pages.length-1 && <button onClick={()=>setPages(ps=>{const a=[...ps];[a[i],a[i+1]]=[a[i+1],a[i]];return a;})} className="mono text-[10px]" style={{ color:'var(--t3)' }}>↓</button>}
                        <button onClick={()=>setPages(ps=>ps.filter(pp=>pp.id!==p.id))} className="mono text-[10px] transition-colors" style={{ color:'var(--err-text)', opacity:0.6 }}>remove</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* ── Global tab ──────────────────────────────────────────────────────── */}
      {tab==='global' && (
        <div className="space-y-4">
          <Card>
            <CardHeader title="Display Options" />
            <CardBody>
              <div className="space-y-0">
                {/* ELI5 */}
                <div className="flex items-center justify-between py-3 row-sep">
                  <div>
                    <div className="text-[12px]" style={{ color:'var(--t1)' }}>ELI5 Explanations</div>
                    <div className="text-[10px] mt-0.5" style={{ color:'var(--t3)' }}>Show "What does this mean?" on advanced measurements</div>
                  </div>
                  <Toggle on={eli5} onChange={setEli5} />
                </div>
                {/* Units */}
                <div className="flex items-center justify-between py-3 row-sep">
                  <div>
                    <div className="text-[12px]" style={{ color:'var(--t1)' }}>Units</div>
                    <div className="text-[10px] mt-0.5" style={{ color:'var(--t3)' }}>Height, distance, and temperature display</div>
                  </div>
                  <div className="flex gap-1">
                    {(['metric','imperial'] as const).map(u => (
                      <button key={u} onClick={()=>setUnits(u)} className={btnBase}
                        style={units===u
                          ? { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }
                          : { border:'1px solid var(--border)', color:'var(--t3)' }}>
                        {u}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Precision */}
                <div className="flex items-center justify-between py-3">
                  <div>
                    <div className="text-[12px]" style={{ color:'var(--t1)' }}>Display Precision</div>
                    <div className="text-[10px] mt-0.5" style={{ color:'var(--t3)' }}>Significant figures shown for measurements</div>
                  </div>
                  <div className="flex gap-1">
                    {(['standard','high','scientific'] as const).map(pr => (
                      <button key={pr} onClick={()=>setPrecision(pr)} className={btnBase}
                        style={precision===pr
                          ? { border:'1px solid var(--accent)', color:'var(--accent)', background:'var(--accent-dim)' }
                          : { border:'1px solid var(--border)', color:'var(--t3)' }}>
                        {pr}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>

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

          <button onClick={()=>{ setWidgets(defaultWidgets); setPages(defaultPages); setEli5(false); setUnits('metric'); setPrecision('standard'); setActivePreset(''); }}
            className={`${btnBase} py-2`}
            style={{ border:'1px solid var(--err-border)', color:'var(--err-text)', opacity:0.65 }}>
            Reset to Defaults
          </button>
        </div>
      )}
    </div>
  );
}
