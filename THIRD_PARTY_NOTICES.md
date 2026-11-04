# Third-party notices

GPS Time's own code and documentation are under the MIT License (`LICENSE`). This file lists the third-party software and data it includes, installs or downloads, under their own licenses. Nothing here is relicensed by the project.

**In this repository** means the files are committed here. **Shipped** means they are inside the built web UI or the Pi bundle. **Installed** means `install.sh` fetches them onto a station from their usual source. **Downloaded** means the station fetches them at install or run time.

## Data in this repository

| File | What | Source | License | Notes |
|---|---|---|---|---|
| `gps_time_pi/data/messier.json` | the 110 Messier objects: positions, types, magnitudes, common names | [OpenNGC](https://github.com/mattiaverga/OpenNGC) by Mattia Verga, commit `be3cd6c54988`; **verified** 2026-10-21 and rebuilt from it by `tools/build_sky_data.py` | **CC BY-SA 4.0** | "Contains data from OpenNGC by Mattia Verga, CC BY-SA 4.0." This file is an adapted work and is itself CC BY-SA 4.0, not MIT; the changes are listed in `third_party/licenses/CC-BY-SA-4.0-OpenNGC.txt`. One entry departs from OpenNGC: M102 is mapped to NGC 5866 (Spindle Galaxy), where OpenNGC lists it as a duplicate of M101. |
| `gps_time_pi/data/catalog.json` (`stars`), `gps_time_pi/data/stars.json` | named bright stars, and the sky map's stars to magnitude 4.5 | [d3-celestial](https://github.com/ofrohn/d3-celestial) by Olaf Frohn, commit `7e720a3de062` (`stars.6.json`, `starnames.json`; its star data are from the XHIP compilation of Hipparcos, Anderson & Francis 2012); **verified** 2026-10-21: identical | BSD 3-Clause | Not the Yale Bright Star Catalogue, as an earlier design note said. The planet list in `catalog.json` is the project's. |
| `gps_time_pi/data/constellations.json` | constellation stick figures | d3-celestial `constellations.lines.json`, same commit; **verified** 2026-10-21: identical | BSD 3-Clause | |
| `tests/fixtures/` | sample chrony, gpsd, leap-second and TLE outputs for the tests | written for this project, or short excerpts of public-domain files (IERS/IANA leap-second list) | MIT (project) / public domain | |

## Shipped in the web UI (`web/dist`)

Bundled by Vite from npm at build time. These are the production dependencies; `pnpm licenses list --prod` lists them with versions.

| Package(s) | License |
|---|---|
| react, react-dom, scheduler | MIT |
| recharts, and its dependencies (@reduxjs/toolkit, immer, reselect, redux, clsx, decimal.js-light, eventemitter3, victory-vendor, and others) | MIT (victory-vendor: MIT AND ISC) |
| d3-array, d3-color, d3-format, d3-interpolate, d3-path, d3-scale, d3-shape, d3-time, d3-time-format, d3-timer, internmap (via recharts) | ISC |
| d3-ease (via recharts) | BSD 3-Clause |
| lucide-react | ISC |
| @fontsource/inter (Inter, © 2016 The Inter Project Authors) | SIL Open Font License 1.1 |
| @fontsource/jetbrains-mono (JetBrains Mono, © 2020 The JetBrains Mono Project Authors) | SIL Open Font License 1.1 |

The fonts are served from the station itself (no font CDN). The OFL's text travels with them: `third_party/licenses/OFL-1.1-Inter.txt` and `OFL-1.1-JetBrains-Mono.txt` (copied from the packages), shipped in the Pi bundle with this file.

Build-time tools (not shipped): Vite, Tailwind CSS, TypeScript, Vitest, oxfmt, @vitejs/plugin-react, under their own (MIT or Apache-2.0) licenses.

## Installed on a station (Python, from PyPI into the station's venv)

| Package | License | Notes |
|---|---|---|
| skyfield | MIT | astronomy |
| jplephem, sgp4 (skyfield dependencies) | MIT | |
| numpy | BSD 3-Clause | |
| certifi (skyfield dependency) | MPL 2.0 | |
| cryptography | Apache 2.0 or BSD 3-Clause (dual) | Ed25519 station key: signs observation files. Its wheels bundle OpenSSL (Apache 2.0). |
| cffi, pycparser (cryptography dependencies) | MIT, BSD 3-Clause | |
| tzfpy | MIT | Its embedded time-zone boundaries come from timezone-boundary-builder, which is derived from OpenStreetMap data (© OpenStreetMap contributors, ODbL 1.0). Used offline to find the display zone from the station position. |

The system packages (`gpsd`, `chrony`, `pps-tools`, Python) come from Debian under their own licenses. With `GTP_WEBSDR=1`, OpenWebRX+ (`openwebrx`, AGPL-3.0, with csdr and its connectors under GPL-3.0) comes from its maintainer's apt repository (luarvique.github.io/ppa); none of it is in the bundle.

## Downloaded by a station

| Data | Source | Terms | When |
|---|---|---|---|
| JPL DE440s planetary ephemeris (`de440s.bsp`, about 32 MB) | NASA JPL (via Skyfield's mirror) | US government work, public domain | `install.sh`; not committed |
| Satellite orbital elements (TLE / OMM) | CelesTrak | CelesTrak's terms of use | only when the operator runs `python -m gps_time_pi.tle_fetch`; the web service never fetches |
| Leap-second table | IANA tzdata `leap-seconds.list` (from the IERS), read from the station's tzdata package | public domain | already on the station |
| UT1 − UTC | IERS Bulletin A, if the operator puts a copy on the station | IERS terms | operator's choice |

## BSD 3-Clause notice (d3-celestial, d3-ease)

`gps_time_pi/data/README.md` gives each data file's source, version and license, and how to rebuild it.

d3-celestial: Copyright (c) 2015, Olaf Frohn. All rights reserved. (Its own LICENSE file is in `third_party/licenses/BSD-3-Clause-d3-celestial.txt`.) d3-ease: Copyright the d3 authors (Mike Bostock). All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
