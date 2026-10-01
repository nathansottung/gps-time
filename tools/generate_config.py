#!/usr/bin/env python3
"""Generate the three system config snippets for your GPS hardware.

Interactive:  python3 tools/generate_config.py
With flags:   python3 tools/generate_config.py --profile uputronics
              python3 tools/generate_config.py --uart /dev/ttyAMA0 \
                  --pps-gpio 18 --rtc rv3028 --allow 192.168.0.0/16

Writes config.txt.snippet, gpsd.default and chrony.conf.snippet into
./generated/ — review, then apply per the comments in each file.
"""

import argparse
import os
import sys

PROFILES = {
    "uputronics": dict(uart="/dev/ttyAMA0", pps=18, rtc="rv3028",
        note="Uputronics GPS/RTC Expansion Board (u-blox MAX-M8Q)"),
    "adafruit-ultimate": dict(uart="/dev/ttyAMA0", pps=4, rtc=None,
        note="Adafruit Ultimate GPS HAT (MTK3339) — PPS on GPIO 4"),
    "waveshare-l76x": dict(uart="/dev/ttyAMA0", pps=4, rtc=None,
        note="Waveshare L76X HAT — PPS requires vendor-documented wiring to GPIO 4"),
    "sparkfun-gnss-flex": dict(uart="/dev/ttyAMA0", pps=22, rtc=None,
        note="SparkFun GNSS Flex pHAT — PPS1 on GPIO 22; receiver module determines capability"),
    "usb-gps": dict(uart="/dev/ttyACM0", pps=None, rtc=None,
        note="Generic USB GPS — NMEA only; NO PPS, so no stratum-1 "
             "precision. Expect ~10-100 ms, not microseconds."),
}


def ask(prompt, default):
    v = input(f"{prompt} [{default}]: ").strip()
    return v or default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=sorted(PROFILES))
    ap.add_argument("--uart"), ap.add_argument("--pps-gpio", type=int)
    ap.add_argument("--rtc"), ap.add_argument("--allow", default="192.168.0.0/16")
    ap.add_argument("--no-pps", action="store_true",
                    help="force NMEA-only configuration even if a GPIO PPS profile/default exists")
    ap.add_argument("--no-cpu-lock", action="store_true",
                    help="skip the fixed-CPU-clock jitter reduction")
    a = ap.parse_args()

    if a.profile:
        p = PROFILES[a.profile]
        uart, pps, rtc = p["uart"], p["pps"], p["rtc"]
        print(f"# Profile: {a.profile} — {p['note']}")
    elif a.uart or a.pps_gpio:
        uart = a.uart or "/dev/ttyAMA0"
        pps = a.pps_gpio
        rtc = a.rtc
    else:
        print("Known profiles:", ", ".join(sorted(PROFILES)), "\n")
        uart = ask("GPS serial device", "/dev/ttyAMA0")
        ppss = ask("PPS GPIO pin (blank = no PPS)", "18")
        pps = int(ppss) if ppss else None
        rtc = ask("RTC overlay name (blank = none)", "rv3028") or None

    if a.no_pps:
        pps = None

    os.makedirs("generated", exist_ok=True)

    lines = ["# Append to /boot/firmware/config.txt, then reboot"]
    if uart.startswith("/dev/ttyAMA"):
        lines += ["enable_uart=1", "dtoverlay=disable-bt"]
    if pps is not None:
        lines += [f"dtoverlay=pps-gpio,gpiopin={pps}"]
    if rtc:
        lines += ["dtparam=i2c_arm=on",
                  f"dtoverlay=i2c-rtc,{rtc},backup-switchover-mode=1"]
    if not a.no_cpu_lock:
        lines += ["# fixed CPU clock reduces PPS jitter (optional)",
                  "arm_freq=600", "arm_freq_min=600", "arm_boost=0"]
    open("generated/config.txt.snippet", "w").write("\n".join(lines) + "\n")

    open("generated/gpsd.default", "w").write(
        '# Replace /etc/default/gpsd with this, then: '
        'sudo systemctl enable --now gpsd\n'
        'START_DAEMON="true"\n'
        f'DEVICES="{uart}"\n'
        'GPSD_OPTIONS="-n"\n'
        'USBAUTO="false"\n')

    ch = ["# Append to /etc/chrony/chrony.conf, then: sudo systemctl restart chrony"]
    if pps is not None:
        ch += ["refclock SHM 0 refid NMEA offset 0.1 delay 0.2 noselect",
               "refclock PPS /dev/pps0 lock NMEA refid GPS prefer"]
    else:
        ch += ["# No PPS: NMEA is the coarse selectable refclock",
               "refclock SHM 0 refid GPS offset 0.1 delay 0.2 prefer"]
    ch += ["server time.nist.gov iburst noselect",
           "server time.cloudflare.com iburst noselect",
           "pool us.pool.ntp.org iburst maxsources 4",
           f"allow {a.allow}", "rtcsync", "log tracking",
           "logdir /var/log/chrony"]
    open("generated/chrony.conf.snippet", "w").write("\n".join(ch) + "\n")

    readme = [
        "GPS Time Pi generated hardware configuration",
        "",
        "REVIEW THESE FILES BEFORE APPLYING THEM.",
        "UART names vary by Raspberry Pi model / OS configuration.",
        "",
        f"Serial device: {uart}",
        f"PPS GPIO: {pps if pps is not None else 'none / NMEA-only'}",
        f"RTC overlay: {rtc or 'none'}",
        "",
        "Suggested validation order:",
        "1. Apply config.txt.snippet and reboot.",
        "2. Confirm the serial device and GNSS data with gpsmon/cgps.",
        "3. If PPS is configured, run: sudo ppstest /dev/pps0",
        "4. Apply gpsd.default and verify gpsd.",
        "5. Apply chrony.conf.snippet and restart chrony.",
        "6. Verify: chronyc sources -v ; chronyc tracking",
        "",
        "See docs/HARDWARE-PROFILES.md for board-specific wiring notes.",
    ]
    open("generated/README.txt", "w").write("\n".join(readme) + "\n")

    print("\nWrote generated/config.txt.snippet, generated/gpsd.default,",
          "generated/chrony.conf.snippet, generated/README.txt")
    if pps is None:
        print("\nNOTE: without PPS this will be a convenience clock, not a "
              "precision one.", file=sys.stderr)


if __name__ == "__main__":
    main()
