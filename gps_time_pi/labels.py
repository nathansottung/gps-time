"""Provenance labels for every value the station reports.

observed   — measured by station hardware or read from the running system
calculated — derived mathematically from observations
modeled    — physical/statistical model output for a present or past quantity
predicted  — forecast of a future value
inferred   — reasoned from indirect evidence (classifications, likely boundaries)
external   — obtained from a source outside the station

When a value's origin or state cannot be established, report UNKNOWN instead
of choosing a label (see web/guidelines/Guidelines.md).
"""

PROVENANCE = ("observed", "calculated", "modeled", "predicted", "inferred", "external")


def q(value, unit=None, provenance="observed", note=None):
    """A labeled value: {'value', 'unit', 'provenance'[, 'note']}."""
    if provenance not in PROVENANCE:
        raise ValueError(f"unknown provenance label: {provenance}")
    out = {"value": value, "unit": unit, "provenance": provenance}
    if note:
        out["note"] = note
    return out
