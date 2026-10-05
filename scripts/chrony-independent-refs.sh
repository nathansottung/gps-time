#!/bin/bash
# Adds, or removes, NTP servers that chrony only measures and never uses to
# set the clock (`noselect`): independent references for the station to be
# compared with (docs/architecture/independent-references.md).
#
# Off unless asked for. Run by install.sh, which restarts chrony afterwards:
#   GTP_INDEPENDENT_REFS=1                 the default set below (NIST, USNO)
#   GTP_INDEPENDENT_REFS="host1 host2"     your own servers
#   GTP_INDEPENDENT_REFS=0                 remove the file this script wrote
#   (unset)                                change nothing
#
# It writes one file of its own in chrony's sources directory and touches no
# other chrony configuration. Polling is slow (256 s to 1024 s per server).
# Usage: chrony-independent-refs.sh [/etc/chrony/sources.d]
DIR="${1:-/etc/chrony/sources.d}"
FILE="$DIR/gps-time-independent.sources"
DEFAULT_SERVERS="time.nist.gov tick.usno.navy.mil tock.usno.navy.mil"
WANT="${GTP_INDEPENDENT_REFS-}"

if [ -z "$WANT" ]; then
  if [ -f "$FILE" ]; then
    echo "Independent references: $FILE is kept as it is (GTP_INDEPENDENT_REFS is not set)."
  else
    echo "Independent references: none added. To add them: sudo GTP_INDEPENDENT_REFS=1 bash install.sh"
  fi
  exit 0
fi
case "$WANT" in
  0|off|no|false)
    if [ -f "$FILE" ]; then
      rm -f "$FILE" && echo "Independent references: removed $FILE."
    else
      echo "Independent references: nothing to remove."
    fi
    exit 0 ;;
  1|on|yes|true) SERVERS="$DEFAULT_SERVERS" ;;
  *) SERVERS="$WANT" ;;
esac
if [ ! -d "$DIR" ]; then
  echo "Independent references: $DIR does not exist (chrony.conf needs 'sourcedir $DIR'); nothing changed." >&2
  exit 1
fi
lines=""
for host in $SERVERS; do
  # Host names and addresses only: nothing else may reach chrony's configuration.
  if ! [[ "$host" =~ ^[A-Za-z0-9]([A-Za-z0-9.:-]{0,252}[A-Za-z0-9])?$ ]]; then
    echo "Independent references: '$host' is not a host name or address; nothing changed." >&2
    exit 1
  fi
  lines="${lines}server $host noselect minpoll 8 maxpoll 10"$'\n'
done
if [ -z "$lines" ]; then
  echo "Independent references: no servers given; nothing changed." >&2
  exit 1
fi
{
  echo "# Written by gps-time-pi install.sh (scripts/chrony-independent-refs.sh)."
  echo "# noselect: chrony measures these servers and never uses them to set the clock."
  printf '%s' "$lines"
} > "$FILE.tmp" && mv -f "$FILE.tmp" "$FILE" || { rm -f "$FILE.tmp"; exit 1; }
chmod 0644 "$FILE"
echo "Independent references: wrote $FILE:"
printf '%s' "$lines" | sed 's/^/  /'
echo "chrony will poll these servers over the Internet. To remove them: sudo GTP_INDEPENDENT_REFS=0 bash install.sh"
