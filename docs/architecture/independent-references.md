# Independent references

Status: implemented (`gps_time_pi/references.py`, `/api/references`, Timing → References in `/app/`). Requirement: `specs/SPEC-TIMING-METROLOGY.md` §4. Not yet run on a Pi.

## What it does

chrony measures every NTP server it polls. A server that chrony is **not** using to set the clock is an independent check on the station. This feature reads chrony's measurements of those servers, keeps a short history of each, and reports whether the station agrees with them.

The station software never contacts a server itself and never writes chrony's configuration at run time. It reads `chronyc -n sources`, which the timing chain already polls every 5 s.

## Which servers count

| chrony's view of a network source | Role | Counted |
|---|---|---|
| selected (`*`) or combined (`+`) | steering the clock | no; listed as "not counted" |
| one of the station's own addresses | the station itself | no; never a reference |
| anything else (configured `noselect`, or just not chosen) | independent | yes |

The role is taken from chrony's current state, not from the configuration. So a pool server that chrony isn't using right now counts, and it stops counting the moment chrony selects it (for example after a PPS loss). A server configured `noselect` can never be selected, so it stays independent in every situation. That is why the optional installer step adds `noselect` servers.

A reference is **usable** when chrony has reached it (reach ≠ 0) and its last measurement is recent (within four poll intervals, at least 120 s). An unusable reference shows no offset: a stale or zero value is never displayed.

## The comparison

For each usable reference, with chrony's offset and error bound for that server:

| Condition | Result |
|---|---|
| \|offset\| ≤ limit | agrees |
| \|offset\| > limit, but ≤ the server's error bound | inconclusive (the measurement can't decide) |
| \|offset\| > limit and > the error bound | disagrees |

The limit is 50 ms by default (`GTP_REF_DISAGREE_S`, in seconds). Public servers over the Internet are typically good to a few tens of milliseconds, so a smaller limit would flag network delay, not clocks.

Overall outcome (`verdict.code`):

| Code | Meaning |
|---|---|
| `AGREE` | at least two usable references, and no more than half disagree |
| `DISAGREE` | more than half of the usable references disagree |
| `ONE_REFERENCE` | only one usable reference: its result is given, but one server is not a majority |
| `NONE_REACHABLE` | references exist, none is answering: "no external references reachable" |
| `NONE_CONFIGURED` | chrony polls no server that isn't steering the clock |
| `UNKNOWN` | chrony's source list couldn't be read |

**A disagreement is not a diagnosis.** The text says that the station's clock differs from N of M references by more than the limit, and that this does not say which clock is wrong or why. It never names a cause. The comparison does not change the timing-chain status or the banner.

Working without the Internet is normal for this station. `NONE_REACHABLE` is a plain statement, not an error, and nothing else depends on it.

## Labels

- Each server's offset, error bound and delay: `external` (other people's servers, measured over the network by chrony).
- The outcome: `calculated`.
- Offset sign: chrony's. Positive means the station's clock is ahead of that server.

## Delay

`chronyc sources` has no delay column. The network delay per server comes from `chronyc -n ntpdata` ("Peer delay"), which chronyd answers only over its Unix socket. The existing helper service (`gps-time-pi-chrony-clients.service`, user `_chrony`, ADR-0005) now publishes that report too, as `/run/gps-time-pi/chrony-ntpdata.txt`, next to the client list. The helper still runs a fixed list of read-only reports and takes no input. Without the file, delay reads UNKNOWN and the comparison still works.

## History

RAM only, lost on a service restart: one point per new measurement, at most one a minute, 1440 points per server (24 h at one a minute; longer at slower polls), at most 16 servers.

## Adding `noselect` servers (optional)

Off by default. The installer adds them only when asked, because it changes chrony's configuration and makes chrony contact servers on the Internet:

```sh
sudo GTP_INDEPENDENT_REFS=1 bash install.sh                      # time.nist.gov, tick.usno.navy.mil, tock.usno.navy.mil
sudo GTP_INDEPENDENT_REFS="ntp1.example ntp2.example" bash install.sh
sudo GTP_INDEPENDENT_REFS=0 bash install.sh                      # remove them again
```

- It writes one file, `/etc/chrony/sources.d/gps-time-independent.sources`, with `server <host> noselect minpoll 8 maxpoll 10` per server (one poll every 4 to 17 minutes). Nothing else in chrony's configuration is touched. The installer restarts chrony afterwards, as it always has.
- Only host names and addresses are accepted, and every line is written with `noselect`.
- With the variable unset, an existing file is left as it is.
- Without this step the page still works with whatever servers chrony already polls and isn't using.

Those servers see the station's public IP address, like any NTP server the station uses.
