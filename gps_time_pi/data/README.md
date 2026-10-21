# Bundled sky data

Each file keeps the license of its source, not the MIT License of the rest of the project. All four are built by `tools/build_sky_data.py` from the sources below, and `--check` confirms the committed files match them exactly. Don't edit them by hand: change the script, or the source version, and rebuild.

| File | Contents | Source | License |
|---|---|---|---|
| `messier.json` | the 110 Messier objects: position (J2000, degrees), type, magnitude, common names, constellation | [OpenNGC](https://github.com/mattiaverga/OpenNGC) by Mattia Verga, commit `be3cd6c54988` (2026-10-18), `NGC.csv` and `addendum.csv` | **CC BY-SA 4.0** ([`third_party/licenses/CC-BY-SA-4.0-OpenNGC.txt`](../../third_party/licenses/CC-BY-SA-4.0-OpenNGC.txt), which lists the changes) |
| `catalog.json` | `stars`: every star with a proper name to magnitude 2.6 (99); `planets`: the planet names | [d3-celestial](https://github.com/ofrohn/d3-celestial) by Olaf Frohn, commit `7e720a3de062`, `stars.6.json` and `starnames.json` (star data from the XHIP compilation of Hipparcos) | BSD 3-Clause ([`third_party/licenses/BSD-3-Clause-d3-celestial.txt`](../../third_party/licenses/BSD-3-Clause-d3-celestial.txt)); the planet list is the project's (MIT) |
| `stars.json` | stars to magnitude 4.5 for the sky map: `[RA°, Dec°, V mag]` (921) | d3-celestial `stars.6.json`, same commit | BSD 3-Clause |
| `constellations.json` | constellation stick figures, `[RA°, Dec°]` points (89 figures; Serpens has two) | d3-celestial `constellations.lines.json`, same commit | BSD 3-Clause |

**One departure from OpenNGC (owner, 2026-10-21, #102):** OpenNGC lists M102 as a duplicate of M101. `messier.json` maps M102 to NGC 5866 (Spindle Galaxy) instead, a common identification, using OpenNGC's own NGC 5866 row; the name and a note saying it departs from OpenNGC are the project's additions (`OVERRIDES` in the build script).

Conversions: d3-celestial stores right ascension as longitude in −180…180°; these files use 0…360°. Rounding is to 0.001° (`stars.json`), 0.01° (`constellations.json`) and 0.0001° (`catalog.json`, `messier.json`).

Provenance check (2026-10-21, #101): the files bundled before then were compared with these sources. `stars.json`, `constellations.json` and the named stars matched d3-celestial exactly (not the Yale Bright Star Catalogue an earlier design note named). 107 of the 110 Messier objects matched OpenNGC; M40, M45 and M102, and seven magnitudes OpenNGC doesn't carry, came from elsewhere and were replaced with OpenNGC's values (M102 then mapped to NGC 5866 as above, #102).

To rebuild: download the two repositories (or just the files above), then

```sh
python tools/build_sky_data.py --openngc <OpenNGC checkout> --d3 <d3-celestial checkout> [--check]
```
