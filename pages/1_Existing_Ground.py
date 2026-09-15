"""Existing Ground DEM processor."""

import importlib
import tempfile
from pathlib import Path

import streamlit as st

import dem_processor
import dem_viz
from hub_styles import INFO_EXISTING_GROUND, render_footer, render_page_shell

importlib.reload(dem_processor)
importlib.reload(dem_viz)
from dem_processor import process_aoi
from dem_viz import make_3d_figure, make_contour_figure

st.set_page_config(page_title="Existing Ground · SUR4463", page_icon="🗺️", layout="wide")

render_page_shell("Existing Ground Processor", show_back=True, info_markdown=INFO_EXISTING_GROUND)

st.markdown(
    """
<style>
    [data-testid="stMetric"] {
        background: #f4f6f8; border: 1px solid #dde3ea; border-radius: 8px; padding: 8px 12px;
    }
    .viz-card {
        background: #0e1117; border: 1px solid #21262d; border-radius: 10px;
        padding: 0.4rem 0.6rem 0.2rem;
    }
    .viz-label { color: #8b949e; font-size: 0.8rem; margin-bottom: 0.2rem; }
</style>
<div class="sur-step">Upload <strong>AOI GeoJSON</strong> only — USGS 3DEP elevation is fetched automatically.</div>
""",
    unsafe_allow_html=True,
)

uploaded = st.file_uploader("AOI GeoJSON", type=["geojson", "json"], label_visibility="collapsed")

col_res, col_btn = st.columns([2, 1])
with col_res:
    resolution = st.selectbox(
        "Resolution",
        options=["Auto (10 m, fallback 30 m)", "10 m", "30 m"],
        label_visibility="collapsed",
    )
with col_btn:
    run = st.button("Process DEM", type="primary", use_container_width=True, disabled=uploaded is None)

if run:
    if uploaded is None:
        st.error("Upload an AOI GeoJSON first.")
        st.stop()

    res_map = {"Auto (10 m, fallback 30 m)": None, "10 m": 10, "30 m": 30}
    aoi_bytes = uploaded.getvalue()

    with st.spinner("Fetching elevation data…"):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                aoi_path = Path(tmp) / "aoi.geojson"
                aoi_path.write_bytes(aoi_bytes)
                out_path = Path(tmp) / "EG.asc"
                result = process_aoi(aoi_path, out_path, resolution_m=res_map[resolution])
                asc_bytes = out_path.read_bytes()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Processing failed: {exc}")
            st.stop()

    st.success("Done")
    for note in result.warnings:
        st.warning(note)
    if result.filled_pct > 0:
        st.info(f"~{result.filled_pct:.0f}% of cells interpolated inside your AOI.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Low (ft)", f"{result.min_elev_ft:,.1f}")
    m2.metric("High (ft)", f"{result.max_elev_ft:,.1f}")
    m3.metric("Relief (ft)", f"{result.max_elev_ft - result.min_elev_ft:,.1f}")
    m4.metric("Acres", f"{result.acres:,.1f}")

    st.download_button("Download EG.asc", asc_bytes, "EG.asc", type="primary", use_container_width=True)

    left, right = st.columns(2, gap="small")
    with left:
        st.markdown('<div class="viz-card"><div class="viz-label">Plan view</div>', unsafe_allow_html=True)
        try:
            st.pyplot(make_contour_figure(asc_bytes, aoi_bytes), clear_figure=True, use_container_width=True)
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="viz-card"><div class="viz-label">3D view · drag to rotate</div>', unsafe_allow_html=True)
        try:
            st.plotly_chart(make_3d_figure(asc_bytes, aoi_bytes), width="stretch", config={"displayModeBar": False})
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
render_footer()
