import datetime as dt
from typing import List, Tuple

import polars as pl
import pyproj
import folium
from polium import PoliumMap

TILES = "http://127.0.0.1:8080/{z}/{x}/{y}.png"  # works even if tileserver is offline (grey bg)
TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

# --- helper: geodesic circle (range ring) as GeoJSON polygon coordinates ---
def geodesic_circle(lon: float, lat: float, radius_m: float, n: int = 256) -> List[List[float]]:
    """
    Return a closed polygon ring [[lon,lat], ...] approximating a geodesic circle on WGS84.
    """
    geod = pyproj.Geod(ellps="WGS84")
    coords: List[List[float]] = []
    for az in [i * (360.0 / n) for i in range(n)]:
        lon2, lat2, _ = geod.fwd(lon, lat, az, radius_m)
        coords.append([lon2, lat2])
    coords.append(coords[0])
    return coords

NM = 1852.0  # meters per nautical mile

# --- 1) Sample AIS track with a gap (dark zone) ---
# Times: two legs with a ~2h gap in between.
df = pl.DataFrame(
    {
        "time": [
            dt.datetime(2024, 1, 1, 12, 0, 0),
            dt.datetime(2024, 1, 1, 12, 10, 0),
            dt.datetime(2024, 1, 1, 12, 20, 0),  # last before gap
            dt.datetime(2024, 1, 1, 14, 20, 0),  # first after gap (dark zone ended)
            dt.datetime(2024, 1, 1, 14, 30, 0),
        ],
        "lat": [51.50, 51.505, 51.510, 51.620, 51.630],
        "lon": [-0.20, -0.190, -0.180, -0.050, -0.040],
        "sog_kn": [12.0, 12.8, 12.3, 11.5, 11.0],  # speed over ground (knots)
    }
).sort("time")

# --- 2) Detect the dark zone (gap larger than threshold) ---
gap_threshold = dt.timedelta(minutes=30)
times = df["time"].to_list()
gap_idx = None  # index i where gap is between rows i and i+1
for i in range(len(times) - 1):
    if times[i + 1] - times[i] > gap_threshold:
        gap_idx = i
        break
assert gap_idx is not None, "No gap detected in sample data."

t_before = df.row(gap_idx)[0]
t_after = df.row(gap_idx + 1)[0]
gap_dur = t_after - t_before
gap_hours = gap_dur.total_seconds() / 3600.0

lat_before = float(df.row(gap_idx)[1])
lon_before = float(df.row(gap_idx)[2])
sog_before = float(df.row(gap_idx)[3])

# --- 3) Compute range rings for the dark zone ---
# Conservative: assume vessel held last SOG during the blackout.
radius_conservative_m = sog_before * gap_hours * NM
# Max: assume an operational cap (e.g., 22 kn) to show "worst-case" reach.
max_speed_kn = 22.0
radius_max_m = max_speed_kn * gap_hours * NM

ring_conservative = geodesic_circle(lon_before, lat_before, radius_conservative_m, n=256)
ring_max = geodesic_circle(lon_before, lat_before, radius_max_m, n=256)

# --- 4) Build map ---
m = PoliumMap(TILES, center=(lat_before, lon_before), zoom_start=10)

# Points with popups (time, sog)
m.add_points(
    df,
    popup=["time", "sog_kn"],
    tooltip="time",
    cluster=False,
    name="AIS points",
)

# Draw known track before the gap (solid line)
coords_before = [(df.row(i)[1], df.row(i)[2]) for i in range(0, gap_idx + 1)]  # (lat, lon)
folium.PolyLine(coords_before, weight=3, color="#2c7fb8", opacity=0.9).add_to(m.folium_map)

# Draw known track after the gap (solid line)
coords_after = [(df.row(i)[1], df.row(i)[2]) for i in range(gap_idx + 1, len(df))]  # (lat, lon)
folium.PolyLine(coords_after, weight=3, color="#41ab5d", opacity=0.9).add_to(m.folium_map)

# Draw a dashed line between last-before-gap and first-after-gap to mark the dark zone span
dash_segment = [(lat_before, lon_before), (float(df.row(gap_idx + 1)[1]), float(df.row(gap_idx + 1)[2]))]
folium.PolyLine(
    dash_segment,
    weight=3,
    color="#e34a33",
    opacity=0.9,
    dash_array="6,6",
    tooltip=f"Dark zone ~ {gap_hours:.1f}h",
).add_to(m.folium_map)

# Add range rings as GeoJSON polygons (max + conservative)
folium.GeoJson(
    {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring_max]}},
    name=f"Range ring max ({max_speed_kn:.0f} kn)",
    style_function=lambda _: {
        "color": "#e34a33",
        "weight": 2,
        "fillColor": "#e34a33",
        "fillOpacity": 0.10,
    },
    tooltip=f"Max reach ~ {radius_max_m/1000:.1f} km in {gap_hours:.1f} h",
).add_to(m.folium_map)

folium.GeoJson(
    {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring_conservative]}},
    name=f"Range ring conservative ({sog_before:.1f} kn)",
    style_function=lambda _: {
        "color": "#2b8cbe",
        "weight": 2,
        "fillColor": "#2b8cbe",
        "fillOpacity": 0.10,
    },
    tooltip=f"Conservative reach ~ {radius_conservative_m/1000:.1f} km",
).add_to(m.folium_map)

# Mark the center (last pre-gap fix)
folium.CircleMarker(
    location=(lat_before, lon_before),
    radius=5,
    color="#000000",
    fill=True,
    fill_opacity=1.0,
    tooltip=f"Last AIS before gap: {t_before}",
).add_to(m.folium_map)

m.add_layer_control().save("ais_dark_zone.html")
print("Saved ais_dark_zone.html")
