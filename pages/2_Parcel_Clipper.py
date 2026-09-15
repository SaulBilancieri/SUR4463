"""Parcel clipper — clip GIS parcels to AOI."""

import tempfile
from pathlib import Path

import streamlit as st

from hub_styles import INFO_PARCEL, render_footer, render_page_shell
from parcel_processor import process_parcels

st.set_page_config(page_title="Parcel Clipper · SUR4463", page_icon="📐", layout="wide")

render_page_shell("Parcel Clipper", show_back=True, info_markdown=INFO_PARCEL)

st.markdown(
    """
<div class="sur-step">
Upload <strong>AOI GeoJSON</strong> + <strong>parcel GIS file</strong> (.zip, .shp, .geojson, .gpkg)
→ download <strong>Parcel_Clipped.zip</strong> for Civil 3D <code>MAPIMPORT</code>.
</div>
""",
    unsafe_allow_html=True,
)

c1, c2 = st.columns(2)
with c1:
    aoi_file = st.file_uploader("AOI GeoJSON", type=["geojson", "json"])
with c2:
    parcel_file = st.file_uploader("Parcel file", type=["zip", "shp", "geojson", "json", "gpkg"])

if st.button("Clip Parcels", type="primary", use_container_width=True, disabled=not (aoi_file and parcel_file)):
    with st.spinner("Clipping parcels…"):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                aoi_path = tmp / "aoi.geojson"
                aoi_path.write_bytes(aoi_file.getvalue())

                ext = Path(parcel_file.name).suffix.lower() or ".zip"
                parcel_path = tmp / f"parcels{ext}"
                parcel_path.write_bytes(parcel_file.getvalue())

                result = process_parcels(aoi_path, parcel_path)
                zip_bytes = result.output_zip.read_bytes()

            st.success("Done")
            m1, m2, m3 = st.columns(3)
            m1.metric("Original", result.original_count)
            m2.metric("Clipped", result.clipped_count)
            m3.metric("Acres", f"{result.acres:,.1f}")

            st.download_button(
                "Download Parcel_Clipped.zip",
                zip_bytes,
                "Parcel_Clipped.zip",
                type="primary",
                use_container_width=True,
            )
            st.caption(f"CRS: {result.crs}")

        except Exception as exc:  # noqa: BLE001
            st.error(f"Processing failed: {exc}")

st.markdown("</div>", unsafe_allow_html=True)
render_footer()
