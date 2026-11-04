# Bench kit

**Status:** list, 2026-10-26 (#127); station and RF parts with checked links and prices added 2026-11-04 (#169). Models are examples, not endorsements. Check current specifications on the maker's datasheet before buying.

**Prices and links are dated.** Each price is what the linked page showed on **2026-11-04**, in that page's currency, before tax and shipping. Each link was opened that day and showed the product. Prices, stock and pages change; several pages showed a price but "sold out" (noted). No affiliate links. Parts whose page couldn't be opened that day are named at the end of each section, without a link or price.

Two parts: the **timing-validation kit** (Levels 1 and 2, below, no prices), then the **station and RF parts** (GNSS, antennas, coax, surge protection, SDR, VLF, all-sky camera, mast), with prices.

What it takes to validate a station's timing from outside the Pi: [`second-pulse.md`](second-pulse.md) (system clock against PPS), and a second station ([`../deploy/second-station.md`](../deploy/second-station.md)). The station parts themselves are in [`../hardware/HARDWARE-REFERENCE-NODE.md`](../hardware/HARDWARE-REFERENCE-NODE.md).

## Level 1: system clock against PPS (second pulse)

Enough to run `secpulse` and `pps_compare`.

| Item | Need | Examples | Notes |
|---|---|---|---|
| **Time-interval counter** *or* scope | one of them | see the two rows below | a counter is simpler for long runs; a scope shows the edges |
| Time-interval counter | single-shot time-interval resolution of 1 ns or better, two inputs, CSV/USB/LAN logging | used HP/Agilent 53131A or 53132A; Keysight 53220A/53230A; Pendulum CNT-90/91 | check that it logs one reading per second for hours. Older counters may need GPIB; plan the logging |
| Oscilloscope | 2 channels, ≥ 100 MHz, ≥ 1 GSa/s, delay measurement with logging or export | Rigol DS1000Z family; Siglent SDS1000X-E family | export of a measurement per trigger varies by model; test a short run first |
| Probes | 2 × 10× passive, or short coax to 1 MΩ inputs | the scope's own probes | measure each channel's delay, or use equal lengths |
| BNC tee and short coax | tap the receiver's PPS without moving it | BNC T, RG-58 patch leads | keep the tap high impedance (1 MΩ input) |
| Header-to-BNC lead | the Pi's GPIO pin and a ground pin to BNC | Dupont-to-BNC lead, or a small adapter board | short; a 3.3 V output into 1 MΩ |
| Line driver (only for 50 Ω inputs) | buffer the Pi's 3.3 V output | a 74LVC1G125-class buffer with a series resistor, or a PPS distribution amplifier | a bare Pi pin into 50 Ω is a heavy load with a slow edge |

## Level 2: an independent reference

To say anything about PPS against UTC. Choose at least one.

| Item | What it adds | Examples | Notes |
|---|---|---|---|
| Second GNSS receiver with its own PPS | another receiver on the same sky; a receiver-specific error shows as a difference | ZED-F9T timing board; a second MAX-M8Q board | both receivers still use GNSS; a shared error (antenna, site, constellation) doesn't show |
| GNSS-disciplined oscillator (GPSDO) with 1 PPS and 10 MHz outputs | a reference that holds through short GNSS outages, and a 10 MHz timebase for the counter | Leo Bodnar GPS reference clocks; Trimble Thunderbolt-class units (used) | disciplined by GNSS too; its holdover is what makes it independent during an outage |
| 10 MHz reference into the counter | the counter's timebase stops being the weak link on long runs | the GPSDO's 10 MHz output | only if the counter has an external reference input |

## For a second station sharing an antenna (setup A)

| Item | Need | Notes |
|---|---|---|
| GNSS splitter, 2-way, active | one port passes DC to the antenna, the other has a DC block with a load | two receivers powering one antenna can damage one; check which port passes DC |
| Matched short GNSS cables | equal lengths from splitter to each receiver | or measure each and record the difference |

## Recording

- **Cable delays:** measure them (a scope with a tee and an open end, or the counter) or use equal lengths. Note the coax type: about 5 ns per metre for solid-PE coax.
- **What was connected:** channel A, channel B, trigger levels and slopes, the instrument's timebase (internal or 10 MHz), the date. `pps_compare` prints what it assumed; keep that with the result.
- **Keep instrument files outside the repository.** They are real station data. Only summaries go into the docs, as for the soak runs.

# Station and RF parts (prices as of 2026-11-04)

## GNSS receivers with PPS

| Item | Example | Price | Notes |
|---|---|---|---|
| Multi-band timing board | [SparkFun GNSS Timing Breakout ZED-F9T-20B (GPS-30975)](https://www.sparkfun.com/sparkfun-gnss-timing-breakout-zed-f9t-20b-qwiic.html) | USD 314.95 | in stock; 2 timepulse SMA outputs plus the antenna SMA; USB-C. It replaces the retired ZED-F9T board (GPS-18774, ZED-F9T-00B). Check its bands against the antenna |
| Single-band navigation board | [SparkFun GPS Breakout NEO-M9N, SMA (GPS-17285)](https://www.sparkfun.com/sparkfun-gps-breakout-neo-m9n-sma-qwiic.html) | USD 76.50 | in stock; a navigation module, not a timing one (30 ns time-pulse accuracy on the page) |
| Budget PPS HAT | [Waveshare MAX-M8Q GNSS HAT](https://www.waveshare.com/product/raspberry-pi/hats/max-m8q-gnss-hat.htm) | USD 34.99 | the MAX-M8Q, as on the reference node's HAT; antenna included; check which GPIO carries PPS |
| Budget PPS HAT | [Adafruit Ultimate GPS HAT (2324)](https://www.adafruit.com/product/2324) | USD 29.95 | in stock; PPS on GPIO 4, not the `uputronics` profile's GPIO 18: pick the profile or the PPS pin as in [`../HARDWARE-PROFILES.md`](../HARDWARE-PROFILES.md); not a timing receiver |
| GNSS reference clock | [Leo Bodnar Mini Precision GPS Reference Clock](https://www.leobodnar.com/shop/index.php?main_page=product_info&products_id=301) | GBP 132.00 | in stock; a programmable frequency output (400 Hz–810 MHz); check the datasheet for a 1 PPS output before using it as a Level 2 reference |

Not checked on 2026-11-04 (the pages answered HTTP 429): the reference node's own HAT, the Uputronics GPS/RTC expansion board (MAX-M8Q), at Uputronics and The Pi Hut.

## GNSS antennas and an active splitter

| Item | Example | Price | Notes |
|---|---|---|---|
| L1/L5 patch | [u-blox ANN-MB5 (SparkFun GPS-25071)](https://www.sparkfun.com/u-blox-multi-band-active-gnss-antenna-l1-l5-ann-mb5.html) | USD 42.50 | in stock; 3 m RG174, SMA; magnetic base; needs a ground plane (gain is given on a 12 cm plate) |
| L1/L5 antenna | [SparkFun GNSS L1/L5 Multi-Band High Precision Antenna, 5 m (GPS-23814)](https://www.sparkfun.com/gnss-l1-l5-multi-band-high-precision-antenna-5m-sma.html) | USD 99.95 | in stock; SAW pre-filter; 5 m cable, SMA |
| L1/L2 survey-style | [TOP106 L1/L2 Surveying Antenna (SparkFun GPS-17751)](https://www.sparkfun.com/gnss-multi-band-l1-l2-surveying-antenna-tnc-top106.html) | USD 199.95 | in stock; 40 dB LNA; TNC female; 5/8"-11 thread |
| L1/L5 timing antenna | [L-com HG-GPSL1L5-40](https://www.l-com.com/l1-l5-gnss-antenna-1166-1218-1559-1606-mhz-type-n-female-43-db-hg-gpsl1l5-40) | USD 460.99 | in stock; 40 dB LNA; N female; sold for timing |
| Active splitter, 1×2 (setup A) | [GPS Networking ALDCBS1X2 (NavtechGPS)](https://www.navtechgps.com/gps_networking_aldcbs1x2_active_antenna_splitter_1x2/) | USD 380.00 | J1 passes DC to the antenna; J2 is DC-blocked with a 200 Ω load, which is what setup A needs; L1/L2; several connector options |
| DC-blocked splitter | [Tallysman TW151 (NavtechGPS)](https://www.navtechgps.com/?p=13342) | no price shown | DC blocked on **both** receiver ports: the antenna needs its own feed. Not the setup-A part |

Not checked (HTTP 403): the GPS Source S12S splitter, the ArduSimple triple-band survey antenna.

## Coax and connectors

| Item | Example | Price | Notes |
|---|---|---|---|
| Low-loss coax | [LMR-400, by the foot (Fleeman Anderson & Bird)](https://fab-corp.com/lmr-400-by-the-foot) | USD 1.65 / ft | 5.1 dB per 100 ft at 1500 MHz on the page: about **1.7 dB per 10 m** near L1 |
| Low-loss coax | [LMR-240, per foot (Fleeman Anderson & Bird)](https://fab-corp.com/bulk-lmr-coax-cable/lmr-r-240-per-foot) | USD 1.10 / ft | 9.9 dB per 100 ft at 1500 MHz: about **3.2 dB per 10 m** near L1 |
| Jumper | [SMA male – N male, LMR-240, 1.5 ft (ChannelComp)](https://channelcomp.com/low-loss-sma-male-to-n-male-cable-assembly-using-lmr-240-coax-1-5-ft-with-times-microwave-components) | USD 50.44 | Times Microwave parts |
| Adapter | [Amphenol 242113, SMA female – N male (RF Parts)](https://www.rfparts.com/242113.html) | USD 13.90 | in stock; 50 Ω |
| Adapter | [Amphenol 242114, N male – SMA male (RF Parts)](https://www.rfparts.com/242114.html) | USD 18.90 | in stock; DC–18 GHz |

The loss figures are the distributor's copy of the maker's table (dB per 100 ft at 1500 MHz, converted). Foam-dielectric coax like LMR is faster than the solid-PE figure above (about 5 ns per metre): take the velocity factor from the datasheet when you record a cable delay.

Not checked (HTTP 403): the Rosenberger SMA–N adapter at DigiKey.

## Lightning and surge protection

| Item | Example | Price | Notes |
|---|---|---|---|
| GNSS arrestor (DC pass) | [PolyPhaser GPS-06NFSF (BSW)](https://bswusa.com/polyphaser-gps-06nfsf/) | USD 148.74 | **out of stock** on the page; 1.2–1.6 GHz; passes up to 6 V DC to the antenna; N female – SMA female bulkhead |
| GNSS arrestor (DC pass) | [RAKwireless GPS SPD (datasheet)](https://docs.rakwireless.com/product-categories/accessories/gps-spd/datasheet/) | no price shown | 1500–1650 MHz; 6 V / 500 mA DC pass; N female – N male |
| SDR feed arrestor (DC pass) | [Proxicast ANT-241-002, SMA female bulkhead](https://www.proxicast.com/shopping/ANT-241-002) | USD 19.95 | in stock; DC–6 GHz, passes a bias-tee supply; ground lug |
| Ground rod | [ROHN 5/8" × 8 ft copper-bonded (3 Star)](https://www.3starinc.com/58_x_8_foot_ground_rod_copper_clad.html) | USD 34.00 | UL listed |
| Mast ground clamp | [3 Star GC-2, bronze, 1.25–2" OD](https://www.3starinc.com/tower_base_copper_ground_clamp) | USD 12.95 | |
| Ground wire | [#6 solid bare copper, 10 ft (3 Star)](https://www.3starinc.com/ground-wire-bonding-blocks-clamps-rods) | USD 18.95 | the coax ground blocks on the same page are F-type (75 Ω TV): not for 50 Ω GNSS or SDR feeds |

What's needed, by name only:
- an arrestor on each coax where it enters the building, on a grounded plate or bulkhead;
- a grounding electrode (a rod, or the existing one), a mast ground clamp and conductor;
- a bond from that ground to the building's electrical-service grounding electrode, done by a qualified electrician to local code.

Match each arrestor's DC rating to what it passes: the GNSS antenna's supply (3.3–5 V) or an SDR bias tee (4.5 V on the RTL-SDR Blog dongles). An arrestor reduces the risk; it doesn't make a direct strike safe.

Not checked: Times-Protect LP-GPX-05-NFF (HTTP 404 and 403).

## SDR gear

| Item | Example | Price | Notes |
|---|---|---|---|
| General SDR | [RTL-SDR Blog V4L (Lite)](https://www.rtl-sdr.com/buy-rtl-sdr-dvb-t-dongles/) | USD 37.95 | the **V4 is end-of-life** (its R828D tuner ran out). The V4L has an R828S tuner, a diplexed (not triplexed) input and no notch filter; 1 ppm TCXO, 4.5 V bias tee. A limited run ([announcement](https://www.rtl-sdr.com/rtl-sdr-blog-v4l-lite-now-available-for-purchase/)) |
| Wideband LNA | [RTL-SDR Blog Wideband LNA V2](https://www.rtl-sdr.com/buy-rtl-sdr-dvb-t-dongles/) | USD 19.95 | bias-tee powered |
| Alternative SDR | [Nooelec NESDR SMArt v5](https://www.nooelec.com/store/sdr/nesdr-smart-sdr.html) | USD 44.95 | 0.5 ppm TCXO |
| 1090 MHz dongle (filtered LNA) | [FlightAware Pro Stick Plus](https://flightaware.store/products/pro-stick-plus) | USD 45.99 | **sold out** on the page; its 1090 MHz filter (1075–1105 MHz) means it **can't receive 978** |
| 978 MHz: dongle | [FlightAware Pro Stick (unfiltered)](https://flightaware.store/products/pro-stick) | USD 36.99 | **sold out** on the page; LNA, no filter: for 978 with an external filter |
| 978 MHz: filtered LNA | [GPIO Labs 978 MHz UAT filtered LNA (Tindie)](https://www.tindie.com/products/gpio/978-mhz-ads-b-uat-filtered-lna/) | USD 75.00 | few left; SMA female; USB or bias-tee power |
| 1090 MHz antenna | [FlightAware 1090 MHz antenna, 66 cm](https://flightaware.store/products/antenna-1090mhz) | USD 49.99 | **sold out** on the page; N female; bracket for 2.5–4 cm poles |
| Powered USB hub | [Raspberry Pi USB 3.0 Hub (SparkFun WIG-26390)](https://www.sparkfun.com/raspberry-pi-usb-3-0-hub.html) | USD 18.60 | in stock; give it its own 5 V 3 A USB-C supply for several dongles and LNAs ([maker's page](https://www.raspberrypi.com/products/usb-3-hub/)) |

At most 3 dongles on a Pi 4 (`scripts/dongle-roles.sh`). An SDR node keeps the load off the timing Pi ([`../deploy/sdr-node.md`](../deploy/sdr-node.md)).

Not checked (HTTP 429): FlightAware's dual 978/1090 band-pass filter.

## VLF (10–60 kHz)

| Item | Example | Price | Notes |
|---|---|---|---|
| Loop or dipole amplifier kit | [LZ1AQ AAA-1C](https://active-antenna.eu/amplifier-kit/) | EUR 112.00 excl. VAT | loop, crossed-loop and dipole modes; usable from **20 kHz**, so not below that |
| Mini-whip (PA0RDT-style) | [Portable Class A MiniWhip (Motorobit)](https://www.motorobit.com/portable-class-a-miniwhip-vlf-lf-hf-active-antenna-module) | TRY 545.70 + VAT | a small retailer; 10 kHz–30 MHz on the page; 12–15 V; BNC; stock unclear |
| USB sound card, ≥ 96 kHz | [Behringer U-Phoria UMC202HD (Markertek)](https://www.markertek.com/product/beh-umc202hd/behringer-u-phoria-umc202hd-audio-interface-2x2-24-bit-192-khz-usb-audio-interface-with-midas-mic-preamps) | USD 86.90 | up to 192 kHz, 2 inputs; 2+ weeks lead time. 96 kHz sampling reaches 48 kHz; **192 kHz** is needed to cover 60 kHz (WWVB) |

No major distributor listed a 10 kHz-capable active whip that could be opened that day. Most mini-whips are copies of the free PA0RDT design. Not checked: the JasonKits mini-whip (Tindie, HTTP 403), a generic clone (Fruugo, HTTP 403), a 60 kHz time-code receiver module (HTTP 404; a demodulator, not an SDR path).

## All-sky camera

| Item | Example | Price | Notes |
|---|---|---|---|
| Pi camera | [Raspberry Pi High Quality Camera (maker's page)](https://www.raspberrypi.com/products/raspberry-pi-high-quality-camera/) | no price shown | IMX477R; C/CS and M12 versions; in production until at least January 2030 |
| Pi camera, C/CS | [Raspberry Pi HQ Camera (Adafruit 4561)](https://www.adafruit.com/product/4561) | USD 55.00 | **out of stock** on the page |
| Pi camera, M12 | [Raspberry Pi HQ Camera M12 (Adafruit 5661)](https://www.adafruit.com/product/5661) | USD 52.50 | **out of stock** on the page |
| Pi camera, M12 | [Raspberry Pi HQ Camera M12 (SparkFun SEN-21333)](https://www.sparkfun.com/products/21333) | USD 63.75 | **out of stock** on the page |
| Fisheye lens | [Arducam LN031 1.56 mm M12 fisheye with HQ adapter (Botland)](https://botland.store/raspberry-pi-camera-lenses/17066-fisheye-lens-m12-156mm-with-adapter-for-raspberry-pi-camera-arducam-ln031-5904422378349.html) | EUR 21.50 | in stock; 180° on the HQ camera; F2; IR-cut filter |
| Dome | [Entaniya O-ring acrylic dome cover, waterproof](https://e-products.entaniya.co.jp/en/list/product-list/o-ring-acrylic-dome-cover-waterproof/) | no price shown | 60 mm or 45.5 mm; matching cases |

A dew heater belongs with the dome (the reference node lists one); not priced here. Not checked: the ZWO ASI662MC (HTTP 403 and 429; retailers list it as the successor to the discontinued ASI224MC), the SBIG all-sky dome (HTTP 403), Arducam's own pages (HTTP 403).

## Mast and mounts

| Item | Example | Price | Notes |
|---|---|---|---|
| Mast section | [ROHN 5 ft × 1.25" OD, 16 ga, galvanized, swaged (3 Star)](https://3starinc.com/rohn-hdg-swaged-antenna-mast-5-foot-by-125-od-16-awg.html) | USD 24.85 | 0 listed, "usually ships in 24 hrs" |
| J-mount | [ROHN 1LG 1.25" J-pipe roof/wall mount (3 Star)](https://www.3starinc.com/rohn-1lg-universal-j-pipe-antenna-mast-roof-and-wall-mount) | USD 52.00 | the page also says "Call for Pricing" |
| Wall bracket | [ROHN WM24S 24" Y bracket (3 Star)](https://www.3starinc.com/rohn_24_inch_single_mount_antenna_mast_bracket_r-wm24s.html) | USD 48.00 | 1.25–2.75" OD; 24" standoff |
| Chimney mount | [Easy Up EZ 29-36S with straps (3 Star)](https://www.3starinc.com/tv_antenna_chimney_mount_y_bracket_ez29-36s.html) | USD 35.90 | 1.00–1.50" OD mast |
| Mast clamp | [3 Star CPP-LD crossover clamp](https://www.3starinc.com/light-duty-small-crossover-pole-to-pole-clamp.html) | USD 11.00 | 1.25–1.75" mast to 1.5–2" pipe |
| Antenna thread mount | [GNSS magnetic mount, 5/8"-11 (SparkFun PRT-21257)](https://www.sparkfun.com/gnss-magnetic-antenna-mount-5-8-11-tpi.html) | USD 40.50 | in stock; for survey antennas, on the bench or temporarily |

Ground the mast (above). A GNSS antenna wants open sky, away from walls and metal ([`../hardware/HARDWARE-REFERENCE-NODE.md`](../hardware/HARDWARE-REFERENCE-NODE.md) → Siting notes). Not checked: Channel Master CM-3099 (the page loaded empty).
