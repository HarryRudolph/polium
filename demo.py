# demo.py
import polars as pl
from polium import PoliumMap  # imports from polium.py in the same folder

TILES = "http://127.0.0.1:8080/{z}/{x}/{y}.png"
TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

# points
df_pts = pl.DataFrame({
    "lat": [51.5074, 51.52, 51.49],
    "lon": [-0.1278, -0.10, -0.15],
    "name": ["Westminster", "Regent's Park", "Battersea"],
})

m = PoliumMap(TILES, center=(51.5074, -0.1278), zoom_start=12)
m.add_points(df_pts, popup=["name"], tooltip="name", cluster=True, name="Places")

# time points
df_time = df_pts.with_columns(pl.datetime_range(pl.datetime(2024,1,1), pl.datetime(2024,1,3), "1d").alias("time"))
m.add_time_points(df_time, time="time", popup=["name"], name="When")

# optional: H3 hexes (requires `pip install "h3>=4,<5"`)
# import h3
# cell = h3.latlng_to_cell(51.5074, -0.1278, 8)
# df_hex = pl.DataFrame({"h3": [cell], "value": [42]})
# m.add_h3_hexes(df_hex, value="value", name="Density")

m.add_layer_control().save("out.html")
print("Saved out.html")

