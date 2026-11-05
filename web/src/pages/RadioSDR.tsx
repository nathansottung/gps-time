import { useState } from 'react';
import { Card, CardHeader, CardBody, MaturityBadge, Tabs } from '../components/ui';
import { sdrDevices } from '../api/previews';
import { useStation } from '../api/station';
import { AirbandCard, WebSdrCard } from '../components/websdr';
import { ClipsCard } from '../components/clips';
import { AircraftStackCard } from '../components/aircraftstack';

// RF modules table
const modules = [
  { name:'Spectrum / RFI monitoring',  maturity:'supported',    sdr:'Any',        notes:'Continuous FFT, power logging' },
  { name:'ADS-B 1090 MHz',             maturity:'supported',    sdr:'by serial',  notes:'readsb, tar1090 map' },
  { name:'UAT 978 MHz',                maturity:'supported',    sdr:'by serial',  notes:'dump978-fa, skyaware978 map' },
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
  const { isDemo } = useStation();

  return (
    <div className="space-y-4 page-enter">
      <div className="flex items-baseline justify-between">
        <h1 className="text-sm font-semibold" style={{ color:'var(--t1)' }}>Radio & SDR</h1>
        <MaturityBadge level="experimental" />
      </div>

      <Tabs tabs={['Devices','RF Modules','Timing Tiers']} active={tab} onChange={setTab} />

      {tab === 'Devices' && <AircraftStackCard />}
      {tab === 'Devices' && <WebSdrCard />}
      {tab === 'Devices' && <AirbandCard />}
      {tab === 'Devices' && <ClipsCard />}

      {tab === 'RF Modules' && (
        <Card>
          <CardHeader title="RF Observation Modules" />
          <CardBody className="p-0">
            <div className="table-scroll"><table className="w-full text-[11px]">
              <thead>
                <tr style={{ borderBottom:'1px solid var(--border)' }}>
                  {['Module','Maturity','SDR','Notes'].map(h => (
                    <th key={h} className="text-left px-4 py-2.5 font-normal mono text-[10px]" style={{ color:'var(--t3)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map(m => (
                  <tr key={m.name} className="row-sep">
                    <td className="px-4 py-2.5" style={{ color:'var(--t1)' }}>{m.name}</td>
                    <td className="px-4 py-2.5"><MaturityBadge level={m.maturity as any} /></td>
                    <td className="px-4 py-2.5 mono" style={{ color:'var(--t2)' }}>{m.sdr}</td>
                    <td className="px-4 py-2.5" style={{ color:'var(--t3)' }}>{m.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          </CardBody>
        </Card>
      )}

      {tab === 'Timing Tiers' && (
        <Card>
          <CardHeader title="SDR Timestamp Capability Tiers" />
          <CardBody>
            <div className="mb-3 p-2 rounded-[2px] text-[10px]" style={{ background:'var(--warn-bg)', border:'1px solid var(--warn-border)', color:'var(--warn-text)' }}>
              Important: GPS/PPS clock discipline accuracy is not automatically the sample-timestamp accuracy of an SDR device. Tiers define what is actually achieved.
            </div>
            <div className="space-y-3">
              {[
                { tier:1, label:'USB Receive-Only', desc:'Sample timestamps derived from USB host clock. ±ms uncertainty typical. No GPS relationship.' },
                { tier:2, label:'Frequency-Calibrated', desc:'Oscillator calibrated against GPS-disciplined reference. Fractional frequency error ~10⁻⁶ to 10⁻⁹. Time origin not precisely known.' },
                { tier:3, label:'PPS/Epoch-Aligned', desc:'Sample epoch snapped to PPS epoch at start of capture. Drift accumulates. Useful for short captures.' },
                { tier:4, label:'PPS + Reference Clock', desc:'Ongoing frequency correction plus PPS epoch alignment. Sub-µs sample timestamp accuracy for extended captures.' },
                { tier:5, label:'Hardware Timestamped', desc:'Device provides per-sample hardware timestamps from a calibrated oscillator phase-characterized against PPS. Best achievable.' },
              ].map(t => (
                <div key={t.tier} className="flex gap-4 p-3 rounded-[2px]" style={{ background:'rgba(255,255,255,0.018)', border:'1px solid var(--border-dim)' }}>
                  <div className="mono text-base font-light w-6 text-center" style={{ color:'var(--t1)' }}>{t.tier}</div>
                  <div className="flex-1">
                    <div className="text-[12px] font-medium" style={{ color:'var(--t1)' }}>{t.label}</div>
                    <div className="text-[11px] mt-0.5" style={{ color:'var(--t2)' }}>{t.desc}</div>
                    {isDemo && <div className="mt-1 text-[10px]" style={{ color:'var(--t3)' }}>
                      Currently installed: {sdrDevices.filter(d=>d.tier===t.tier).map(d=>d.id).join(', ') || 'none'}
                    </div>}
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
