import { useState } from 'react';
import { Card, CardHeader, CardBody, MetricRow, StatusBadge, MaturityBadge, ELI5, Tabs, ProvenanceTag } from '../components/ui';
import { sdrDevices } from '../data/demo';
import { fmtSci } from '../lib/units';

const TIER_LABELS = [
  '', // 0
  'USB receive-only',
  'Frequency-calibrated',
  'PPS/epoch-aligned',
  'PPS + reference clock',
  'Hardware timestamped',
];
const TIER_COLORS = [
  '', 'text-slate-500', 'text-cyan-400/70', 'text-cyan-400', 'text-blue-400', 'text-purple-400',
];

// Simulated waterfall data
function WaterfallDisplay({ freqMHz }: { freqMHz: number }) {
  const rows = 24, cols = 80;
  return (
    <div className="w-full overflow-hidden rounded-sm border border-[#222840]">
      <div className="flex items-center justify-between px-3 py-1 bg-[#0e1118] border-b border-[#222840]">
        <span className="mono text-[10px] text-slate-500">Waterfall — {freqMHz} MHz ± 1.024 MHz</span>
        <span className="mono text-[10px] text-slate-600">2.048 MS/s</span>
      </div>
      <svg width="100%" height={rows*3} viewBox={`0 0 ${cols} ${rows}`} preserveAspectRatio="none">
        {Array.from({ length: rows }, (_, r) =>
          Array.from({ length: cols }, (_, c) => {
            const noise = Math.random() * 0.3;
            // Simulate a center signal spike and some interference
            const sig = freqMHz === 1090 && Math.abs(c - cols/2) < 3 ? 0.9 : 0;
            const v = Math.min(1, noise + sig * Math.random());
            // Color: dark blue → cyan → yellow
            const hue = v < 0.5 ? `rgba(34,211,238,${v*0.5})` : `rgba(251,191,36,${(v-0.5)*1.5})`;
            return <rect key={`${r}-${c}`} x={c} y={r} width={1} height={1} fill={hue}/>;
          })
        )}
      </svg>
    </div>
  );
}

// SDR device card
function SDRCard({ dev }: { dev: typeof sdrDevices[0] }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <Card>
      <CardHeader
        title={dev.service}
        badge={<StatusBadge variant={dev.state==='active'?'good':'muted'} label={dev.state.toUpperCase()} />}
        action={
          <button onClick={() => setExpanded(!expanded)}
            className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors mono">
            {expanded ? 'collapse' : 'details'}
          </button>
        }
      />
      <CardBody>
        <div className="grid grid-cols-2 gap-x-6">
          <div>
            <MetricRow label="Device" value={dev.name} />
            <MetricRow label="Tuner" value={dev.tuner} />
            <MetricRow label="Serial" value={dev.serial} />
          </div>
          <div>
            <MetricRow label="Center freq." value={`${dev.freqMHz} MHz`} />
            <MetricRow label="Sample rate" value={`${dev.sampleRateMsps} MS/s`} />
            <MetricRow label="Gain" value={typeof dev.gain === 'number' ? `${dev.gain} dB` : dev.gain} />
          </div>
        </div>
        <div className="mt-2 flex items-center gap-3">
          <span className="text-[10px] text-slate-600">Timestamp tier:</span>
          <span className={`mono text-[10px] ${TIER_COLORS[dev.tier]}`}>
            {dev.tier} — {TIER_LABELS[dev.tier]}
          </span>
        </div>
        {dev.calibPpm !== undefined && (
          <MetricRow label="Freq. calibration Δf/f" value={fmtSci(dev.calibPpm * 1e-6)} unit={`(${dev.calibPpm} ppm)`} provenance="observed" />
        )}
        {expanded && (
          <div className="mt-3">
            <WaterfallDisplay freqMHz={dev.freqMHz} />
          </div>
        )}
        <div className="mt-3 p-2 bg-amber-400/5 border border-amber-400/10 rounded-sm text-[10px] text-amber-400/70">
          Clock discipline accuracy ≠ SDR sample-timestamp accuracy. Tier {dev.tier} device.
        </div>
      </CardBody>
    </Card>
  );
}

// RF modules table
const modules = [
  { name:'Spectrum / RFI monitoring',  maturity:'supported',    sdr:'Any',        notes:'Continuous FFT, power logging' },
  { name:'ADS-B 1090 MHz',             maturity:'supported',    sdr:'RTL-SDR #1', notes:'dump1090-fa' },
  { name:'UAT 978 MHz',                maturity:'supported',    sdr:'RTL-SDR #2', notes:'dump978-fa' },
  { name:'WWV/CHU Doppler analysis',   maturity:'experimental', sdr:'RTL-SDR #3', notes:'10/5/2.5/15/20 MHz' },
  { name:'WSPR / FST4W',               maturity:'experimental', sdr:'RTL-SDR #3', notes:'Weak signal propagation' },
  { name:'Radiosonde reception',        maturity:'experimental', sdr:'Any',        notes:'RS41, RS92, iMet' },
  { name:'Meteor scatter',              maturity:'research',     sdr:'Any',        notes:'BRAMS protocol' },
  { name:'Satellite reception (LEO)',   maturity:'research',     sdr:'Airspy',     notes:'NOAA APT, GOES LRIT' },
  { name:'RF TDoA (authorized)',        maturity:'research',     sdr:'Multi',      notes:'Amateur fox-hunt experiments only' },
  { name:'Hardware timestamping',       maturity:'planned',      sdr:'—',          notes:'Phase-characterized capture' },
];

const maturityOrder: Record<string, number> = { supported:0, experimental:1, research:2, planned:3 };

export default function RadioSDR() {
  const [tab, setTab] = useState('Devices');
  const sorted = [...modules].sort((a,b) => maturityOrder[a.maturity] - maturityOrder[b.maturity]);

  return (
    <div className="space-y-4 page-enter">
      <div className="flex items-baseline justify-between">
        <h1 className="text-sm font-semibold text-[#dde3ef]">Radio & SDR</h1>
        <StatusBadge variant="info" label={`${sdrDevices.length} DEVICES ACTIVE`} />
      </div>

      <Tabs tabs={['Devices','RF Modules','Timing Tiers']} active={tab} onChange={setTab} />

      {tab === 'Devices' && (
        <div className="grid grid-cols-1 gap-4">
          {sdrDevices.map(dev => <SDRCard key={dev.id} dev={dev}/>)}

          {/* Airspy placeholder */}
          <Card>
            <CardHeader title="Experimental Capture" badge={<StatusBadge variant="muted" label="NOT CONNECTED" />} action={<MaturityBadge level="research" />} />
            <CardBody>
              <div className="text-[11px] text-slate-600">Airspy HF+ Discovery — configured for experimental IQ capture. Device not currently connected.</div>
              <MetricRow label="Assigned service" value="Experimental" muted />
              <MetricRow label="Planned tier" value="4 — PPS + reference clock" muted />
            </CardBody>
          </Card>
        </div>
      )}

      {tab === 'RF Modules' && (
        <Card>
          <CardHeader title="RF Observation Modules" />
          <CardBody className="p-0">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-[#222840]">
                  {['Module','Maturity','SDR','Notes'].map(h => (
                    <th key={h} className="text-left px-4 py-2.5 text-slate-600 font-normal">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map(m => (
                  <tr key={m.name} className="border-b border-[#1a1e2e] hover:bg-[#1a1e2e] transition-colors">
                    <td className="px-4 py-2.5 text-slate-300">{m.name}</td>
                    <td className="px-4 py-2.5"><MaturityBadge level={m.maturity as any} /></td>
                    <td className="px-4 py-2.5 mono text-slate-500">{m.sdr}</td>
                    <td className="px-4 py-2.5 text-slate-600">{m.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}

      {tab === 'Timing Tiers' && (
        <Card>
          <CardHeader title="SDR Timestamp Capability Tiers" />
          <CardBody>
            <div className="mb-3 p-2 bg-amber-400/5 border border-amber-400/15 rounded-sm text-[10px] text-amber-400/80">
              Important: GPS/PPS clock discipline accuracy is not automatically the sample-timestamp accuracy of an SDR device. Tiers define what is actually achieved.
            </div>
            <div className="space-y-3">
              {[
                { tier:1, label:'USB Receive-Only', desc:'Sample timestamps derived from USB host clock. ±ms uncertainty typical. No GPS relationship.', color:'text-slate-500' },
                { tier:2, label:'Frequency-Calibrated', desc:'Oscillator calibrated against GPS-disciplined reference. Fractional frequency error ~10⁻⁶ to 10⁻⁹. Time origin not precisely known.', color:'text-cyan-400/70' },
                { tier:3, label:'PPS/Epoch-Aligned', desc:'Sample epoch snapped to PPS epoch at start of capture. Drift accumulates. Useful for short captures.', color:'text-cyan-400' },
                { tier:4, label:'PPS + Reference Clock', desc:'Ongoing frequency correction plus PPS epoch alignment. Sub-µs sample timestamp accuracy for extended captures.', color:'text-blue-400' },
                { tier:5, label:'Hardware Timestamped', desc:'Device provides per-sample hardware timestamps from a calibrated oscillator phase-characterized against PPS. Best achievable.', color:'text-purple-400' },
              ].map(t => (
                <div key={t.tier} className="flex gap-4 p-3 bg-[#0e1118] border border-[#1a1e2e] rounded-sm">
                  <div className={`mono text-lg font-light ${t.color} w-6 text-center`}>{t.tier}</div>
                  <div className="flex-1">
                    <div className={`text-[12px] font-medium ${t.color}`}>{t.label}</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">{t.desc}</div>
                    <div className="mt-1 text-[10px] text-slate-600">
                      Currently installed: {sdrDevices.filter(d=>d.tier===t.tier).map(d=>d.id).join(', ') || 'none'}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
