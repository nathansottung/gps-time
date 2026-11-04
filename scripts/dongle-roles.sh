# Dongle roles by serial, and the owner's limit of 3 RTL-SDRs on a Pi 4 (sourced by sdr-stack.sh
# and websdr.sh; docs/deploy/sdr-stack.md -> "Roles and the limit").
#
# Roles: PPS markers, 1090 MHz, 978 MHz (/etc/default/gps-time-sdr) and the web SDR
# (/etc/default/gps-time-websdr). Each role names one dongle by its USB serial. The web SDR may
# share the 1090 MHz dongle (readsb stops while it runs), so roles are counted by distinct serial.
#
# The limit: on a Raspberry Pi 4 (and Pi 400, Compute Module 4) at most 3 distinct serials
# (owner, 2026-11-04). Its four USB ports share one USB 2.0 bus, and the dongles share its power
# and CPU with the timing core. Other models have no limit here. The model is read from the
# device tree (under ROOT in tests); an unreadable model means no limit and says so.

DONGLE_MAX_PI4=3

dongle_model() {   # dongle_model <root> -> the model string, or nothing
  tr -d '\0' < "$1/proc/device-tree/model" 2>/dev/null
}

dongle_limit() {   # dongle_limit <root> -> the limit for this model, or nothing for none
  case "$(dongle_model "$1")" in
    "Raspberry Pi 4"*|"Raspberry Pi 400"*|"Raspberry Pi Compute Module 4"*) echo "$DONGLE_MAX_PI4" ;;
  esac
}

dongle_saved() {   # dongle_saved <file> <NAME> -> the saved value
  [ -f "$1" ] && sed -n "s/^$2=\\([A-Za-z0-9_-]*\\)\$/\\1/p" "$1" | tail -n 1
}

# dongle_check <root> <serial>... : the serials of every role after this change (empty ones
# ignored). Prints the count; returns 1 with a message when it's over this model's limit.
dongle_check() {
  local root="$1"; shift
  local distinct n limit
  distinct="$(printf '%s\n' "$@" | sed '/^$/d' | sort -u)"
  n="$(printf '%s\n' "$distinct" | sed '/^$/d' | wc -l | tr -d ' ')"
  limit="$(dongle_limit "$root")"
  if [ -n "$limit" ] && [ "$n" -gt "$limit" ]; then
    echo "Dongle roles: $n RTL-SDRs by serial ($(printf '%s ' $distinct)), but at most $limit on a $(dongle_model "$root") (owner's limit). Give a role no serial (=none), or share the 1090 MHz dongle with the web SDR." >&2
    return 1
  fi
  if [ -n "$limit" ]; then
    echo "Dongle roles: $n of at most $limit RTL-SDRs on this $(dongle_model "$root")."
  elif [ -n "$(dongle_model "$root")" ]; then
    echo "Dongle roles: $n RTL-SDR(s) by serial; no limit for a $(dongle_model "$root")."
  else
    echo "Dongle roles: $n RTL-SDR(s) by serial; the board model can't be read, so no limit is applied."
  fi
  return 0
}
