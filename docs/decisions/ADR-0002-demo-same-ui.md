# ADR-0002: Windows demo uses the production dashboard renderer

**Status:** Implemented in 1.4.0-dev scaffold

Do not maintain a separate fake HTML mockup. Demo mode swaps hardware/chrony providers for sample data while using the same dashboard/layout APIs, CSS and JavaScript as the Pi.
