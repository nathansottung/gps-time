# The aircraft decoders' RTL-SDR support (sourced by sdr-stack.sh; docs/deploy/sdr-stack.md -> Check it).
#
# rc.8 on the owner's Pi: Debian 13's readsb package is built without RTL-SDR support, so
# "--device-type rtlsdr" failed with "Unknown device type:rtlsdr" and readsb restarted for ever.
# The stack now builds readsb itself (make RTLSDR=yes) and checks the result before enabling it.

# decoder_readsb_rtlsdr <readsb> : true when this readsb accepts --device-type rtlsdr.
# Never runs the decoder: an unknown option after --device-type makes readsb's argument parser
# stop with an error either way. (readsb --help runs readsb unless --help is the first argument.)
# Without RTL-SDR support it says "Unknown device type:rtlsdr" first.
decoder_readsb_rtlsdr() {
  local out
  [ -x "$1" ] || return 1
  out="$(timeout 10 "$1" --device-type rtlsdr --gtp-check-only 2>&1)"
  [ -n "$out" ] || return 1
  case "$out" in *"Unknown device type"*) return 1 ;; esac
  return 0
}

# decoder_soapy_rtlsdr <root> : true when SoapySDR's RTL-SDR driver (librtlsdrSupport.so, from the
# soapysdr-module-rtlsdr package) is installed. dump978-fa opens its dongle with
# "--sdr driver=rtlsdr,serial=..." through SoapySDR, so without the driver it can't find any dongle.
# A file check only: SoapySDRUtil --probe would open the dongle.
decoder_soapy_rtlsdr() {
  local f
  for f in "$1"/usr/lib/*/SoapySDR/modules*/librtlsdrSupport.so "$1"/usr/lib/SoapySDR/modules*/librtlsdrSupport.so \
           "$1"/usr/local/lib/SoapySDR/modules*/librtlsdrSupport.so; do
    [ -f "$f" ] && return 0
  done
  return 1
}
