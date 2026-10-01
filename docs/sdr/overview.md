# SDR / RF observatory

SDR is a first-class optional instrument family. It is not part of the timing core.

## Useful local capabilities

- spectrum and RFI monitoring
- WWV/CHU Doppler/frequency observations
- WSPR/FST4W reception
- ADS-B 1090 and UAT 978
- radiosonde reception
- meteor scatter
- satellite reception with predicted Doppler
- receiver oscillator characterization

## Multiple devices

Inventory devices by serial/model and assign roles. A module requests a capability; it should not hard-code `/dev/rtl0`.

## Maturity rule

A cheap USB SDR can be scientifically useful without precision event timing. Do not inherit host-clock accuracy into RF sample timestamps unless the sample epoch has been characterized.
