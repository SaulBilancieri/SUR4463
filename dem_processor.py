"""SUR4463 DEM processor — multi-source fetch, gap fill, EG.asc output."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import numpy as np
import py3dep
import rasterio
import requests
from pyproj import CRS, Transformer
from rasterio.features import rasterize
from rasterio.fill import fillnodata
from rasterio.mask import mask
from rasterio.warp import Resampling, calculate_default_transform, reproject
from shapely.geometry import mapping


TARGET_CRS = CRS.from_epsg(2236)  # NAD83 / Florida East (ftUS)
WORK_CRS = CRS.from_epsg(5070)  # USGS 3DEP working projection
SURVEY_FT_PER_M = 3.280833333
NODATA = -9999.0
IMAGE_SERVER = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/"
    "3DEPElevation/ImageServer/exportImage"
)
MAX_IMAGE_PX = 4000
MIN_VALID_BEFORE_FILL = 0.05  # need at least 5% real pixels unless we expand


@dataclass
class DemResult:
    output_path: Path
    crs: str
    resolution: tuple[float, float]
    acres: float
    min_elev_ft: float
    max_elev_ft: float
    dem_source: str
    dem_resolution_m: int | str
    filled_pct: float = 0.0
    warnings: list[str] = field(default_factory=list)


def _invalid_mask(z: np.ndarray, nodata: float | None) -> np.ndarray:
    invalid = np.isnan(z)
    if nodata is not None and not np.isnan(nodata):
        invalid |= z == nodata
    invalid |= z < -500
    invalid |= z > 9000
    return invalid


def _valid_fraction(z: np.ndarray, nodata: float | None) -> float:
    return float(1.0 - _invalid_mask(z, nodata).mean())


def _rasterize_aoi(aoi: gpd.GeoDataFrame, shape: tuple[int, int], transform) -> np.ndarray:
    """True where cell center is inside the AOI polygon(s)."""
    geoms = [(geom, 1) for geom in aoi.geometry if geom is not None and not geom.is_empty]
    if not geoms:
        raise ValueError("AOI GeoJSON contains no valid geometries.")
    burned = rasterize(
        geoms,
        out_shape=shape,
        transform=transform,
        fill=0,
        all_touched=True,
        dtype="uint8",
    )
    return burned.astype(bool)


def _enforce_aoi_mask(z: np.ndarray, inside_mask: np.ndarray, nodata: float = NODATA) -> np.ndarray:
    out = z.astype("float32", copy=True)
    out[~inside_mask] = nodata
    return out


def _fill_gaps(
    z: np.ndarray,
    nodata: float | None,
    inside_mask: np.ndarray | None = None,
    max_search: float = 500.0,
) -> tuple[np.ndarray, float]:
    """Fill nodata only inside the AOI — never spill into the bounding box voids."""
    arr = _enforce_aoi_mask(z, inside_mask, nodata or NODATA) if inside_mask is not None else z.astype("float32", copy=True)
    nd = nodata if nodata is not None else NODATA

    if inside_mask is None:
        fill_region = np.ones(arr.shape, dtype=bool)
    else:
        fill_region = inside_mask

    invalid = _invalid_mask(arr, nd) & fill_region
    if not invalid.any():
        return arr, 0.0

    fill_pct = 100.0 * invalid.sum() / max(fill_region.sum(), 1)
    valid_for_fill = (~_invalid_mask(arr, nd) & fill_region).astype("uint8")

    if valid_for_fill.sum() == 0:
        arr[invalid] = 0.0
        return _enforce_aoi_mask(arr, fill_region, nd), fill_pct

    filled = fillnodata(arr, mask=valid_for_fill, max_search_distance=max_search)
    still_bad = _invalid_mask(filled, nd) & fill_region
    if still_bad.any():
        fallback = float(np.nanmean(filled[~(_invalid_mask(filled, nd) & fill_region)]))
        filled[still_bad] = fallback

    filled = np.where(filled < 0, 0.0, filled)
    if inside_mask is not None:
        filled = _enforce_aoi_mask(filled, inside_mask, nd)
    return filled, fill_pct


def _write_array(path: Path, arr: np.ndarray, transform, crs, nodata: float | None = None) -> None:
    meta = {
        "driver": "GTiff",
        "height": arr.shape[0],
        "width": arr.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "compress": "lzw",
    }
    if nodata is not None:
        meta["nodata"] = nodata
    with rasterio.open(path, "w", **meta) as dst:
        dst.write(arr.astype("float32"), 1)


def _fetch_py3dep(aoi: gpd.GeoDataFrame, resolution_m: int, buffer_m: float) -> tuple[Path, str, float]:
    geom = _buffered_geom(aoi, buffer_m)
    dem = py3dep.get_dem(geom, resolution_m)
    fetch_tif = Path(tempfile.gettempdir()) / f"fetch_py3dep_{resolution_m}.tif"
    dem.rio.to_raster(fetch_tif)
    with rasterio.open(fetch_tif) as src:
        z = src.read(1)
        vf = _valid_fraction(z, src.nodata)
    return fetch_tif, f"USGS 3DEP {resolution_m} m", vf


def _buffered_geom(aoi: gpd.GeoDataFrame, buffer_m: float):
    aoi_wgs84 = aoi.to_crs(4326)
    if buffer_m <= 0:
        return aoi_wgs84.union_all()
    proj = aoi.to_crs(WORK_CRS)
    buffered = proj.union_all().buffer(buffer_m)
    return gpd.GeoSeries([buffered], crs=WORK_CRS).to_crs(4326).union_all()


def _fetch_imageserver(aoi: gpd.GeoDataFrame, resolution_m: int, buffer_m: float) -> tuple[Path, str, float]:
    aoi_wgs84 = aoi.to_crs(4326)
    geom = _buffered_geom(aoi, buffer_m)
    minx, miny, maxx, maxy = gpd.GeoSeries([geom], crs=4326).total_bounds

    transformer = Transformer.from_crs(4326, WORK_CRS, always_xy=True)
    x0, y0 = transformer.transform(minx, miny)
    x1, y1 = transformer.transform(maxx, maxy)
    width_m = abs(x1 - x0)
    height_m = abs(y1 - y0)

    width_px = int(max(width_m / resolution_m, 128))
    height_px = int(max(height_m / resolution_m, 128))
    scale = min(1.0, MAX_IMAGE_PX / max(width_px, height_px))
    width_px = max(int(width_px * scale), 128)
    height_px = max(int(height_px * scale), 128)

    params = {
        "f": "image",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "bboxSR": 4326,
        "imageSR": WORK_CRS.to_epsg(),
        "size": f"{width_px},{height_px}",
        "format": "tiff",
        "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation",
    }
    resp = requests.get(IMAGE_SERVER, params=params, timeout=180)
    resp.raise_for_status()
    if len(resp.content) < 1000:
        raise RuntimeError("ImageServer returned empty response.")

    fetch_tif = Path(tempfile.gettempdir()) / f"fetch_imageserver_{resolution_m}.tif"
    fetch_tif.write_bytes(resp.content)

    with rasterio.open(fetch_tif) as src:
        vf = _valid_fraction(src.read(1), src.nodata)
    eff_res = int(round(resolution_m * (1 / scale))) if scale < 1 else resolution_m
    return fetch_tif, f"USGS 3DEP ImageServer (~{eff_res} m)", vf


def _fetch_dem(
    aoi: gpd.GeoDataFrame,
    resolution_m: int | None = None,
) -> tuple[Path, str, int | str, list[str]]:
    """Try multiple sources/buffers; always return the best available raster."""
    warnings: list[str] = []
    resolutions = [resolution_m] if resolution_m else [10, 30]
    buffers = [100, 400, 1000, 2500]  # meters — expand until we get land pixels

    candidates: list[tuple[float, Path, str, int | str]] = []

    for buffer_m in buffers:
        for res in resolutions:
            for fetcher, tag in (
                (_fetch_py3dep, "py3dep"),
                (_fetch_imageserver, "imageserver"),
            ):
                try:
                    path, source, vf = fetcher(aoi, res, buffer_m)
                    candidates.append((vf, path, source, res))
                    if vf >= 0.5:
                        break
                except Exception:
                    continue
            if candidates and candidates[-1][0] >= 0.5:
                break
        if candidates and max(c[0] for c in candidates) >= MIN_VALID_BEFORE_FILL:
            break

    if not candidates:
        raise RuntimeError(
            "Could not fetch elevation data for this AOI. "
            "Check that your AOI is in the US and overlaps land."
        )

    candidates.sort(key=lambda c: c[0], reverse=True)
    best_vf, best_path, best_source, best_res = candidates[0]

    if best_vf < MIN_VALID_BEFORE_FILL:
        warnings.append(
            "Very little native elevation coverage for this AOI (likely mostly water). "
            "Gaps were filled by interpolation from nearby land."
        )
    elif best_vf < 0.8:
        warnings.append(
            f"About {round(100 * (1 - best_vf), 1)}% of the AOI had no native DEM cells "
            "(water/void). Gaps were filled by interpolation."
        )

    return best_path, best_source, best_res, warnings


def process_aoi(
    aoi_path: str | Path,
    output_path: str | Path | None = None,
    resolution_m: int | None = None,
) -> DemResult:
    """AOI GeoJSON -> auto-fetch DEM -> clip -> fill gaps -> EG.asc."""
    aoi_path = Path(aoi_path)
    output_path = Path(output_path or Path(tempfile.gettempdir()) / "EG.asc")
    temp_clip = output_path.with_suffix(".clip.tif")

    aoi = gpd.read_file(aoi_path)
    if aoi.empty:
        raise ValueError("AOI GeoJSON contains no features.")

    fetch_tif, source_name, used_res, warnings = _fetch_dem(aoi, resolution_m)
    total_fill_pct = 0.0

    try:
        with rasterio.open(fetch_tif) as src:
            aoi_reproj = aoi.to_crs(src.crs)
            clipped, transform = mask(
                src,
                [mapping(aoi_reproj.union_all())],
                crop=True,
                nodata=src.nodata,
                filled=False,
            )
            band = clipped[0].astype("float32")
            inside_mask = _rasterize_aoi(aoi_reproj, band.shape, transform)
            band = _enforce_aoi_mask(band, inside_mask, src.nodata or NODATA)
            band, fill_pct = _fill_gaps(band, src.nodata, inside_mask=inside_mask, max_search=800)
            total_fill_pct = fill_pct

            _write_array(temp_clip, band, transform, src.crs, nodata=src.nodata or NODATA)

        with rasterio.open(temp_clip) as src:
            out_transform, width, height = calculate_default_transform(
                src.crs,
                TARGET_CRS,
                src.width,
                src.height,
                *src.bounds,
                resolution=SURVEY_FT_PER_M,
            )

            profile = src.profile.copy()
            profile.update(
                {
                    "driver": "AAIGrid",
                    "crs": TARGET_CRS,
                    "transform": out_transform,
                    "width": width,
                    "height": height,
                    "dtype": "float32",
                    "nodata": NODATA,
                }
            )

            with rasterio.open(output_path, "w", **profile) as dst:
                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    src_nodata=src.nodata if src.nodata is not None else NODATA,
                    dst_transform=out_transform,
                    dst_crs=TARGET_CRS,
                    dst_nodata=NODATA,
                    resampling=Resampling.bilinear,
                )

        aoi_target = aoi.to_crs(TARGET_CRS)
        with rasterio.open(output_path, "r+") as dst:
            z = dst.read(1).astype("float32")
            inside_mask = _rasterize_aoi(aoi_target, z.shape, dst.transform)
            z = _enforce_aoi_mask(z, inside_mask, NODATA)
            z, post_fill = _fill_gaps(z, NODATA, inside_mask=inside_mask, max_search=200)
            total_fill_pct = max(total_fill_pct, post_fill)
            z = np.where(z < 0, 0.0, z)
            z = np.where((z != NODATA) & inside_mask, z * SURVEY_FT_PER_M, NODATA)
            dst.write(z, 1)

        with rasterio.open(output_path) as src:
            z = src.read(1)
            valid = z[z != NODATA]
            if valid.size == 0:
                # Absolute last resort — should never happen now
                warnings.append("No elevation cells after processing; using flat 10 ft surface.")
                z = np.full_like(z, 10.0, dtype="float32")
                with rasterio.open(output_path, "r+") as dst:
                    dst.write(z, 1)
                valid = z

            acres = float(aoi.to_crs(TARGET_CRS).geometry.area.sum() / 43560.0)

            return DemResult(
                output_path=output_path,
                crs=str(src.crs),
                resolution=src.res,
                acres=round(acres, 2),
                min_elev_ft=round(float(valid.min()), 2),
                max_elev_ft=round(float(valid.max()), 2),
                dem_source=source_name,
                dem_resolution_m=used_res,
                filled_pct=round(float(total_fill_pct), 1),
                warnings=warnings,
            )
    finally:
        if fetch_tif.exists() and "fetch_" in fetch_tif.name:
            fetch_tif.unlink(missing_ok=True)
        temp_clip.unlink(missing_ok=True)
