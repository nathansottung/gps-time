# reference-adsb

**Maturity:** experimental, 0.1.0 (#134). Types: reference and source. Spec: `docs/specs/SPEC-EXTENSIBILITY.md` → "Reference modules to build first", item 1.

Aircraft broadcast their own GPS position. With a position and the station's site, the time a signal takes from the aircraft to the station follows from geometry. This module turns a local ADS-B decoder's view of the sky into **self-reported references**: a list of transmitters with positions, and a predicted delay to the station with a bound. It is the pattern for every self-reported reference (aircraft, ships, radiosondes): the position is `external`, it is checked before use, and rejections are counted, never silent.

It covers both links:

| Band | Link | Decoder | File read (default) |
|---|---|---|---|
| 1090 MHz | ADS-B 1090ES | readsb or dump1090-fa | `/run/readsb/aircraft.json` |
| 978 MHz | UAT (US, below 18,000 ft) | dump978-fa with skyaware978 | `/run/skyaware978/aircraft.json` |

Each decoder needs its own SDR. The module reads only those files; it has no network permission and no device.

**Installing the decoders:** `sudo GTP_SDR=1 GTP_SDR_1090_SERIAL=... GTP_SDR_978_SERIAL=... bash install.sh` installs readsb and builds dump978-fa with skyaware978. Both write to the default paths above, in RAM, with no outside network and no station position (`docs/deploy/sdr-stack.md`).

## What it does with each aircraft

Checks, in order:

| Rejected as | When |
|---|---|
| `no_position` | no latitude/longitude |
| `not_self_reported` | MLAT (`type` "mlat", or `lat` in `mlat`), TIS-B or ADS-R (`type` "tisb…"/"adsr…", or `lat` in `tisb`), Mode S. MLAT positions are computed by a network; TIS-B and ADS-R are re-broadcast by a ground station, so the signal doesn't come from the aircraft |
| `stale` | position older than `max_age_s` (5 s) |
| `accuracy_unknown`, `low_accuracy` | no NACp, or NACp below `min_nac_p` (8: 95 % bound under 92.6 m) |
| `no_altitude` | no geometric or barometric altitude (e.g. "ground") |
| `out_of_range` | beyond `max_range_km` (450 km), or below the horizon |
| `implausible_jump` | moved faster than `max_speed_mps` (700 m/s) since its previous accepted position |

For an accepted aircraft:
- **Delay** (`calculated`): the slant range from the site to the self-reported position (WGS84 ECEF), divided by c.
- **Bound** (`calculated`): an approximate 95 % bound, root-sum-square of:
  - the position's NACp bound;
  - the altitude's (GVA for geometric altitude; ±300 m for barometric);
  - movement since the fix (age × ground speed);
  - the site's height (±100 m if only its height above sea level is known);
  - in rounded privacy mode, the site's rounding (about ±7 km, which dominates).
- **Not modelled,** as the note says: the troposphere (a few metres) and the decoder's own latency.

## Privacy

- The site comes only from `ctx.site()`, already filtered by the station's privacy mode.
- **Hidden:** nothing is predicted. The module emits only counts, with `site_available` false.
- **Rounded:** delays are computed from the rounded site and carry its rounding in the bound.
- The module never outputs the site. Aircraft positions are what the aircraft broadcast.

## What it emits

Every `interval_s` (10 s):
- **A summary:** aircraft seen per band (`external`), references accepted, rejections by reason, whether a site was available.
- **One observation per accepted aircraft,** best-bounded first, at most `max_per_band` (10) per band:
  - `transmitter` (band:ICAO address), `frequency_hz`, `lat`, `lon`, `alt_m` (`external`);
  - `delay_s`, `uncertainty_s`, `range_m` (`calculated`).

## Enable it on a station

1. Run the decoder(s) so they write `aircraft.json`, readable by every user (they usually are, under `/run`).
2. Copy this folder to `/opt/gps-time-pi/modules/reference-adsb/` (`sudo chmod -R a+rX`).
3. Administration → Experimental modules: turn the switch on, then this module. Paths and limits go in `module_config` in the station config.
4. `gps-time-modules.service` must be enabled (`docs/modules/README.md`). No drop-in is needed: the module needs no device and no network.

## Try it

```bash
python -m gps_time_pi.modkit demo reference-adsb
```

This replays `fixtures/aircraft-1090.json` and `aircraft-978.json`: synthetic traffic around the US Naval Observatory example site, with one aircraft for each rejection reason. It emits the summary and 8 references.

## Limits

- **Not yet run against a live decoder.** The field names follow readsb's and skyaware978's documented `aircraft.json`. A decoder that writes them differently gives `no_position`/`stale` counts rather than wrong delays.
- **No measured arrival times yet.** Comparing predicted with measured delays needs an SDR source timestamping 1090/978 MHz messages (SPEC-RF-NODE-AND-TDOA). That is a later analysis module (`analysis-tower-delay-check` is the pattern).
- **Self-reported positions can be wrong,** even with a good NACp. Use many aircraft and look at the spread, never one.
