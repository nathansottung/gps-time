# Design review against Guidelines.md, 2026-10-26

**Status:** done (#130). The owner asked for a pass over the web UI on spacing, type scale, number alignment, contrast, focus states, and empty and loading states: list the deviations, then fix them.

## How it was checked

- `web/e2e/design-audit.ts` runs in the browser on every page and every tab, at 1280 px, with demo data. It checks:
  - **contrast:** each text run against the background it actually sits on, composited, WCAG 2.2 AA;
  - **type scale:** sizes off the scale;
  - **weights:** none above 600;
  - **tabular figures:** numbers standing alone in their element.
- **Focus:** Tab through each page; every focused control must show a ring.
- **Loading:** with the station API held (no answer), then failing.
- **Source:** greps for Tailwind palette classes, radii, letter-spacing, sizes and padding.
- **By eye:** screenshots of pages before and after.

Before: about 2,180 findings from the browser audit, plus the source findings below. After: none. `e2e/design.spec.ts` keeps it that way in CI.

## Deviations and fixes

| # | Area | Deviation found | Count | Fix |
|---|---|---|---|---|
| 1 | Contrast | `--t3` text at 2.2–2.5:1 and `--t4` text at 1.2–1.4:1, both below 4.5:1. They come from the guidelines' own token values, used as specified (section headers, units, notes, chart ticks, build info, placeholders) | ~1,840 text runs (and 202 chart ticks, painted `--t3` by CSS) | Tokens raised, keeping hue and order: `--t2` #8892aa → #9fa7ba, `--t3` #4c5268 → #8188a3 (4.8:1 worst case). `--t4` is now decorative only (#3a4052); its 132 text uses moved to `--t3` |
| 2 | Contrast | `--muted-text` (UNKNOWN, NOT OBSERVABLE badges) 2.95:1; `--mod-text` ("modeled" tag) 4.34:1; `--err-text` 4.26:1 on `--float` | 25 | #5a6278 → #8089a0; #8870c0 → #927dc6; #c86060 → #d06868 |
| 3 | Contrast | Text dimmed with `opacity` (holdover figure, tracked-only satellite labels at 35 %) | 4 | No opacity on text; tracked-only satellites keep a dim circle and a full-colour label |
| 4 | Contrast | Light-distance table: the highlighted row's note `--t3` on `--live-dim` 4.42:1 | 1 | `--t2` in that row |
| 5 | Colour tokens | Tailwind palette and hex classes (`bg-cyan-400`, `text-slate-500`, `bg-[#0e1118]`, `text-[#dde3ef]`…) instead of tokens | ~35 (GNSS, Radio & SDR, Secondary, Timing) | Token styles: warning panels use `--warn-*`; constellations use the guideline chart colours; tables use `--t1`–`--t3` and `.row-sep`; buttons use status tokens |
| 6 | Tables | Row hover background on the RF modules table ("No `hover:bg-*` on table rows") | 1 | Removed; `.row-sep` |
| 7 | Radius | `rounded-sm`/`rounded` (4px in Tailwind v4) on panels, buttons and legend swatches | 26 | `rounded-[2px]` |
| 8 | Type scale | No page-title size: 14px on most pages, 13px on the Overview | 13 | One page-title size, 14px (`text-sm`), added to the scale |
| 9 | Type scale | Display sizes 18 and 24px (and a 15px line) beside 16, 20 and 36 | 7 | Display set 16, 20, 36, 44, 72px; 18 → 20 or 16, 24 → 20, the 15px UTC line → 16 |
| 10 | Type scale | 7px research badge in the nav | 1 | 8px |
| 11 | Letter-spacing | 0.12, 0.14, 0.15 and 0.22em and `tracking-wider` beside the three guideline values | 17 | Set: 0.18em section headers, 0.12em sub-labels, 0.1em badges and tabs, 0.08em chips |
| 12 | Numbers | The station name (an identifier) and a few numbers in proportional figures | 12 | Mono; numbers in prose stay prose |
| 13 | Loading | `MetricRow` showed UNKNOWN before the first answer, the same as "the station can't establish this" | most cards | Loading mark `…` while the station's first answers or the card's own request are pending (`useStarting()`, `<Card pending>`) |
| 14 | Loading / empty | "Not loaded." shown both while loading and after a failure; "No samples" shown while loading | 6 | `LoadingNote`, `EmptyNote` with the reason, and "the station did not answer" after a failure |
| 15 | Focus | The ring (`:focus-visible`) existed but wasn't in the guidelines; a date field's calendar button showed none | 1 control | Fields show the ring on any focus (`:focus`, `:focus-within`); documented |
| 16 | Spacing | Card padding and gaps follow the scale; `CardBody` everywhere, `p-0` only for edge-to-edge tables. Page rhythm `space-y-4`, except the Overview's grid view (`space-y-3`, cards closer together on purpose) | — | No change; the Overview exception is noted here |

## Changed in Guidelines.md

- **New sections:** the type scale, the contrast rule, focus states, and loading/empty/unknown.
- **Revised:**
  - the text tokens, with their worst-case ratios;
  - `--t4` is now decorative only;
  - the `MetricRow` muted label is `--t3`;
  - ELI5, sidebar and sky-plot colours;
  - the Do-not list.

## Not changed

- The night theme's own values (only the red channel survives its overlay; contrast there is a different question).
- Chart colours for data series.
