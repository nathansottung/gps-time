# GPS Time — Design System Guidelines

A precision scientific instrument interface. Every decision should read as observatory control software or professional RF instrumentation — not a tech startup, not a gaming dashboard.

---

## Stance

**Professional scientific instrument.** Restrained, sophisticated, dark. Color is reserved for data and live state, not decoration. The UI chrome should be nearly colorless so that the measurements themselves stand out.

Do not:
- Use rounded cards (border-radius > 2px on panels)
- Use glow effects or neon
- Use gradients on surfaces (only in chart fills, never UI chrome)
- Use cyan/live color for anything other than the primary live reading
- Use more than 4 colors visible at once on any screen region

---

## Fonts

### Import (CSS entrypoint — must appear before all other CSS)

Fonts are **self-hosted**: the station UI must render correctly with no Internet connection, so never load fonts (or anything else) from a CDN at runtime. They are bundled from the `@fontsource` packages (SIL OFL-1.1):

```css
@import '@fontsource/inter/300.css';
@import '@fontsource/inter/400.css';
@import '@fontsource/inter/500.css';
@import '@fontsource/inter/600.css';
@import '@fontsource/jetbrains-mono/300.css';
@import '@fontsource/jetbrains-mono/400.css';
@import '@fontsource/jetbrains-mono/500.css';
@import '@fontsource/jetbrains-mono/600.css';
```

Weights 300–600 only. The 700 weight is not shipped.

### Application

| Role | Family | Weight | Notes |
|------|--------|--------|-------|
| Body / UI labels | Inter | 400 | Default for all prose and labels |
| Section headings | Inter | 600 | Only in uppercase + letter-spacing |
| Measurement values | JetBrains Mono | 400–500 | All numeric readings |
| Status / badges | JetBrains Mono | 500 | Uppercase, tracked |
| Code / identifiers | JetBrains Mono | 400 | Serial numbers, IPs, filenames |

### Rules

- All numeric measurements: `font-family: var(--font-mono); font-variant-numeric: tabular-nums`
- Use CSS class `.mono` for monospace + tabular, `.tabular` for tabular-only
- Section headers: `text-[9px] font-semibold uppercase tracking-[0.18em]` in `--t3` color
- Never use weight 700 (it is not shipped; the browser would synthesize a fake bold). Use 600 only for headings
- Never mix mono and sans within a single value+unit pair — keep units in sans at `--t3` alongside mono value

---

## Color Tokens

All tokens live in `:root` in `src/index.css`.

### Surfaces

```css
--bg:       #080809;   /* Page background — warm near-black */
--nav:      #0c0c10;   /* Sidebar / header */
--card:     #101014;   /* Card panels */
--card-hi:  #14141a;   /* Elevated: hover states, inputs, dropdowns */
--float:    #1c1c26;   /* Tooltips, floating elements */
```

**Surfaces must remain neutral-warm (not blue-tinted).** The distinction between bg, nav, and card is subtle but important — it creates the panel hierarchy without color.

### Borders

```css
--border-dim: rgba(255,255,255,0.04);   /* Internal row separators */
--border:     rgba(255,255,255,0.07);   /* Card/panel edges */
--border-em:  rgba(255,255,255,0.11);   /* Emphasized, hover, active */
```

Use opacity-based borders rather than hex colors — they adapt to any surface color.

### Text Hierarchy (4 levels)

```css
--t1: #e2e6ef;   /* Primary: live values, page headings, important data */
--t2: #8892aa;   /* Secondary: labels, field names, identifiers */
--t3: #4c5268;   /* Tertiary: section headers (uppercase), metadata, footnotes */
--t4: #282d3c;   /* Quaternary: barely-there markers, build info, placeholders */
```

**Use the correct level:**
- A measurement value → `--t1`
- The label next to that value → `--t2`
- A section title like "TIMING QUALITY" → `--t3`
- A timestamp in a footer or version string → `--t4`

### Live / Accent

```css
--live:        #4dc8e2;              /* Slightly desaturated cyan: live GPS readings */
--live-bright: #22d3ee;              /* The brightest cyan: only for THE primary reading */
--live-dim:    rgba(77,200,226,0.12);/* Background tint for live-data panels */

--accent:      #5b8cb8;              /* Steel blue: nav active, buttons, interactive */
--accent-dim:  rgba(91,140,184,0.10);/* Background tint for accent elements */
```

**`--live` / `--live-bright` must only be used for GPS/PPS-sourced real-time values.** The primary Δt reading gets `--live-bright`. Secondary live readings get `--live`. Everything else gets the text hierarchy.

**`--accent` is for interactive UI chrome** (nav active state, focused buttons, active tab underline, range selectors). Not for data.

### Status Colors

All status colors are desaturated — they signal state without visually shouting.

```css
/* Good / locked / nominal */
--good:        #3b8c5c;
--good-text:   #5ab87c;
--good-bg:     rgba(59,140,92,0.08);
--good-border: rgba(59,140,92,0.20);

/* Warning / holdover / degraded */
--warn:        #b07810;
--warn-text:   #d4a030;
--warn-bg:     rgba(176,120,16,0.08);
--warn-border: rgba(176,120,16,0.20);

/* Error / loss / critical */
--err:         #9e4040;
--err-text:    #c86060;
--err-bg:      rgba(158,64,64,0.08);
--err-border:  rgba(158,64,64,0.20);

/* Info / neutral call-out */
--info-text:   #5b8cb8;
--info-bg:     rgba(91,140,184,0.08);
--info-border: rgba(91,140,184,0.20);

/* Muted / unknown / offline */
--muted-text:  #5a6278;
--muted-bg:    rgba(90,98,120,0.08);
--muted-border:rgba(90,98,120,0.18);

/* Demo / synthetic data */
--demo-text:   #c07840;
--demo-bg:     rgba(192,120,64,0.08);
--demo-border: rgba(192,120,64,0.20);
```

### Provenance Colors

Every value has an epistemological origin. Use exactly these six labels, consistently:

| Label | Meaning | Examples |
|-------|---------|----------|
| `observed` | Directly measured by station hardware | PPS offset, satellite C/N₀, GNSS fix |
| `calculated` | Derived mathematically from observations | Light-distance equivalent, RMS, orthometric height from h − N |
| `modeled` | Output of a physical or statistical model for a present or past quantity | Geoid undulation, error budget terms |
| `predicted` | Forecast of a future value | Sunrise/sunset, satellite passes, holdover time-to-threshold |
| `inferred` | Reasoned from indirect evidence | Likely sky obstruction from C/N₀ patterns |
| `external` | Obtained from a source outside the station | Upstream NTP server values, space-weather feeds, downloaded datasets |

When a value's origin cannot be established, do not pick a label to fill the gap — show the value as UNKNOWN (`<StatusBadge variant="muted" />`).

```css
/* OBSERVED — directly measured by hardware */
--obs-text:   #4dc8e2;   --obs-bg: rgba(77,200,226,0.07);   --obs-border: rgba(77,200,226,0.18);

/* CALCULATED — derived mathematically from observations */
--calc-text:  #6092c8;   --calc-bg: rgba(96,146,200,0.07);  --calc-border: rgba(96,146,200,0.18);

/* MODELED — output of a physical or statistical model */
--mod-text:   #8870c0;   --mod-bg: rgba(136,112,192,0.07);  --mod-border: rgba(136,112,192,0.18);

/* PREDICTED — forecast of a future value */
--pred-text:  #c07898;   --pred-bg: rgba(192,120,152,0.07); --pred-border: rgba(192,120,152,0.18);

/* INFERRED — derived by reasoning from indirect evidence */
--inf-text:   #b8963c;   --inf-bg: rgba(184,150,60,0.07);   --inf-border: rgba(184,150,60,0.18);

/* EXTERNAL — from a source outside the station (tag border is dashed) */
--ext-text:   #9aa0ae;   --ext-bg: rgba(154,160,174,0.06);  --ext-border: rgba(154,160,174,0.22);
```

---

## Spacing

Base unit: 4px. Follow a consistent scale.

| Token | Value | Usage |
|-------|-------|-------|
| `py-[5px]` | 5px | MetricRow vertical padding |
| `px-4` | 16px | Card / panel horizontal padding |
| `py-3` | 12px | Card body vertical padding |
| `py-2.5` | 10px | Card header vertical padding |
| `gap-3` | 12px | Default grid/flex gap |
| `gap-4` | 16px | Section-level gap |
| `space-y-4` | 16px | Page-level vertical rhythm |
| `tracking-[0.18em]` | — | Section header letter-spacing |
| `tracking-[0.1em]` | — | Badge / tab letter-spacing |

---

## Components

### Card

```tsx
<Card>
  <CardHeader title="Section Name" badge={<StatusBadge .../>} action={<button.../>} />
  <CardBody>
    {/* content */}
  </CardBody>
</Card>
```

**Card rules:**
- `border-radius: 2px` (CSS `rounded-[2px]`)
- `box-shadow: inset 0 1px 0 rgba(255,255,255,0.045)` — the top-edge glass highlight. Required on all cards. Implemented via `.card-surface` class.
- `border: 1px solid var(--border)`
- `background: var(--card)`
- CardHeader title: `text-[9px] font-semibold uppercase tracking-[0.18em]` in `--t3`
- CardHeader `border-bottom: 1px solid var(--border-dim)` (not `--border`)

Never use:
- Rounded corners > 2px on cards
- Drop shadows on cards (only inset top highlight)
- Colored card backgrounds (except tinted contextual panels — see below)

### Contextual Panels (inside cards)

For sub-panels with semantic meaning, use tinted backgrounds:

```tsx
/* Live / GPS state */
style={{ background:'var(--live-dim)', border:'1px solid rgba(77,200,226,0.18)' }}

/* Status good */
style={{ background:'var(--good-bg)', border:'1px solid var(--good-border)' }}

/* Warning / holdover */
style={{ background:'var(--warn-bg)', border:'1px solid var(--warn-border)' }}

/* Interactive accent */
style={{ background:'var(--accent-dim)', border:'1px solid rgba(91,140,184,0.20)' }}

/* Neutral elevated */
style={{ background:'rgba(255,255,255,0.018)', border:'1px solid var(--border-dim)' }}
```

### MetricRow

```tsx
<MetricRow
  label="PPS availability (30d)"
  value="99.71"
  unit="%"
  uncertainty="0.02"        /* optional */
  provenance="observed"      /* optional: observed|calculated|modeled|predicted|inferred|external */
  muted                      /* optional: dims the label further to --t4 */
  large                      /* optional: uses text-base for the value */
/>
```

**Rules:**
- Label: `text-[11px]` in `--t2` (or `--t4` if `muted`)
- Value: `mono tabular text-[12px] font-medium` in `--t1`
- Unit: `text-[10px]` in `--t3`
- Separator: `border-bottom: 1px solid var(--border-dim)` (`.row-sep` class), none on last row
- All numbers must be monospace + tabular

### StatusBadge

```tsx
<StatusBadge variant="good" label="GPS PPS LOCKED" pulse />
<StatusBadge variant="warn" label="HOLDOVER" dot={false} />
<StatusBadge variant="info" label="STRATUM 1" />
<StatusBadge variant="muted" label="NOT CONNECTED" />
<StatusBadge variant="demo" label="DEMO" />
```

**Rules:**
- Text: `9px font-mono font-medium uppercase tracking-[0.1em]`
- Border-radius: `2px`
- Dot: 1px, rounded-full, optionally pulse-animated
- Do not use for decorative purposes — only for actual state

### ProvenanceTag

```tsx
<ProvenanceTag type="observed" />    /* cyan */
<ProvenanceTag type="calculated" />  /* steel blue */
<ProvenanceTag type="modeled" />     /* purple */
<ProvenanceTag type="predicted" />   /* rose */
<ProvenanceTag type="inferred" />    /* amber */
<ProvenanceTag type="external" />    /* neutral grey, dashed border */
```

**Apply to every value whose epistemological origin matters.** Place inline with the value or in the CardHeader beside the title. Size: `8px mono uppercase`.

### MaturityBadge

```tsx
<MaturityBadge level="supported" />    /* green */
<MaturityBadge level="experimental" /> /* amber */
<MaturityBadge level="research" />     /* purple */
<MaturityBadge level="planned" />      /* muted */
<MaturityBadge level="demo" />         /* orange */
```

Apply to any feature/module that is not fully production-supported.

### Tabs

```tsx
<Tabs
  tabs={['Overview', 'PPS Stats', 'Error Budget']}
  active={activeTab}
  onChange={setActiveTab}
/>
```

- Active tab: `--t1` text, `1.5px solid var(--accent)` bottom border
- Inactive: `--t3` text, hover to `--t2`
- Font: `10px font-medium uppercase tracking-[0.1em]`

### RangeSelector

```tsx
<RangeSelector ranges={['1h','24h','7d']} active={range} onChange={setRange} />
```

- Active: `border: 1px solid var(--accent)`, text `var(--accent)`, bg `var(--accent-dim)`
- Inactive: `border: 1px solid var(--border)`, text `var(--t3)`
- Font: `9px mono`

### Toggle

```tsx
<Toggle on={enabled} onChange={setEnabled} />
```

- Track on: `rgba(91,140,184,0.35)` (accent-dim)
- Thumb on: `var(--accent)`
- Track off: `var(--border-em)`
- Thumb off: `var(--t3)`

### ELI5 Expander

```tsx
<ELI5 text="Plain-language explanation of the measurement above." />
```

- Trigger link: `9px mono underline` in `--t4`, hover to `--t3`
- Expanded panel: `rgba(255,255,255,0.025)` bg, `--border-dim` border, `--t2` italic text, `11px`
- Place immediately after the metric it explains

---

## Tables

Standard data table pattern:

```tsx
<table className="w-full text-[11px]">
  <thead>
    <tr>
      <th style={{ color:'var(--t3)', fontWeight:400, fontFamily:'JetBrains Mono',
                   fontSize:10, letterSpacing:'0.05em', padding:'6px 16px',
                   borderBottom:'1px solid var(--border)', textAlign:'left' }}>
        Column
      </th>
    </tr>
  </thead>
  <tbody>
    <tr className="row-sep">
      <td className="px-4 py-2" style={{ color:'var(--t1)' }}>value</td>
      <td className="px-4 py-2 mono tabular" style={{ color:'var(--t2)' }}>data</td>
    </tr>
  </tbody>
</table>
```

Rules:
- No hover background change — too noisy in data-dense tables
- `.row-sep` for `border-bottom: 1px solid var(--border-dim)`, cleared on last row
- Header `fontWeight: 400` — not bold
- Numeric columns: `mono tabular` class
- Status columns: use `<StatusBadge>` or `<MaturityBadge>`
- Provenance columns: use `<ProvenanceTag>`

---

## Charts (Recharts)

### Universal chart configuration

```tsx
// Grid
<CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,0.05)" vertical={false} />

// Axes
<XAxis tick={{ fontSize:9, fontFamily:'JetBrains Mono', fill:'var(--t3)' }}
       tickLine={false} axisLine={{ stroke:'var(--border)' }} />
<YAxis tick={{ fontSize:9, fontFamily:'JetBrains Mono', fill:'var(--t3)' }}
       tickLine={false} axisLine={false} width={34} />

// Tooltip
<Tooltip content={<CustomTooltip />} />
```

### Custom tooltip pattern

```tsx
function ChartTip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tip">
      <div style={{ color:'var(--t3)', marginBottom:2 }}>{label}</div>
      <div style={{ color:'var(--live)' }}>{payload[0].value.toFixed(1)} {unit}</div>
    </div>
  );
}
```

`.chart-tip` CSS class:
```css
.chart-tip {
  background: var(--float);
  border: 1px solid var(--border-em);
  border-radius: 2px;
  padding: 6px 10px;
  font-family: var(--font-mono);
  font-size: 10px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}
```

### Chart color assignments

| Data series | Color |
|-------------|-------|
| Primary live measurement (Δt, signal) | `var(--live)` |
| Chart fill gradient (from) | `var(--live)` at 18% opacity |
| Chart fill gradient (to) | `var(--live)` at 0% opacity |
| Warning / outage duration | `var(--warn-text)` |
| Solar irradiance | `var(--warn-text)` |
| Good / availability | `var(--good-text)` |
| Error / outage marker | `var(--err-text)` |
| GPS satellites | `var(--live)` |
| GLONASS satellites | `var(--warn-text)` |
| Galileo satellites | `var(--mod-text)` |
| BeiDou satellites | `var(--good-text)` |

### SVG Sky Plot

- Background: `var(--bg)` fill (transparent)
- Concentric rings: `rgba(255,255,255,0.05)` stroke, 0.5px
- Horizon ring: `rgba(255,255,255,0.05)` stroke, 1px
- Azimuth spokes: same as rings
- Cardinal labels: `8px JetBrains Mono`, `var(--t4)`
- Satellite used: fill at 20% opacity, stroke at full opacity, `r=5`
- Satellite tracked only: same but `opacity={0.35}`, `r=4`
- SVID labels: `6.5px JetBrains Mono`, satellite system color

---

## Layout

### App shell

```
┌────────────────────────────────────────────┐
│  Header (h-11, --nav bg, --border bottom)  │
├──────────┬─────────────────────────────────┤
│ Sidebar  │ Main content area               │
│ (188px)  │ (overflow-y-auto, p-5)          │
│ --nav bg │ --bg                            │
│ --border │                                 │
│ right    │                                 │
└──────────┴─────────────────────────────────┘
```

### Page layout patterns

**Full-width card:**
```tsx
<Card>...</Card>
```

**2-column equal:**
```tsx
<div className="grid grid-cols-2 gap-4">...</div>
```

**3-column equal:**
```tsx
<div className="grid grid-cols-3 gap-4">...</div>
```

**12-column asymmetric (most overview pages):**
```tsx
<div className="grid grid-cols-12 gap-3">
  <div className="col-span-5">...</div>
  <div className="col-span-3">...</div>
  <div className="col-span-4">...</div>
</div>
```

**Page vertical rhythm:**
```tsx
<div className="space-y-4 page-enter">
```

The `.page-enter` class applies a 140ms fade-in-up animation on mount.

### Header layout

```
[Logo + Station name] ... [Status chips] ... [UTC clock | Local clock]
```

- Status chips: `h=~28px`, background `rgba(255,255,255,0.030)`, border `var(--border)`, text `var(--t3)`
- GPS LOCKED chip: uses `--good-bg` / `--good-border` / `--good-text`
- DEMO chip: uses `--demo-bg` / `--demo-border` / `--demo-text`
- UTC clock: `mono 11px` in `--t1`; LOCAL clock: `mono 11px` in `--t2`

### Sidebar

- Width: 188px fixed
- Group labels: `8px mono uppercase tracking-[0.18em]` in `--t4`
- Nav items: `11px Inter`, `--t2` inactive, `--t1` active
- Active item: `background: var(--accent-dim)`, `border-left: 2px solid var(--accent)`
- Nav icon: `12px`, `--t4` inactive, `var(--accent)` active
- Research items get a small `R` badge in `--mod-text`

---

## Navigation structure

```
Overview
── Measurement
   Timing & Reliability
   GNSS & Site
   Sun & Astronomy
── Station
   Network & Devices
   Radio & SDR
   Aviation
── Research            ← badge: R
   Distributed Obs.
── System
   Data & Logs
   Configure
   Administration
```

---

## Scientific terminology conventions

Always use correct scientific notation and units:

| Quantity | Symbol | Units |
|----------|--------|-------|
| Time offset | Δt | s, ms, µs, ns |
| Fractional frequency offset | Δf/f | dimensionless (ppm, ppb, or ×10⁻ⁿ) |
| Carrier-to-noise-density ratio | C/N₀ | dB-Hz |
| Ellipsoidal height | h | m |
| Orthometric height | H | m |
| Geoid undulation | N | m |
| Round-trip time | RTT | ms |
| Solar irradiance | — | W/m² |
| Daily irradiation | — | kWh/m²/day |
| Sampling rate | — | MS/s (megasamples per second) |

Use `×10⁻ⁿ` notation for fractional frequency offset (format with `fmtSci()` from `src/lib/units.ts`, e.g. `−1.24 × 10⁻⁹`). ppm/ppb may appear only as a secondary parenthetical, never alone. Rates of change use `s⁻¹` (e.g. `8.4 × 10⁻⁹ s⁻¹`), not ppb/s.

---

## Offline / Live distinction

The UI must always communicate data origin:

| Category | Visual treatment |
|----------|-----------------|
| GPS/PPS live value | `--live` or `--live-bright` color |
| Observed (hardware) | `<ProvenanceTag type="observed" />` |
| Calculated | `<ProvenanceTag type="calculated" />` |
| Modeled (no hardware) | `<ProvenanceTag type="modeled" />` |
| Predicted (future value) | `<ProvenanceTag type="predicted" />` |
| Inferred | `<ProvenanceTag type="inferred" />` |
| External source | `<ProvenanceTag type="external" />` |
| Demo/synthetic | Orange demo banner + `<MaturityBadge level="demo" />` |
| Requires network | `<StatusBadge variant="muted" label="network required" />` |
| Feature not implemented | `<MaturityBadge level="planned" />` |

Demo data must never appear to be real measurements. Always render `<DemoBanner />` at the top of the page content area when running in demo mode.

---

## CSS utility classes (defined in index.css)

| Class | Purpose |
|-------|---------|
| `.mono` | JetBrains Mono + tabular-nums |
| `.tabular` | font-variant-numeric: tabular-nums only |
| `.card-surface` | Card bg + border + inset top-highlight shadow |
| `.row-sep` | `border-bottom: 1px solid var(--border-dim)`, none on last |
| `.page-enter` | 140ms fade-in-up animation |
| `.pulse-dot` | 2.2s opacity pulse for live indicators |
| `.chart-tip` | Chart tooltip panel style |
| `.tab-active` | Active tab text + bottom border |
| `.tab-inactive` | Inactive tab text with hover |
| `.nav-item` | Base nav button + transition |
| `.nav-item.active` | Active nav state |
| `.toggle-on/off` | Toggle track states |
| `.toggle-thumb-on/off` | Toggle thumb states |
| `.tag-observed/calculated/modeled/predicted/inferred/external` | Provenance tag colors |
| `.badge-good/warn/error/info/muted/demo` | StatusBadge colors |
| `.mat-supported/experimental/research/planned/demo` | MaturityBadge colors |

---

## Do / Do not

### Do
- Use `style={{ color:'var(--t2)' }}` for labels — inline styles for token values keep them visible in JSX
- Use `.mono.tabular` on every numeric measurement
- Apply `.card-surface` to all panel elements
- Reserve `--live-bright` for exactly one primary value per screen
- Use `border-radius: 2px` (`rounded-[2px]`) consistently
- Apply `<ProvenanceTag>` to every measurement value where origin matters
- Write section labels as: `text-[9px] font-semibold uppercase tracking-[0.18em]` in `--t3`
- Separate internal card rows with `var(--border-dim)` (4% white), not `var(--border)` (7% white)
- Use the `.page-enter` class on every page root `<div>`

### Do not
- Use Tailwind color classes for surface/text colors (use CSS vars via inline `style={}`)
- Use `text-cyan-400`, `text-slate-*`, `bg-[#...]` — these bypass the token system
- Use rounded corners > 2px on cards or panels
- Use `--live` / `--live-bright` for UI chrome, buttons, or non-GPS data
- Add `hover:bg-*` to table rows — too noisy in dense scientific tables
- Use `font-weight: 700` (bold) anywhere in the interface
- Add box-shadow drop shadows to cards — only inset top highlights
- Use emojis in the UI
- Display synthetic demo values without the demo banner and `<MaturityBadge level="demo" />`
