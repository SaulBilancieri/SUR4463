"""Shared SUR4463 hub styling and layout."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

FAU_BLUE = "#003366"
FAU_BLUE_DARK = "#002244"
WHITE = "#ffffff"
TEXT = "#1a1a1a"
MUTED = "#5a6472"
BANNER = Path(__file__).parent / "assets" / "fau_banner.png"
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLG1N9qRhpQYplnzd9aX9YVPsJOH-MGcTH"
TEMPLATE_URL = "https://drive.google.com/uc?export=download&id=1HlREbLoVuiaO4gEoOU7bPT9ZTuf6P14e"
PAGE_PAD = "2rem"

INFO_HUB = """
### About this hub
Course tools for **SUR4463 — Subdivision Design** at FAU. Replaces the Google Colab
workflow with one-click web tools.

### Workflow
1. **Download Template** — open in Civil 3D
2. **Parcel Clipper** — clip county GIS to your AOI
3. **Existing Ground** — auto-fetch DEM → `EG.asc`
4. Import everything in Civil 3D (see video series)

### Data sources
- [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) — elevation (Existing Ground tool)
- [USGS National Map](https://elevation.nationalmap.gov/) — DEM ImageServer fallback
- County / Property Appraiser GIS — parcel data (you provide)
- [GeoJSON.io](https://geojson.io) — draw your AOI

### Resources
- [YouTube Playlist](https://www.youtube.com/playlist?list=PLG1N9qRhpQYplnzd9aX9YVPsJOH-MGcTH)
- [Site Data Walkthrough](https://youtu.be/bcakViVi-rU)
- [Civil 3D Template (Google Drive)](https://drive.google.com/file/d/1HlREbLoVuiaO4gEoOU7bPT9ZTuf6P14e/view)

### Course
Florida Atlantic University · Civil, Environmental & Geomatics Engineering
"""

INFO_EXISTING_GROUND = """
### How it works
1. Upload **AOI GeoJSON** (draw in GeoJSON.io, ~100–300 ft beyond site)
2. Tool fetches **USGS 3DEP**, clips to your exact polygon shape
3. Download **EG.asc** → import in Civil 3D as Existing Ground surface

### Output
| | |
|---|---|
| File | `EG.asc` (Arc/Info ASCII Grid) |
| CRS | EPSG:2236 — NAD83 Florida East (ftUS) |
| Resolution | 1 US survey foot per cell |
| Elevations | Feet |
| Outside AOI | `-9999` (nodata) |

### Data sources
- [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) — 10 m / 30 m seamless DEM
- [3DEP ImageServer](https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer) — fallback
- Coastal gaps filled by interpolation from nearby land

### Civil 3D import
1. Surface → Create Surface → EG
2. Definition → Add → DEM Files → select `EG.asc`
3. Boundaries → add parcel outline

### Links
- [GeoJSON.io](https://geojson.io) — create AOI
- [Video walkthrough](https://youtu.be/bcakViVi-rU)
"""

INFO_PARCEL = """
### How it works
1. Upload **AOI GeoJSON**
2. Upload **parcel GIS** (.zip shapefile, .shp, .geojson, or .gpkg)
3. Download **Parcel_Clipped.zip** → import in Civil 3D with `MAPIMPORT`

### Where to get parcels
- County GIS / Open Data portal
- Property Appraiser website
- State GIS repositories

### Tips
- Draw AOI ~100–300 ft beyond your site in [GeoJSON.io](https://geojson.io)
- If parcels don't align in Civil 3D, use **`MAPCASSIGN`** to set the correct CRS
  (e.g. Pasco County → NAD83 HARN West Florida US Foot)

### Links
- [GeoJSON.io](https://geojson.io)
- [Video walkthrough](https://youtu.be/bcakViVi-rU)
"""


def inject_base_css(hide_sidebar: bool = True):
    hide = """
    [data-testid="stSidebar"], [data-testid="stSidebarNav"], [data-testid="collapsedControl"] {
        display: none !important;
    }
    """ if hide_sidebar else ""
    st.markdown(
        f"""
<style>
    {hide}
    .stApp, .main .block-container {{ background: {WHITE} !important; }}
    .main .block-container {{
        padding-top: 0 !important;
        padding-bottom: 0.5rem !important;
        max-width: 100% !important;
        padding-left: {PAGE_PAD} !important;
        padding-right: {PAGE_PAD} !important;
    }}
    #MainMenu, footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{ background: transparent; }}

    .sur-bleed {{
        margin-left: -{PAGE_PAD} !important;
        margin-right: -{PAGE_PAD} !important;
        padding-left: {PAGE_PAD} !important;
        padding-right: {PAGE_PAD} !important;
    }}

    .sur-topbar {{
        display: flex; align-items: center; justify-content: space-between;
        min-height: 2rem; margin-bottom: 0.15rem;
    }}
    .sur-topbar .stButton > button {{
        background: transparent !important; border: 1px solid #ccd6e0 !important;
        color: {FAU_BLUE} !important; font-size: 0.82rem !important;
        padding: 0.2rem 0.75rem !important; min-height: 2rem !important;
        border-radius: 6px !important;
    }}
    .sur-topbar .stButton > button:hover {{
        background: #eef3f8 !important; border-color: {FAU_BLUE} !important;
    }}

    .sur-header {{
        background: {FAU_BLUE};
        padding: 0.55rem {PAGE_PAD} 0.65rem;
    }}
    .sur-header img {{ max-height: 52px; width: auto; display: block; }}
    .sur-header h1 {{
        color: {WHITE}; font-size: 1.25rem; font-weight: 600;
        margin: 0.4rem 0 0; letter-spacing: 0.02em;
    }}
    .sur-header p {{
        color: #c8d6e5; font-size: 0.85rem; margin: 0.1rem 0 0;
    }}

    .sur-footer {{
        background: {FAU_BLUE_DARK};
        color: #b0c4d8;
        text-align: center;
        font-size: 0.75rem;
        padding: 0.55rem {PAGE_PAD};
        margin-top: 1.5rem;
    }}

    .sur-body {{ padding: 0.75rem 0 0.5rem; }}

    .sur-welcome {{
        color: {TEXT}; font-size: 0.95rem; line-height: 1.55;
        margin-bottom: 1rem;
    }}
    .sur-section {{
        color: {FAU_BLUE}; font-size: 0.72rem; font-weight: 700;
        letter-spacing: 0.12em; text-transform: uppercase;
        margin: 1.25rem 0 0.65rem; border-bottom: 2px solid {FAU_BLUE};
        padding-bottom: 0.3rem;
    }}

    .series-card {{
        background: {WHITE}; border: 1px solid #dde3ea;
        border-radius: 8px; overflow: hidden;
        height: 100%;
    }}
    .series-card:hover {{ box-shadow: 0 3px 12px rgba(0,51,102,0.1); }}
    .series-card img {{ width: 100%; display: block; aspect-ratio: 16/9; object-fit: cover; }}
    .series-card-body {{ padding: 0.55rem 0.75rem 0.7rem; }}
    .series-card-body h4 {{
        color: {FAU_BLUE}; font-size: 0.85rem; margin: 0 0 0.2rem; font-weight: 600;
    }}
    .series-card-body p {{ color: {MUTED}; font-size: 0.76rem; margin: 0; line-height: 1.35; }}

    .tool-card {{
        background: {WHITE}; border: 1px solid #dde3ea;
        border-radius: 8px; padding: 0.85rem 0.75rem 0.7rem;
        text-align: center; min-height: 88px;
    }}
    .tool-card h3 {{ color: {FAU_BLUE}; font-size: 0.95rem; margin: 0 0 0.2rem; }}
    .tool-card p {{ color: {MUTED}; font-size: 0.78rem; margin: 0; line-height: 1.35; }}

    .sur-step {{
        color: {MUTED}; font-size: 0.88rem; margin-bottom: 0.75rem; line-height: 1.5;
    }}
</style>
""",
        unsafe_allow_html=True,
    )


def _banner_html() -> str:
    if not BANNER.exists():
        return ""
    import base64

    b64 = base64.b64encode(BANNER.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{b64}" alt="FAU Civil Engineering"/>'


def render_top_bar(*, show_back: bool = False, info_markdown: str | None = None):
    """Nav row: back button (left) + info popover (right)."""
    left_w, mid_w, right_w = (1.4, 8, 0.6) if show_back else (10, 0.1, 0.6)
    c1, c2, c3 = st.columns([left_w, mid_w, right_w])
    with c1:
        if show_back and st.button("← Course Hub", key="btn_back_hub"):
            st.switch_page("Home.py")
    with c3:
        if info_markdown:
            with st.popover("ℹ️", use_container_width=True):
                st.markdown(info_markdown)


def render_header(subtitle: str = "Subdivision Design · SUR4463"):
    st.markdown(
        f"""
<div class="sur-header sur-bleed">
    {_banner_html()}
    <h1>Subdivision Design · SUR4463</h1>
    <p>{subtitle}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def render_footer():
    st.markdown(
        """
<div class="sur-footer sur-bleed">
    Florida Atlantic University · Department of Civil, Environmental &amp; Geomatics Engineering
    · SUR4463 Subdivision Design
</div>
""",
        unsafe_allow_html=True,
    )


def render_page_shell(
    subtitle: str,
    *,
    show_back: bool = False,
    info_markdown: str | None = None,
):
    """Standard page wrapper: CSS → top bar → header."""
    inject_base_css(hide_sidebar=True)
    render_top_bar(show_back=show_back, info_markdown=info_markdown)
    render_header(subtitle=subtitle)
    st.markdown('<div class="sur-body">', unsafe_allow_html=True)
