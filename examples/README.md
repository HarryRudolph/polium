# Polium Examples

This directory contains example scripts demonstrating various features of Polium.

## Running Examples

After installing Polium:

```bash
cd examples
python demo.py
python demo_ais_dark_zone.py
```

## Offline Asset Setup

To run examples with fully offline maps:

```bash
# Download assets once
python fetch_map_assets.py --dir ./assets --with-time --with-antpath

# Then run examples - they'll use offline assets automatically
python demo_ais_dark_zone.py
```

## Examples

- **demo.py** - Basic usage with points, time animation, and optional H3 hexes
- **demo_ais_dark_zone.py** - AIS vessel tracking with tracks, dots, and range rings
- **fetch_map_assets.py** - Utility to download Leaflet/folium assets for offline use
