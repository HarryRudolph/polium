# polium.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Optional, Tuple

import folium
import polars as pl
from branca.colormap import LinearColormap
from folium import GeoJson, Map, Marker, Popup, Tooltip
from folium.plugins import MarkerCluster, TimestampedGeoJson, AntPath

# ----- Optional deps -----
try:
    from shapely.geometry import mapping  # type: ignore
    from shapely.geometry.base import BaseGeometry  # type: ignore

    _HAS_SHAPELY = True
except Exception:  # pragma: no cover
    _HAS_SHAPELY = False
    BaseGeometry = object  # type: ignore

try:
    import h3  # type: ignore

    _HAS_H3 = True
except Exception:  # pragma: no cover
    _HAS_H3 = False

try:
    import pyproj  # type: ignore

    _HAS_PYPROJ = True
except Exception:  # pragma: no cover
    _HAS_PYPROJ = False

# ----- Small helpers -----


def _ensure_latlon(df: pl.DataFrame, lat: str, lon: str) -> None:
    if lat not in df.columns or lon not in df.columns:
        raise KeyError(f"DataFrame must contain '{lat}' and '{lon}' columns.")


def _infer_center(df: pl.DataFrame, lat: str, lon: str) -> tuple[float, float]:
    _ensure_latlon(df, lat, lon)
    la = df[lat].cast(pl.Float64)
    lo = df[lon].cast(pl.Float64)
    return float(la.mean()), float(lo.mean())


def _popup_text(row: dict, keys: list[str]) -> str:
    parts: list[str] = []
    for k in keys:
        if k in row and row[k] is not None:
            parts.append(f"<b>{k}</b>: {row[k]}")
    return "<br/>".join(parts)


def _colormap(values: Iterable[float] | None, cmap: Optional[LinearColormap]) -> LinearColormap:
    if cmap is not None:
        return cmap
    vals: list[float] = []
    if values is not None:
        for v in values:
            try:
                vals.append(float(v))
            except Exception:
                pass
    if not vals:
        return LinearColormap(["#440154", "#21908C", "#FDE725"], vmin=0.0, vmax=1.0)
    vmin = min(vals)
    vmax = max(vals)
    if abs(vmax - vmin) < 1e-12:
        vmax = vmin + 1e-9
    return LinearColormap(["#440154", "#21908C", "#FDE725"], vmin=vmin, vmax=vmax)


def _to_geojson_geom(geom: Any) -> dict:
    """Accept shapely geometry, GeoJSON dict, or list-of-[lon,lat] ring."""
    if isinstance(geom, dict) and "type" in geom and "coordinates" in geom:
        return geom
    if _HAS_SHAPELY and isinstance(geom, BaseGeometry):  # type: ignore[arg-type]
        return mapping(geom)  # type: ignore[misc]
    if isinstance(geom, (list, tuple)) and geom and isinstance(geom[0], (list, tuple)):
        ring = [[float(x), float(y)] for x, y in geom]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        return {"type": "Polygon", "coordinates": [ring]}
    raise TypeError(
        "Unsupported geometry. Provide shapely geometry, GeoJSON geometry dict, "
        "or a list of [lon,lat] ring coordinates."
    )


# H3 compatibility shim (v3/v4), called only if _HAS_H3 is True.
def _h3_boundary(cell: str) -> list[list[float]]:
    if not _HAS_H3:
        raise RuntimeError("h3 not installed. pip install 'h3>=4,<5'  (or h3==3.7.7)")
    if hasattr(h3, "h3_to_geo_boundary"):
        return h3.h3_to_geo_boundary(cell, geo_json=True)  # v3 → [(lat,lon), ...]
    return h3.cell_to_boundary(cell, geo_json=True)  # v4


def _geodesic_circle(lon: float, lat: float, radius_m: float, n: int = 256) -> List[List[float]]:
    if not _HAS_PYPROJ:
        raise RuntimeError("pyproj required for geodesic ring. Install with: pip install pyproj")
    geod = pyproj.Geod(ellps="WGS84")
    coords: List[List[float]] = []
    step = 360.0 / n
    a = 0.0
    for _ in range(n):
        lon2, lat2, _ = geod.fwd(lon, lat, a, radius_m)
        coords.append([lon2, lat2])
        a += step
    coords.append(coords[0])
    return coords


@dataclass
class PoliumMap:
    """Minimal Polars → Folium wrapper using a local tileserver. AIS-friendly visuals by default."""

    tiles_url_template: str
    center: Optional[tuple[float, float]] = None
    zoom_start: int = 10

    def __post_init__(self) -> None:
        self._map = Map(
            location=self.center if self.center is not None else [0.0, 0.0],
            zoom_start=self.zoom_start,
            tiles=None,
            control_scale=True,
            prefer_canvas=True,
        )
        folium.TileLayer(
            tiles=self.tiles_url_template,
            name="Local Tiles",
            attr="Local tiles",
            overlay=False,
            control=True,
        ).add_to(self._map)

    # ---------- AIS-friendly dots (CircleMarker) ----------

    def add_dots(
        self,
        df: pl.DataFrame,
        lat: str = "lat",
        lon: str = "lon",
        *,
        value: Optional[str] = None,  # e.g., "sog_kn" to color by speed
        cmap: Optional[LinearColormap] = None,
        radius: int = 4,
        stroke: bool = True,
        stroke_color: str = "#ffffff",  # white halo for contrast
        stroke_weight: int = 1,
        fill_opacity: float = 0.85,
        default_fill: str = "#1f77b4",
        tooltip: Optional[str] = None,
        popup: Optional[List[str]] = None,
        name: str = "dots",
    ) -> "PoliumMap":
        """
        Plot each row as a small vector dot (CircleMarker). Fast and clean for AIS.
        If `value` provided, colors by a LinearColormap and adds a legend.
        """
        _ensure_latlon(df, lat, lon)
        if self._map.location == [0.0, 0.0] and df.height:
            self._map.location = list(_infer_center(df, lat, lon))

        vals = df[value].to_list() if (value and value in df.columns) else None
        col = _colormap(vals, cmap)

        group = folium.FeatureGroup(name=name, show=True)

        for row in df.to_dicts():
            la = float(row[lat])
            lo = float(row[lon])
            fill = default_fill
            if value and value in row and row[value] is not None:
                try:
                    fill = col(float(row[value]))
                except Exception:
                    pass
            cm = folium.CircleMarker(
                location=(la, lo),
                radius=radius,
                color=stroke_color if stroke else None,
                weight=stroke_weight if stroke else 0,
                fill=True,
                fill_color=fill,
                fill_opacity=fill_opacity,
                opacity=1.0 if stroke else 0.0,
            )
            if tooltip and tooltip in row:
                cm.add_child(Tooltip(str(row[tooltip])))
            if popup:
                cm.add_child(Popup(_popup_text(row, popup), max_width=300))
            cm.add_to(group)

        group.add_to(self._map)
        if value:
            col.caption = f"{name}: {value}"
            col.add_to(self._map)
        return self

    # ---------- Optional: classic pin markers (kept for completeness) ----------

    def add_points(
        self,
        df: pl.DataFrame,
        lat: str = "lat",
        lon: str = "lon",
        popup: Optional[List[str]] = None,
        tooltip: Optional[str] = None,
        cluster: bool = True,
        name: str = "points",
    ) -> "PoliumMap":
        """Classic pin markers; prefer `add_dots` for AIS."""
        _ensure_latlon(df, lat, lon)
        if self._map.location == [0.0, 0.0] and df.height:
            self._map.location = list(_infer_center(df, lat, lon))

        group = folium.FeatureGroup(name=name, show=True)
        container: Any = MarkerCluster(name=name) if cluster else group

        for row in df.to_dicts():
            la = float(row[lat])
            lo = float(row[lon])
            m = Marker(location=(la, lo))
            if popup:
                m.add_child(Popup(_popup_text(row, popup), max_width=300))
            if tooltip and tooltip in row:
                m.add_child(Tooltip(str(row[tooltip])))
            m.add_to(container)

        if cluster:
            container.add_to(group)
        group.add_to(self._map)
        return self

    # ---------- Time points (always-on plugin; not toggleable in LayerControl) ----------

    def add_time_points(
        self,
        df: pl.DataFrame,
        time: str,
        lat: str = "lat",
        lon: str = "lon",
        popup: Optional[List[str]] = None,
        tooltip: Optional[str] = None,
        period: str = "P1D",
        name: str = "time-points",  # kept for API symmetry
    ) -> "PoliumMap":
        _ensure_latlon(df, lat, lon)
        feats: list[dict[str, Any]] = []
        for row in df.to_dicts():
            t = row[time]
            ts = t.isoformat() if isinstance(t, datetime) else str(t)
            props: dict[str, Any] = {"time": ts}
            if tooltip and tooltip in row:
                props["tooltip"] = str(row[tooltip])
            if popup:
                props["popup"] = _popup_text(row, popup)
            feats.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [float(row[lon]), float(row[lat])]},
                    "properties": props,
                }
            )

        TimestampedGeoJson(
            {"type": "FeatureCollection", "features": feats},
            period=period,
            transition_time=200,
            add_last_point=True,
            auto_play=False,
            loop=False,
            duration="P1D",
        ).add_to(self._map)
        return self

    # ---------- Choropleth + H3 (unchanged APIs) ----------

    def add_choropleth(
        self,
        df: pl.DataFrame,
        geometry: str = "geometry",
        value: Optional[str] = None,
        cmap: Optional[LinearColormap] = None,
        fill_opacity: float = 0.6,
        line_opacity: float = 0.2,
        name: str = "choropleth",
    ) -> "PoliumMap":
        if geometry not in df.columns:
            raise KeyError(f"Expected a '{geometry}' column with polygons.")
        feats: list[dict[str, Any]] = []
        vals: list[float] = []
        for row in df.to_dicts():
            gj = _to_geojson_geom(row[geometry])
            props: dict[str, Any] = {}
            if value is not None:
                v = float(row[value])
                props["value"] = v
                vals.append(v)
            feats.append({"type": "Feature", "geometry": gj, "properties": props})
        col = _colormap(vals, cmap)

        def style_fn(feat: dict[str, Any]) -> dict[str, Any]:
            v = feat.get("properties", {}).get("value")
            return {
                "fillColor": col(v) if v is not None else "#3388ff",
                "color": "#000000",
                "weight": 1,
                "fillOpacity": fill_opacity,
                "opacity": line_opacity,
            }

        GeoJson({"type": "FeatureCollection", "features": feats}, name=name, style_function=style_fn).add_to(self._map)
        if value is not None:
            col.caption = name
            col.add_to(self._map)
        return self

    def add_h3_hexes(
        self,
        df: pl.DataFrame,
        h3_col: str = "h3",
        value: Optional[str] = None,
        cmap: Optional[LinearColormap] = None,
        fill_opacity: float = 0.6,
        line_opacity: float = 0.2,
        name: str = "h3",
    ) -> "PoliumMap":
        if not _HAS_H3:
            raise RuntimeError(
                "h3 not installed. Install one of:\n"
                "  pip install 'h3>=4,<5'   # recommended\n"
                "  CMAKE_POLICY_VERSION_MINIMUM=3.5 pip install 'h3==3.7.7'"
            )
        if h3_col not in df.columns:
            raise KeyError(f"Expected an '{h3_col}' column with H3 cells.")
        feats: list[dict[str, Any]] = []
        vals: list[float] = []
        for row in df.to_dicts():
            cell = str(row[h3_col])
            boundary = _h3_boundary(cell)  # [(lat,lon), ...]
            coords = [[lon, lat] for lat, lon in boundary]
            if coords and coords[0] != coords[-1]:
                coords.append(coords[0])
            props: dict[str, Any] = {}
            if value is not None:
                v = float(row[value])
                props["value"] = v
                vals.append(v)
            feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]}, "properties": props})
        col = _colormap(vals, cmap)

        def style_fn(feat: dict[str, Any]) -> dict[str, Any]:
            v = feat.get("properties", {}).get("value")
            return {
                "fillColor": col(v) if v is not None else "#3388ff",
                "color": "#000000",
                "weight": 1,
                "fillOpacity": fill_opacity,
                "opacity": line_opacity,
            }

        GeoJson({"type": "FeatureCollection", "features": feats}, name=name, style_function=style_fn).add_to(self._map)
        if value is not None:
            col.caption = name
            col.add_to(self._map)
        return self

    # ---------- Track + Range ring (AIS utilities) ----------

    def add_track(
        self,
        df: pl.DataFrame,
        lat: str = "lat",
        lon: str = "lon",
        *,
        name: str = "track",
        weight: int = 3,
        color: str = "#2c7fb8",
        opacity: float = 0.9,
        dashed: bool = False,
        ant_path: bool = False,
        show_endpoints: bool = True,
        endpoint_color: str = "#000000",
    ) -> "PoliumMap":
        """Draw a polyline through the points (in row order)."""
        _ensure_latlon(df, lat, lon)
        coords = [(float(r[lat]), float(r[lon])) for r in df.to_dicts()]
        if not coords:
            return self
        if ant_path:
            AntPath(locations=coords, weight=weight, opacity=opacity, color=color).add_to(self._map)
        else:
            folium.PolyLine(
                coords,
                weight=weight,
                color=color,
                opacity=opacity,
                dash_array="6,6" if dashed else None,
                name=name,
            ).add_to(self._map)
        if show_endpoints:
            # start (green), end (red)
            folium.CircleMarker(coords[0], radius=5, color="#2ca25f", fill=True, fill_opacity=1).add_to(self._map)
            folium.CircleMarker(coords[-1], radius=5, color="#de2d26", fill=True, fill_opacity=1).add_to(self._map)
        return self

    def add_range_ring(
        self,
        center: Tuple[float, float],  # (lat, lon)
        radius_m: float,
        *,
        name: str = "range",
        line_color: str = "#e34a33",
        line_weight: int = 2,
        fill_color: str = "#e34a33",
        fill_opacity: float = 0.10,
        n: int = 256,
        tooltip: Optional[str] = None,
    ) -> "PoliumMap":
        """Geodesic ring polygon; requires pyproj."""
        lat, lon = float(center[0]), float(center[1])
        ring = _geodesic_circle(lon=lon, lat=lat, radius_m=radius_m, n=n)
        gj = GeoJson(
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}},
            name=name,
            style_function=lambda _feat: {
                "color": line_color,
                "weight": line_weight,
                "fillColor": fill_color,
                "fillOpacity": fill_opacity,
            },
        )
        if tooltip:
            gj.add_child(folium.Tooltip(tooltip))
        gj.add_to(self._map)
        folium.CircleMarker((lat, lon), radius=4, color=line_color, fill=True, fill_opacity=1).add_to(self._map)
        return self

    # ---------- Output / control ----------

    def add_layer_control(self, collapsed: bool = False) -> "PoliumMap":
        folium.LayerControl(position="topright", collapsed=collapsed).add_to(self._map)
        return self

    def to_html(self) -> str:
        return self._map.get_root().render()

    def save(self, path: str) -> str:
        self._map.save(path)
        return path

    @property
    def folium_map(self) -> Map:
        return self._map
