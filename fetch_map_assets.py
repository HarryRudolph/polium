#!/usr/bin/env python3
"""
Download all JS/CSS assets needed for fully-offline Folium maps.

Default versions match the CDN URLs Folium emitted in your error log:
- Leaflet 1.9.3
- jQuery 3.7.1
- Bootstrap 5.2.2 (+ Bootstrap 3 glyphicons CSS for AwesomeMarkers)
- Font Awesome 6.2.0
- Leaflet.AwesomeMarkers 2.0.2 (+ rotate CSS from folium templates)

Optional:
- TimeDimension 1.1.0 + moment 2.29.4 + iso8601-js-period 0.2.1
- AntPath 1.3.0
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

CORE_ASSETS = {
    # Leaflet
    "leaflet.js": "https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js",
    "leaflet.css": "https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css",
    # jQuery + Bootstrap
    "jquery-3.7.1.min.js": "https://code.jquery.com/jquery-3.7.1.min.js",
    "bootstrap.bundle.min.js": "https://cdn.jsdelivr.net/npm/bootstrap@5.2.2/dist/js/bootstrap.bundle.min.js",
    "bootstrap.min.css": "https://cdn.jsdelivr.net/npm/bootstrap@5.2.2/dist/css/bootstrap.min.css",
    # Font Awesome + Bootstrap 3 glyphicons (for AwesomeMarkers template)
    "all.min.css": "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.2.0/css/all.min.css",
    "bootstrap-glyphicons.css": "https://netdna.bootstrapcdn.com/bootstrap/3.0.0/css/bootstrap-glyphicons.css",
    # Leaflet.AwesomeMarkers
    "leaflet.awesome-markers.js": "https://cdnjs.cloudflare.com/ajax/libs/Leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.js",
    "leaflet.awesome-markers.css": "https://cdnjs.cloudflare.com/ajax/libs/Leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.css",
    "leaflet.awesome.rotate.min.css": "https://cdn.jsdelivr.net/gh/python-visualization/folium/folium/templates/leaflet.awesome.rotate.min.css",
}

TIME_ASSETS = {
    # Leaflet.TimeDimension + deps
    "leaflet.timedimension.min.js": "https://cdn.jsdelivr.net/npm/leaflet-timedimension@1.1.0/dist/leaflet.timedimension.min.js",
    "leaflet.timedimension.control.css": "https://cdn.jsdelivr.net/npm/leaflet-timedimension@1.1.0/dist/leaflet.timedimension.control.css",
    "moment.min.js": "https://cdn.jsdelivr.net/npm/moment@2.29.4/min/moment.min.js",
    "iso8601.min.js": "https://cdn.jsdelivr.net/npm/iso8601-js-period@0.2.1/iso8601.min.js",
}

ANTPATH_ASSETS = {
    "leaflet-ant-path.min.js": "https://cdn.jsdelivr.net/npm/leaflet-ant-path@1.3.0/dist/leaflet-ant-path.min.js",
}


def download(url: str, dest: Path, force: bool) -> tuple[bool, str]:
    """Return (downloaded, message)."""
    if dest.exists() and not force:
        return False, f"skip (exists)  {dest.name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            data = r.read()
            f.write(data)
        return True, f"ok   ({len(data):,} B)  {dest.name}"
    except HTTPError as e:
        return False, f"HTTP {e.code}  {url}"
    except URLError as e:
        return False, f"URL error {e.reason}  {url}"


def main() -> int:
    p = argparse.ArgumentParser(
        description="Download local JS/CSS assets for offline Folium maps.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              python fetch_map_assets.py --dir ./assets
              python fetch_map_assets.py --dir /Users/Harry/dev/polium/assets --with-time --with-antpath --force
            """
        ),
    )
    p.add_argument("--dir", default="assets", help="Destination directory (default: ./assets)")
    p.add_argument("--with-time", action="store_true", help="Also download TimeDimension + deps")
    p.add_argument("--with-antpath", action="store_true", help="Also download Leaflet AntPath")
    p.add_argument("--force", action="store_true", help="Re-download even if file exists")
    args = p.parse_args()

    dest_dir = Path(args.dir).expanduser().resolve()
    plan = dict(CORE_ASSETS)
    if args.with_time:
        plan.update(TIME_ASSETS)
    if args.with_antpath:
        plan.update(ANTPATH_ASSETS)

    print(f"Downloading {len(plan)} files to {dest_dir} …\n")
    failures = []
    for name, url in plan.items():
        downloaded, msg = download(url, dest_dir / name, args.force)
        print(("↓ " if downloaded else "• ") + msg)
        if msg.startswith("HTTP") or msg.startswith("URL error"):
            failures.append((name, url))

    print("\nDone.")
    if failures:
        print("Some files failed:")
        for name, url in failures:
            print(f" - {name}: {url}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
