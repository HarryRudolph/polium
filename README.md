# polium (single-file)

**Polars → Folium, made simple.**
Drop `polium.py` next to your script and put AIS (or any lat/lon) data on a Leaflet map with clean dots, tracks, optional time animation, H3 hexes, and **fully offline** assets.

## Fully offline (no CDNs)

1. Fetch local JS/CSS once:

```bash
python fetch_map_assets.py --dir ./assets --with-time --with-antpath
```

2. Save maps with rewrites to your local files:

```python
m.save("ais_offline.html", offline_assets_dir="./assets", strict_offline=True)
```

## Notes / gotchas

- `add_time_points` uses the Leaflet TimeDimension plugin and **does not appear in LayerControl** (plugin limitation).
- H3 on Python 3.13+: prefer `pip install "h3>=4,<5"`.
- For offline maps you don’t use time/ant-path, those assets aren’t needed.

## Minimal API (single file)

- `PoliumMap(tiles_url_template, center=None, zoom_start=10)`
- `add_dots(...)`, `add_points(...)`, `add_track(...)`, `add_range_ring(...)`
- `add_time_points(...)`, `add_choropleth(...)`, `add_h3_hexes(...)`
- `add_layer_control(collapsed=False)`
- `save(path, offline_assets_dir=None, assets_map=None, strict_offline=False)`
- `folium_map` property (access underlying `folium.Map`)
