# demo_ais_pretty.py
import datetime as dt
import polars as pl
from polium import PoliumMap

TILES = "http://127.0.0.1:8080/{z}/{x}/{y}.png"
TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

df = pl.DataFrame({
    "time": [dt.datetime(2024,1,1,12,0), dt.datetime(2024,1,1,12,10), dt.datetime(2024,1,1,12,20),
             dt.datetime(2024,1,1,14,20), dt.datetime(2024,1,1,14,30)],
    "lat":  [51.50, 51.505, 51.510, 51.620, 51.630],
    "lon":  [-0.20, -0.190, -0.180, -0.050, -0.040],
    "sog_kn":[12.0, 12.8, 12.3, 11.5, 11.0],
})

m = PoliumMap(TILES, center=(51.54, -0.12), zoom_start=10)

# Optional: range ring (e.g., 22 kn for 2 hours) around last fix before a gap
NM = 1852.0
gap_hours = 2.0
max_speed_kn = 22.0
radius_m = max_speed_kn * gap_hours * NM
last_pre_gap = df.row(2)  # index of last point before a gap
m.add_range_ring(center=(float(last_pre_gap[1]), float(last_pre_gap[2])),
                 radius_m=radius_m,
                 name="Max reach 2h @ 22 kn",
                #  tooltip=f"~{radius_m/1000:.1f} km"
                 )


# Track line with start (green) and end (red) markers.
m.add_track(df, name="Track", color="#2c7fb8", weight=3, ant_path=False)
# Dots colored by speed (legend auto-added). White halo for map contrast.
m.add_dots(df, 
        #    value="sog_kn", 
           tooltip="time", popup=["time","sog_kn"], name="AIS dots")

m.save("ais_pretty.html")
print("Saved ais_pretty.html")
