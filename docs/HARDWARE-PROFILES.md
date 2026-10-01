# GPS / GNSS hardware profiles

GPS Time Pi deliberately separates **hardware wiring** from the common gpsd/chrony application layer.

A profile records at minimum:

- serial device / transport;
- PPS availability and GPIO when applicable;
- optional RTC overlay;
- receiver-specific installation notes;
- capability class: PPS timing or NMEA-only.

Always review generated files before applying them. Raspberry Pi UART device names can vary by Pi model and OS configuration.

## Supported/generated profiles

### `uputronics`

Project's original hardware: Uputronics GPS/RTC expansion board with u-blox MAX-M8Q.

Project deployment profile:

- UART: `/dev/ttyAMA0`
- PPS: GPIO 18
- RTC overlay: `rv3028`
- Capability: PPS timing

Generate:

```bash
python3 tools/generate_config.py --profile uputronics
```

This is the configuration used by the project's original Pi. Confirm the exact board revision and vendor wiring before applying it to a different Uputronics product/revision.

### `adafruit-ultimate`

Adafruit Ultimate GPS HAT (MTK3339 family).

Vendor documentation specifies:

- UART on the Pi serial interface;
- PPS connected by default to GPIO 4;
- external active antenna support for indoor/obstructed installations;
- no RTC device-tree overlay is required for this project's profile.

Generate:

```bash
python3 tools/generate_config.py --profile adafruit-ultimate
```

Then verify `/dev/pps0` with `ppstest` before configuring chrony as a PPS source.

### `waveshare-l76x`

Waveshare L76X GPS HAT.

Important: vendor documentation does **not** describe PPS as already routed to a Raspberry Pi GPIO. Their PPS FAQ instructs the user to solder the module PPS point to Raspberry Pi GPIO 4 when PPS is desired. The profile therefore assumes that modification has been deliberately made.

- UART: Pi hardware serial interface
- PPS: GPIO 4 **only after the documented PPS connection is made**
- Capability: PPS timing after modification; otherwise NMEA-only

Generate PPS version:

```bash
python3 tools/generate_config.py --profile waveshare-l76x
```

Without the PPS modification, use a custom NMEA-only configuration instead of claiming precision timing.

### `sparkfun-gnss-flex`

SparkFun GNSS Flex pHAT wiring profile.

The pHAT documentation maps:

- primary GNSS UART to Raspberry Pi GPIO14/15;
- PPS1 to GPIO22;
- PPS2 to GPIO23.

The actual GNSS receiver module mounted in the Flex system determines timing/position capabilities. This profile uses PPS1 / GPIO22 and assumes a compatible module is installed.

Generate:

```bash
python3 tools/generate_config.py --profile sparkfun-gnss-flex
```

### `usb-gps`

Generic USB GPS without a kernel PPS device.

This is intentionally classified as **NMEA-only**. It can provide useful coarse network time but must not be presented as equivalent to a GPIO/kernel-PPS installation.

```bash
python3 tools/generate_config.py --profile usb-gps
```

If a USB receiver exposes a real Linux PPS device, create a dedicated profile for that receiver instead of using this generic one.

## Custom hardware

For any UART GNSS receiver with a PPS wire:

```bash
python3 tools/generate_config.py \
  --uart /dev/serial0 \
  --pps-gpio 18 \
  --allow 192.168.1.0/24
```

For UART/NMEA only:

```bash
python3 tools/generate_config.py --uart /dev/serial0 --no-pps
```

## Common install sequence

After generating a profile:

1. Read `generated/README.txt`.
2. Review all three generated files.
3. Apply the `config.txt` snippet and reboot.
4. Confirm the serial device exists.
5. Confirm GNSS data with `cgps` / `gpsmon`.
6. For PPS profiles, confirm pulses with `ppstest /dev/pps0`.
7. Apply the gpsd configuration and verify a valid time/fix.
8. Apply the chrony configuration.
9. Verify `chronyc sources -v` and `chronyc tracking`.
10. Only then enable LAN serving/`allow` for the intended subnet.

## Adding profiles

New hardware support should arrive as a small profile plus documentation/evidence:

- vendor/model and board revision;
- vendor wiring/manual link;
- serial device/baud assumptions;
- PPS pin and whether soldering/jumpers are required;
- RTC information if present;
- sample `ppstest`, `gpsmon`, and `chronyc sources -v` output;
- tested Raspberry Pi model and Raspberry Pi OS release.

Do not merge a profile solely because a board outputs NMEA. Precision-timing support requires a verified PPS path or another explicitly supported hardware timestamp source.
