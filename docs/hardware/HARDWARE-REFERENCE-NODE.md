# HARDWARE — Reference Node Parts List

## Status

DRAFT. Part numbers are examples; confirm current availability and prices before buying. No prices are listed on purpose because they change.

## Goal

A standard node others can build so results from different owners are comparable.

## Tiers

### Tier 1 — Timing station (current design)

| Part | Example | Notes |
|---|---|---|
| Computer | Raspberry Pi 4 or 5 | Pi 5 or CM4/CM5 for hardware timestamping later |
| GNSS + PPS | Uputronics GPS HAT (MAX-M8Q) | Current development board |
| Antenna | Active L1 GNSS antenna with ground plane | Outdoors with open sky is the biggest single improvement |
| Storage | High-endurance microSD or SSD | SSD preferred for long runs |
| Power | Official supply; small UPS optional | Under-voltage upsets timing |
| Network | Ethernet | Wi-Fi off |

### Tier 2 — Precision station

| Part | Example | Notes |
|---|---|---|
| GNSS | u-blox ZED-F9T (timing) or ZED-F9P (positioning) board | See docs/hardware/zed-f9-dual-band.md |
| Antenna | Multi-band (L1/L2 or L1/L5) survey-grade antenna | Fixed mount, open sky |
| Computer | Pi 5 or CM5 | Hardware timestamping for PTP |
| Enclosure | Weatherproof box, cable glands | Keep electronics indoors if possible, antenna outside |

### Tier 3 — RF node

| Part | Example | Notes |
|---|---|---|
| SDR | RTL-SDR Blog V4 | Same model across nodes for comparisons |
| Antennas | Wideband discone; 1090 MHz for ADS-B | |
| Filters/LNA | FM-band notch, 1090 MHz filter + LNA | Reduce overload |
| Computer | Separate Pi 5 or mini PC | Keep SDR load off the timing station |
| Time | NTP from the station, or own PPS | |
| Optional | GPSDO with 10 MHz output | For disciplined frequency |

### Tier 4 — Sensor add-ons

| Sensor | Example |
|---|---|
| Seismometer | Raspberry Shake 1D/3D |
| Infrasound | Raspberry Boom, or Shake & Boom |
| VLF lightning | Loop antenna + sound-card receiver |
| Muons | CosmicWatch-style scintillator + SiPM |
| All-sky | Low-light camera with fisheye lens, dew heater |
| Magnetometer | RM3100-class or fluxgate |
| Weather | Pressure/temperature/humidity sensor (e.g. BME280-class) |

## Siting notes

- GNSS antenna: open sky, away from walls and metal.
- Seismometer: on a concrete slab, away from appliances.
- Magnetometer: away from steel, power lines and moving vehicles.
- Infrasound: sheltered from wind.
- Record each site's details privately; share only approximate location.

## Next steps

- Confirm part availability.
- Build one Tier 3 node and test FM TDOA against the Tier 1 station.
