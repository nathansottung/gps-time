"""Dashboard layout configuration.

The dashboard is data-driven: pages and widgets are declared in JSON so the
same UI can run in Windows demo mode and on a Raspberry Pi.  Runtime writes
are intentionally gated by the server; this module only loads, validates and
persists layout data.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_DEFAULT = _HERE / "data" / "dashboard.default.json"

DEFAULT_LAYOUT = {
    "schema_version": 1,
    "title": "GPS Time",
    "pages": [
        {
            "id": "overview",
            "title": "Overview",
            "widgets": [
                {"id": "time", "visible": True, "size": "wide"},
                {"id": "timing_quality", "visible": True, "size": "normal"},
                {"id": "sun", "visible": True, "size": "normal"},
                {"id": "gnss", "visible": True, "size": "normal"},
                {"id": "network", "visible": True, "size": "normal"},
            ],
        },
        {
            "id": "sky",
            "title": "Sky & Site",
            "widgets": [
                {"id": "sun", "visible": True, "size": "normal"},
                {"id": "gnss", "visible": True, "size": "normal"},
                {"id": "satellites", "visible": True, "size": "wide"},
                {"id": "transits", "visible": True, "size": "normal"},
            ],
        },
        {
            "id": "radio",
            "title": "RF Observatory",
            "widgets": [
                {"id": "sdr", "visible": True, "size": "wide"},
                {"id": "adsb", "visible": True, "size": "normal"},
                {"id": "distributed", "visible": True, "size": "normal"},
            ],
        },
        {
            "id": "network",
            "title": "Network",
            "widgets": [
                {"id": "network", "visible": True, "size": "normal"},
                {"id": "ntp_clients", "visible": True, "size": "wide"},
                {"id": "sources", "visible": True, "size": "wide"},
            ],
        },
    ],
}

KNOWN_WIDGETS = {
    "time", "timing_quality", "sun", "gnss", "network", "satellites",
    "sources", "ntp_clients", "transits", "sdr", "adsb", "distributed",
}


def path() -> Path:
    configured = os.environ.get("GTP_DASHBOARD_CONFIG")
    if configured:
        return Path(configured)
    cfg_path = os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json")
    return Path(cfg_path).resolve().parent / "dashboard.json"


def default_layout() -> dict:
    try:
        with _REPO_DEFAULT.open("r", encoding="utf-8") as f:
            return validate(json.load(f))
    except Exception:
        return copy.deepcopy(DEFAULT_LAYOUT)


def validate(data: object) -> dict:
    """Return a normalized dashboard document or raise ValueError."""
    if not isinstance(data, dict):
        raise ValueError("dashboard configuration must be a JSON object")
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("dashboard must contain at least one page")
    if len(pages) > 20:
        raise ValueError("dashboard supports at most 20 pages")

    seen_pages: set[str] = set()
    out_pages = []
    for raw_page in pages:
        if not isinstance(raw_page, dict):
            raise ValueError("each page must be an object")
        page_id = str(raw_page.get("id", "")).strip()
        title = str(raw_page.get("title", "")).strip()
        if not page_id or not page_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"invalid page id: {page_id!r}")
        if page_id in seen_pages:
            raise ValueError(f"duplicate page id: {page_id}")
        if not title:
            raise ValueError(f"page {page_id} requires a title")
        seen_pages.add(page_id)

        widgets = raw_page.get("widgets", [])
        if not isinstance(widgets, list) or len(widgets) > 50:
            raise ValueError(f"page {page_id} has invalid widget list")
        normalized_widgets = []
        for raw_widget in widgets:
            if not isinstance(raw_widget, dict):
                raise ValueError("widget entries must be objects")
            wid = str(raw_widget.get("id", "")).strip()
            if wid not in KNOWN_WIDGETS:
                raise ValueError(f"unknown widget: {wid}")
            normalized_widgets.append({
                "id": wid,
                "visible": bool(raw_widget.get("visible", True)),
                "size": "wide" if raw_widget.get("size") == "wide" else "normal",
            })
        out_pages.append({"id": page_id, "title": title, "widgets": normalized_widgets})

    return {
        "schema_version": 1,
        "title": str(data.get("title") or "GPS Time")[:80],
        "pages": out_pages,
    }


def load() -> dict:
    p = path()
    try:
        with p.open("r", encoding="utf-8") as f:
            return validate(json.load(f))
    except FileNotFoundError:
        return default_layout()
    except Exception:
        # Never make a malformed optional layout stop the timing dashboard.
        return default_layout()


def save(data: object) -> dict:
    cfg = validate(data)
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dashboard-", suffix=".json", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
            f.write("\n")
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return cfg
