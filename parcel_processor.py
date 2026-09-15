"""Clip parcel GIS data to an AOI — SUR4463 parcel tool."""

from __future__ import annotations

import glob
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd


@dataclass
class ParcelResult:
    output_zip: Path
    original_count: int
    clipped_count: int
    acres: float
    crs: str


def _detect_crs(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is not None:
        return gdf
    xmin, ymin, xmax, ymax = gdf.total_bounds
    if -180 <= xmin <= 180 and -90 <= ymin <= 90:
        return gdf.set_crs("EPSG:4326")
    if 500000 < xmin < 1200000 and 500000 < ymin < 2000000:
        return gdf.set_crs("EPSG:2236")
    raise ValueError(
        "Unable to determine coordinate system. Assign a CRS to your parcel file first."
    )


def _load_parcels(parcel_path: Path) -> gpd.GeoDataFrame:
    if parcel_path.suffix.lower() == ".zip":
        extract_dir = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(parcel_path, "r") as zf:
            zf.extractall(extract_dir)
        shp_files = glob.glob(str(extract_dir / "**" / "*.shp"), recursive=True)
        if not shp_files:
            raise ValueError("No shapefile found inside the uploaded zip.")
        return gpd.read_file(shp_files[0])
    return gpd.read_file(parcel_path)


def process_parcels(aoi_path: str | Path, parcel_path: str | Path) -> ParcelResult:
    aoi = gpd.read_file(aoi_path)
    parcels = _load_parcels(Path(parcel_path))

    if aoi.empty:
        raise ValueError("AOI GeoJSON contains no features.")

    parcels = _detect_crs(parcels)
    aoi = _detect_crs(aoi)
    aoi = aoi.to_crs(parcels.crs)

    parcels.geometry = parcels.geometry.make_valid()
    aoi.geometry = aoi.geometry.make_valid()

    clipped = gpd.clip(parcels, aoi)
    if clipped.empty:
        raise ValueError("No parcels found inside your AOI. Check that they overlap.")

    work = Path(tempfile.mkdtemp())
    out_dir = work / "Parcel_Clipped"
    out_dir.mkdir()
    shp_path = out_dir / "Parcel_Clipped.shp"
    clipped.to_file(shp_path, driver="ESRI Shapefile")

    zip_path = work / "Parcel_Clipped.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in out_dir.iterdir():
            zf.write(f, arcname=f.name)

    try:
        acres = float(clipped.to_crs(epsg=2236).geometry.area.sum() / 43560.0)
    except Exception:  # noqa: BLE001
        acres = float(clipped.geometry.area.sum() / 43560.0)

    return ParcelResult(
        output_zip=zip_path,
        original_count=len(parcels),
        clipped_count=len(clipped),
        acres=round(acres, 2),
        crs=str(clipped.crs),
    )
