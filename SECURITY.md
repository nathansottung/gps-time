# Security policy

GPS Time Pi is intended to be a local-network timing appliance. Timing service availability and integrity take priority over dashboard convenience.

## Supported security model

- NTP serving should be restricted to explicitly allowed networks.
- The normal status interface should be read-only by default.
- Administrative actions must not rely solely on obscurity or LAN placement.
- Extensions and environmental collectors must not receive implicit permission to set system time or rewrite chrony configuration.
- Private location settings must be applied consistently to pages, APIs, exports, and diagnostic bundles.

## Reporting a vulnerability

Please avoid publishing an exploit against an actively deployed timing appliance before the maintainer has had a reasonable opportunity to investigate and fix it. Use a private GitHub security advisory when the repository enables that feature.

## Current development note

The source review in `docs/review/source-review-2026-09-07.md` identified management-interface and privilege-boundary work that should be completed before treating the current dashboard as safe for exposure outside a trusted LAN.
