# Polium

**Polars → Folium, made simple.**

Create beautiful, interactive Leaflet maps from Polars DataFrames with clean dots, tracks, time animations, H3 hexes, and **fully offline** asset support.

## Installation

### From PyPI (once published)

```bash
pip install polium
```

For full features including H3 hexes and geodesic calculations:

```bash
pip install polium[full]
```

Or install specific optional dependencies:

```bash
pip install polium[h3]      # For H3 hex support
pip install polium[geo]     # For geodesic rings (pyproj) and geometry (shapely)
```

### From source

```bash
git clone https://github.com/HarryRudolph/polium.git
cd polium
pip install -e .
```

## Quick Start

```python
import polars as pl
from polium import PoliumMap

# Your data
df = pl.DataFrame({
    "lat": [51.5074, 51.52, 51.49],
    "lon": [-0.1278, -0.10, -0.15],
    "name": ["Westminster", "Regent's Park", "Battersea"],
})

# Create map
TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
m = PoliumMap(TILES, center=(51.5074, -0.1278), zoom_start=12)

# Add data
m.add_dots(df, popup=["name"], tooltip="name", name="Places")
m.add_layer_control()

# Save
m.save("map.html")
```

## Fully Offline Maps (No CDNs)

### 1. Fetch local JS/CSS assets once

```bash
python examples/fetch_map_assets.py --dir ./assets --with-time --with-antpath
```

### 2. Create completely offline maps

```python
# Inline embedding (single HTML file, no external dependencies)
m.save("map_offline.html", offline_assets_dir="./assets", embed_assets=True, strict_offline=True)

# Or use local file references
m.save("map_offline.html", offline_assets_dir="./assets", embed_assets=False, strict_offline=True)
```

The `embed_assets=True` option (default) embeds all JS/CSS directly into the HTML, creating a single standalone file that works completely offline.

## Features

- **Simple API**: Clean, chainable methods for adding map elements
- **Offline Support**: Fully offline maps with embedded or local assets
- **AIS-Friendly**: Optimized for vessel tracking and marine visualization
- **Time Animations**: Built-in support for time-series data
- **H3 Hexes**: Native H3 hexagon support for spatial aggregation
- **Geodesic Rings**: Accurate range rings using geodesic calculations
- **Polars Native**: Designed specifically for Polars DataFrames

## API Overview

### Core Methods

- `PoliumMap(tiles_url_template, center=None, zoom_start=10)` - Create a new map
- `add_dots(...)` - Fast vector dots (CircleMarker) with optional value coloring
- `add_points(...)` - Classic pin markers with optional clustering
- `add_track(...)` - Polyline tracks with optional ant-path animation
- `add_range_ring(...)` - Geodesic range rings (requires pyproj)
- `add_time_points(...)` - Time-animated points (requires TimeDimension plugin)
- `add_choropleth(...)` - Colored polygons from geometry column
- `add_h3_hexes(...)` - H3 hexagon visualization (requires h3)
- `add_layer_control(collapsed=False)` - Add layer toggle control
- `save(path, offline_assets_dir=None, embed_assets=True, strict_offline=False)` - Save to HTML
- `folium_map` - Access underlying folium.Map for advanced usage

## Examples

See the `examples/` directory for more:

- `examples/demo.py` - Basic points, time animation, and H3 hexes
- `examples/demo_ais_dark_zone.py` - AIS vessel tracking with range rings
- `examples/fetch_map_assets.py` - Download assets for offline use

## Notes & Gotchas

- `add_time_points` uses the Leaflet TimeDimension plugin and **does not appear in LayerControl** (plugin limitation)
- H3 on Python 3.13+: prefer `pip install "h3>=4,<5"`
- For offline maps without time/ant-path features, those specific assets aren't needed
- The library prioritizes simplicity and AIS/maritime use cases while remaining general-purpose

## Requirements

**Core:**
- Python ≥ 3.8
- polars ≥ 1.0.0
- folium ≥ 0.20.0
- branca ≥ 0.8.0

**Optional:**
- h3 ≥ 4.0.0 (for H3 hexes)
- shapely ≥ 2.0.0 (for geometry support)
- pyproj ≥ 3.0.0 (for geodesic calculations)

## License

MIT
