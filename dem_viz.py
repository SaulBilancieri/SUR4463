"""Elevation visualizations for SUR4463 DEM output."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
import rasterio
from pyproj import CRS
from rasterio.features import rasterize
from rasterio.transform import Affine
from scipy.ndimage import gaussian_filter


NODATA = -9999.0
TARGET_CRS = CRS.from_epsg(2236)
MAX_VIZ_DIM = 280
BG = "#0e1117"
TEXT = "#e8eaed"
ACCENT_LOW = "#6ea8fe"
ACCENT_HIGH = "#ff6b6b"
OUTLINE = "#ffffff"


def _load_aoi(aoi_source: str | Path | bytes) -> gpd.GeoDataFrame:
    if isinstance(aoi_source, bytes):
        gdf = gpd.read_file(BytesIO(aoi_source))
    else:
        gdf = gpd.read_file(aoi_source)
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    return gdf.to_crs(TARGET_CRS)


def _load_dem(source: str | Path | bytes) -> tuple[np.ndarray, Affine, float, CRS]:
    if isinstance(source, bytes):
        src_ctx = rasterio.open(BytesIO(source))
    else:
        src_ctx = rasterio.open(source)

    with src_ctx as src:
        z = src.read(1).astype("float32")
        transform = src.transform
        nodata = float(src.nodata if src.nodata is not None else NODATA)
        crs = src.crs if src.crs is not None else TARGET_CRS
    return z, transform, nodata, crs


def _inside_mask(aoi: gpd.GeoDataFrame, shape: tuple[int, int], transform) -> np.ndarray:
    geoms = [(geom, 1) for geom in aoi.geometry if geom is not None and not geom.is_empty]
    if not geoms:
        return np.zeros(shape, dtype=bool)
    burned = rasterize(
        geoms, out_shape=shape, transform=transform, fill=0, all_touched=True, dtype="uint8"
    )
    return burned.astype(bool)


def _display_grid(z: np.ndarray, nodata: float, inside_mask: np.ndarray) -> np.ndarray:
    out = z.astype("float32", copy=True)
    out[out == nodata] = np.nan
    out[~inside_mask] = np.nan
    return out


def _smooth(valid: np.ndarray, sigma: float = 1.8) -> np.ndarray:
    """Light smoothing — reduces jagged DEM noise without changing overall shape."""
    mask = ~np.isnan(valid)
    if mask.sum() < 4:
        return valid
    filled = np.where(mask, valid, 0.0)
    weights = gaussian_filter(mask.astype(float), sigma=sigma)
    smoothed = gaussian_filter(filled, sigma=sigma) / np.maximum(weights, 1e-6)
    smoothed[~mask] = np.nan
    return smoothed.astype("float32")


def _downsample(z: np.ndarray, transform: Affine, inside_mask: np.ndarray, max_dim: int = MAX_VIZ_DIM):
    rows, cols = z.shape
    step = max(1, int(np.ceil(max(rows, cols) / max_dim)))
    return z[::step, ::step], transform * Affine.scale(step, step), inside_mask[::step, ::step]


def _extreme_points(valid: np.ndarray, transform: Affine):
    flat_min = np.nanargmin(valid)
    flat_max = np.nanargmax(valid)
    min_row, min_col = np.unravel_index(flat_min, valid.shape)
    max_row, max_col = np.unravel_index(flat_max, valid.shape)
    min_x, min_y = rasterio.transform.xy(transform, min_row, min_col)
    max_x, max_y = rasterio.transform.xy(transform, max_row, max_col)
    return (min_x, min_y, float(valid[min_row, min_col])), (max_x, max_y, float(valid[max_row, max_col]))


def _grid_coords(shape: tuple[int, int], transform: Affine) -> tuple[np.ndarray, np.ndarray]:
    rows, cols = shape
    cols_idx = np.arange(cols)
    rows_idx = np.arange(rows)
    xs = transform.c + cols_idx * transform.a + transform.b * rows_idx[:, None]
    ys = transform.f + cols_idx * transform.d + transform.e * rows_idx[:, None]
    return xs, ys


def _true_aspect_ratio(xs: np.ndarray, ys: np.ndarray, valid: np.ndarray) -> dict[str, float]:
    """Balanced vertical exaggeration — readable but not spiky."""
    x_span = float(np.nanmax(xs) - np.nanmin(xs))
    y_span = float(np.nanmax(ys) - np.nanmin(ys))
    z_span = float(np.nanmax(valid) - np.nanmin(valid))
    horiz = max(x_span, y_span, 1.0)
    z_ratio = z_span / horiz

    # More boost on flat sites, less on steep ones
    if z_span < 8:
        boost = 12.0
    elif z_span < 20:
        boost = 7.0
    elif z_span < 40:
        boost = 4.0
    else:
        boost = 2.5

    z_ratio = min(max(z_ratio * boost, 0.015), 0.055)
    return {"x": 1.0, "y": 1.0, "z": z_ratio}


def _prepare(source: str | Path | bytes, aoi_source: str | Path | bytes, max_dim: int, smooth: bool):
    z, transform, nodata, _ = _load_dem(source)
    aoi = _load_aoi(aoi_source)
    inside_mask = _inside_mask(aoi, z.shape, transform)
    if not inside_mask.any():
        inside_mask = z != nodata
    z, transform, inside_mask = _downsample(z, transform, inside_mask, max_dim=max_dim)
    valid = _display_grid(z, nodata, inside_mask)
    if smooth:
        valid = _smooth(valid, sigma=1.6 if max_dim <= 240 else 1.2)
    xs, ys = _grid_coords(valid.shape, transform)
    return valid, xs, ys, transform, aoi


def _style_matplotlib_ax(ax):
    ax.set_facecolor(BG)
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    for spine in ax.spines.values():
        spine.set_visible(False)


def _popout_label(ax, xy, text, color, offset=(24, 24)):
    ax.annotate(
        text,
        xy,
        xytext=offset,
        textcoords="offset points",
        fontsize=10,
        color="white",
        fontweight="bold",
        ha="center",
        va="center",
        zorder=10,
        bbox={
            "boxstyle": "round,pad=0.45",
            "fc": color,
            "ec": "white",
            "alpha": 0.95,
            "linewidth": 1.4,
        },
        arrowprops={
            "arrowstyle": "-|>",
            "color": "white",
            "lw": 1.4,
            "shrinkA": 0,
            "shrinkB": 6,
            "connectionstyle": "arc3,rad=0.08",
        },
    )


def _plot_aoi_outline(ax, aoi: gpd.GeoDataFrame):
    for geom in aoi.geometry:
        if geom is None or geom.is_empty:
            continue
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for poly in polys:
            x, y = poly.exterior.xy
            ax.plot(x, y, color=OUTLINE, linewidth=1.2, alpha=0.9)


def make_contour_figure(
    source: str | Path | bytes,
    aoi_source: str | Path | bytes,
) -> plt.Figure:
    valid, xs, ys, transform, aoi = _prepare(source, aoi_source, MAX_VIZ_DIM, smooth=True)
    (min_x, min_y, min_z), (max_x, max_y, max_z) = _extreme_points(valid, transform)

    vmin = float(np.nanmin(valid))
    vmax = float(np.nanmax(valid))
    span = max(vmax - vmin, 0.5)
    n_levels = min(14, max(5, int(span / 0.5)))
    levels = np.linspace(vmin, vmax, n_levels)

    fig, ax = plt.subplots(figsize=(7.5, 6.5), dpi=130)
    fig.patch.set_facecolor(BG)
    _style_matplotlib_ax(ax)

    terrain = ax.contourf(xs, ys, valid, levels=levels, cmap="terrain", alpha=0.92, antialiased=True)
    ax.contour(xs, ys, valid, levels=levels, colors="#ffffff22", linewidths=0.4)
    _plot_aoi_outline(ax, aoi)

    ax.scatter([min_x], [min_y], c=ACCENT_LOW, s=85, edgecolors="white", linewidths=1.8, zorder=6)
    ax.scatter([max_x], [max_y], c=ACCENT_HIGH, s=85, edgecolors="white", linewidths=1.8, zorder=6)
    _popout_label(ax, (min_x, min_y), f"LOW\n{min_z:.1f} ft", ACCENT_LOW, offset=(-32, -36))
    _popout_label(ax, (max_x, max_y), f"HIGH\n{max_z:.1f} ft", ACCENT_HIGH, offset=(32, 36))

    ax.set_aspect("equal")
    cbar = fig.colorbar(terrain, ax=ax, shrink=0.72, pad=0.02, fraction=0.035)
    cbar.ax.tick_params(colors=TEXT, labelsize=8)
    cbar.outline.set_visible(False)
    cbar.set_label("ft", color=TEXT, fontsize=9)
    fig.subplots_adjust(left=0.02, right=0.92, top=0.98, bottom=0.02)
    return fig


def _plotly_scene_axis() -> dict:
    return dict(
        showgrid=False,
        showline=False,
        zeroline=False,
        showticklabels=False,
        showbackground=False,
        title="",
    )


def make_3d_figure(
    source: str | Path | bytes,
    aoi_source: str | Path | bytes,
) -> go.Figure:
    valid, xs, ys, transform, aoi = _prepare(source, aoi_source, max_dim=180, smooth=True)
    (min_x, min_y, min_z), (max_x, max_y, max_z) = _extreme_points(valid, transform)
    z_min = float(np.nanmin(valid))
    z_max = float(np.nanmax(valid))
    aspect = _true_aspect_ratio(xs, ys, valid)

    colorscale = [
        [0.0, "#2d4a22"], [0.35, "#5a7a3a"], [0.65, "#a89068"], [1.0, "#ddd0b8"],
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Surface(
            x=xs, y=ys, z=valid, surfacecolor=valid, colorscale=colorscale,
            cmin=z_min, cmax=z_max, showscale=False, opacity=0.97,
            contours={"z": {"show": True, "usecolormap": False, "width": 1, "color": "#ffffff18"}},
            hovertemplate="Elev: %{z:.1f} ft<extra></extra>",
            lighting={"ambient": 0.75, "diffuse": 0.55, "specular": 0.05, "roughness": 0.9},
        )
    )

    outline_x, outline_y, outline_z = [], [], []
    for geom in aoi.geometry:
        if geom is None or geom.is_empty:
            continue
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for poly in polys:
            px, py = poly.exterior.xy
            outline_x.extend(list(px) + [None])
            outline_y.extend(list(py) + [None])
            outline_z.extend([z_min] * len(px) + [None])

    fig.add_trace(go.Scatter3d(
        x=outline_x, y=outline_y, z=outline_z, mode="lines", name="AOI",
        line={"color": "#ffffffaa", "width": 3}, hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter3d(
        x=[min_x], y=[min_y], z=[min_z], mode="markers+text", name="Low",
        marker={"size": 5, "color": ACCENT_LOW, "line": {"color": "white", "width": 1}},
        text=[f"LOW {min_z:.1f} ft"],
        textfont={"size": 11, "color": "white"},
        textposition="bottom center", showlegend=False,
    ))
    fig.add_trace(go.Scatter3d(
        x=[max_x], y=[max_y], z=[max_z], mode="markers+text", name="High",
        marker={"size": 5, "color": ACCENT_HIGH, "line": {"color": "white", "width": 1}},
        text=[f"HIGH {max_z:.1f} ft"],
        textfont={"size": 11, "color": "white"},
        textposition="top center", showlegend=False,
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": TEXT, "size": 11},
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        height=480,
        scene={
            "xaxis": _plotly_scene_axis(),
            "yaxis": _plotly_scene_axis(),
            "zaxis": _plotly_scene_axis(),
            "aspectmode": "manual",
            "aspectratio": aspect,
            "bgcolor": "rgba(0,0,0,0)",
            "camera": {"eye": {"x": 1.35, "y": -1.35, "z": 0.75}, "center": {"x": 0, "y": 0, "z": 0}},
        },
        annotations=[{
            "text": f"Δ elev {z_max - z_min:.1f} ft · drag to rotate",
            "xref": "paper", "yref": "paper", "x": 0.5, "y": 1.0,
            "showarrow": False, "font": {"size": 11, "color": "#9aa0a6"},
        }],
    )
    return fig
