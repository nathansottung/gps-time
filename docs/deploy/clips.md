# Clip recording: audio and IQ, capped, never on the SD card

Short recordings from the SDR stack's rtl_tcp dongle, kept as SigMF files with the station's timing. Owner's rc.3 list and design, 2026-11-04 (#164).

## What a clip is

| Kind | Recorded as | Rate | About |
|---|---|---|---|
| IQ | the RTL-SDR's raw samples, `cu8` | 1.024, 2.048 or 2.4 MS/s | 2 MB a second at 1.024 MS/s |
| AM, NFM, wide FM | audio demodulated from 240 kS/s IQ, `ri16_le` | 48 kHz | 96 kB a second |

- **The files:** each clip is a `.sigmf-meta` and a `.sigmf-data` (`../modules/observation-format.md`). Audio clips can also be downloaded as WAV.
- **Signed** with the station key when it can be read; the clip list says when one isn't.
- **Position:** the metadata carries it at the station's privacy mode (exact, rounded to 0.1°, or none when hidden).
- **Range:** 24–1766 MHz (R820T/R860 tuners), 1–60 s, automatic gain or a fixed 0–50 dB.
- **One clip at a time.** rtl_tcp serves one client: while `sdr-pps-marker` reads it, a clip fails and says rtl_tcp is busy.

## Timing

Each clip says how its samples are timed:
- **`core:datetime`:** this Pi's clock when the first sample after a 0.25 s settle arrived.
- **`gpstime:time_source`** comes from `/api/time-quality`: `pps` on the station (its clock follows its GNSS/PPS reference), `ntp` on an SDR node (`sdr-node.md`), `free_running` when chrony can't tell.
- **`gpstime:time_offset_bound_s`:** chrony's bound on the clock (`|System time| + Root dispersion + ½ Root delay`). It holds only if the reference is right.
- **`gpstime:sample_time_uncertainty_s`:** the RTL-SDR's USB buffering, which dominates. It's one 256 KiB buffer at the byte rate, at least 50 ms: about 0.55 s for audio (240 kS/s) and 0.13 s for IQ at 1.024 MS/s. This is `modeled` from the buffer size, not measured. A clip's start is therefore known to the station's clock, give or take the USB buffer. The station's own clock is far better than that.

## Where clips go

- **By default, RAM:** `/run/gps-time-clips`, cleared at every boot, capped at 64 MB. When a new clip takes the folder past the cap, the oldest go first. A clip that couldn't fit the cap at all is refused before recording.
- **Or a drive you name:** a USB drive or NAS mount under `/mnt`, `/media` or `/srv`, with your own cap:

  ```sh
  sudo GTP_CLIPS_DIR=/mnt/usb/clips GTP_CLIPS_MAX_MB=2048 bash install.sh
  ```

  The installer and the station both refuse a folder on the SD card's file system (the same device as `/`). If the drive isn't mounted, the Radio page says so, and nothing is recorded. `GTP_CLIPS_DIR=ram` goes back to RAM. The recorder unit can write to that one folder (a drive the owner names gets a drop-in), and nowhere else.
- **Kept in** `/etc/default/gps-time-clips`. The deploy scripts pass `GTP_CLIPS_DIR` and `GTP_CLIPS_MAX_MB` too.

## How it runs

- Radio & SDR → Devices → **Clips**: kind, frequency, length (and the rate for IQ), then **Record** (admin token).
- **The web service never records.** It checks the request, writes it as `.pending.json` in the clip folder, and starts `gps-time-clip.service`. That is a one-shot unit as the web service's user, reaching `127.0.0.1` only, which records, writes, applies the cap and exits. The polkit rule allows starting that unit only.
- **The list** shows each clip's start, kind, frequency, length, timing label and files. You can download the meta, the data and (for audio) a WAV, or delete a clip (admin token).
- **Never touched:** chrony, gpsd and PPS. The recorder only reads `chronyc tracking` for the label.

## Not verified

Tested with a fake rtl_tcp that streams synthetic samples (a 1 kHz AM tone comes back at 1 kHz), on temp folders. Not run on a Pi with a real dongle. In particular:
- the demodulators' audio quality: simple filters, and no FM de-emphasis;
- the USB-buffer figure, which is modeled from the buffer size and wasn't measured.

## Privacy after the mode changes

A clip carries the position at the privacy mode in force when it was recorded. A download goes out at the current mode: after a switch to rounded or hidden, `GET /api/clips/file?ext=sigmf-meta` sends the position rounded (0.1°, 10 m) or nulled. The station's signature covered the original, so it is removed, and a `gpstime:position_note` says so. The file on the drive is unchanged; it is the owner's. Security review 2026-11-04, H1.
