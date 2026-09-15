"""SUR4463 Course Hub — landing page."""

import streamlit as st

from hub_styles import (
    INFO_HUB,
    PLAYLIST_URL,
    TEMPLATE_URL,
    render_footer,
    render_page_shell,
)

st.set_page_config(
    page_title="SUR4463 · Subdivision Design",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

render_page_shell("Course Hub", info_markdown=INFO_HUB)

st.markdown(
    """
<div class="sur-welcome">
Welcome to <strong>SUR4463 — Subdivision Design</strong>. Learn civil site design and land
development with <strong>AutoCAD Civil 3D</strong>. Use the tools below to prepare base mapping
data, then follow the video series for the full Civil 3D workflow.
</div>
""",
    unsafe_allow_html=True,
)

# ── Course Tools (top) ─────────────────────────────────────────────────────
st.markdown('<div class="sur-section">Course Tools</div>', unsafe_allow_html=True)

t1, t2, t3 = st.columns(3)

with t1:
    st.markdown(
        """
<div class="tool-card">
    <h3>① Civil 3D Template</h3>
    <p>SUR4463_TEMPLATE.dwg — start every project here</p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.link_button("Download Template", TEMPLATE_URL, use_container_width=True, type="primary")

with t2:
    st.markdown(
        """
<div class="tool-card">
    <h3>② Parcel Clipper</h3>
    <p>Clip county parcel GIS to your AOI → Parcel_Clipped.zip</p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.page_link("pages/2_Parcel_Clipper.py", label="Open Parcel Clipper →", use_container_width=True)

with t3:
    st.markdown(
        """
<div class="tool-card">
    <h3>③ Existing Ground</h3>
    <p>Auto-fetch USGS DEM → EG.asc for Civil 3D</p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.page_link("pages/1_Existing_Ground.py", label="Open Existing Ground →", use_container_width=True)

# ── Video Series (bottom) ──────────────────────────────────────────────────
st.markdown('<div class="sur-section">Video Series</div>', unsafe_allow_html=True)

SERIES = [
    {"num": "▶", "title": "Full Playlist", "desc": "All SUR4463 walkthrough videos", "url": PLAYLIST_URL},
    {"num": "01", "title": "Site Data Prep", "desc": "Template, parcels & existing ground", "url": "https://youtu.be/bcakViVi-rU"},
    {"num": "02", "title": "Civil 3D Setup", "desc": "Import data & build project base", "url": PLAYLIST_URL},
    {"num": "03", "title": "Surface Import", "desc": "MAPIMPORT, surfaces & boundaries", "url": PLAYLIST_URL},
]
THUMB = "https://img.youtube.com/vi/bcakViVi-rU/mqdefault.jpg"

cols = st.columns(len(SERIES))
for col, item in zip(cols, SERIES):
    with col:
        st.markdown(
            f"""
<a href="{item['url']}" target="_blank" style="text-decoration:none;">
<div class="series-card">
    <img src="{THUMB}" alt="{item['title']}"/>
    <div class="series-card-body">
        <h4>{item['num']} · {item['title']}</h4>
        <p>{item['desc']}</p>
    </div>
</div>
</a>
""",
            unsafe_allow_html=True,
        )

st.link_button("Watch full series on YouTube →", PLAYLIST_URL)

st.markdown("</div>", unsafe_allow_html=True)
render_footer()
