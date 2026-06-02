import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import requests
import io
from shapely.geometry import shape

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="TZ CES Maps Generator",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CONFIGURATION
# ============================================================================
COLOR_SURVEYED_STH = "#E600A0"
COLOR_SURVEYED_SCH = "#05545A"
COLOR_NOT_SURVEYED = "#E8E8E8"
COLOR_BORDERS = "#FFFFFF"
COLOR_TITLE = "#1a1a1a"
COLOR_LEGEND_TEXT = "#222222"
COLOR_FOOTNOTE = "#444444"
COLOR_LABEL_OUTLINE = "#00000066"

TITLE_SIZE = 34
LABEL_SIZE = 12
DPI = 200

GEOJSON_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson"

LABEL_NUDGES = {
    "Kagera": (-0.20, 0.10),
    "Mara": (0.10, 0.00),
    "Mtwara": (0.00, 0.25),
    "Lindi": (0.15, 0.10),
    "Njombe": (0.00, -0.15),
}

# ============================================================================
# LOAD BOUNDARIES (NO GEOPANDAS)
# ============================================================================
@st.cache_data
def load_tanzania():
    r = requests.get(GEOJSON_URL, timeout=20)
    data = r.json()

    regions = []
    for f in data["features"]:
        if f["properties"].get("adm0_a3") == "TZA":
            geom = shape(f["geometry"])
            props = f["properties"]
            props["geometry"] = geom
            regions.append(props)

    return regions


# ============================================================================
# HELPERS
# ============================================================================
def get_col(df, col):
    return df[col].fillna(0).astype(int)


def surveyed_count(df, col):
    return int(df[col].sum())


def label_position(geom, name):
    c = geom.centroid
    lon, lat = c.x, c.y

    if name in LABEL_NUDGES:
        dx, dy = LABEL_NUDGES[name]
        lon += dx
        lat += dy

    return lon, lat


# ============================================================================
# MAP FUNCTION
# ============================================================================
def create_map(regions, df, col, title, color):

    fig = plt.figure(figsize=(19.2, 10.8), dpi=DPI)
    ax = fig.add_axes([0.03, 0.08, 0.55, 0.85])
    ax.axis("off")

    # bounds
    all_geoms = [r["geometry"] for r in regions]
    minx = min(g.bounds[0] for g in all_geoms)
    miny = min(g.bounds[1] for g in all_geoms)
    maxx = max(g.bounds[2] for g in all_geoms)
    maxy = max(g.bounds[3] for g in all_geoms)

    pad = 0.5
    ax.set_xlim(minx - pad, maxx + pad)
    ax.set_ylim(miny - pad, maxy + pad)

    lookup = df.set_index("Region Name")[col].to_dict()

    surveyed = 0

    for r in regions:
        name = r["name"]
        geom = r["geometry"]
        val = lookup.get(name, 0)

        if val == 1:
            fc = color
            surveyed += 1
        else:
            fc = COLOR_NOT_SURVEYED

        # handle multipolygon safely
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)

        for poly in polys:
            x, y = poly.exterior.xy
            ax.fill(x, y, facecolor=fc, edgecolor=COLOR_BORDERS, linewidth=1)

        # labels
        if val == 1:
            lon, lat = label_position(geom, name)
            txt = ax.text(
                lon, lat, name,
                fontsize=LABEL_SIZE,
                ha="center",
                va="center",
                color="white",
                fontweight="bold"
            )
            txt.set_path_effects([
                pe.Stroke(linewidth=3, foreground=COLOR_LABEL_OUTLINE),
                pe.Normal()
            ])

    # title
    fig.text(
        0.5, 0.95,
        title,
        ha="center",
        fontsize=TITLE_SIZE,
        fontweight="bold",
        color=COLOR_TITLE
    )

    # legend
    fig.text(0.67, 0.60, f"CES Surveyed ({surveyed})", fontsize=14, fontweight="bold")
    fig.text(0.67, 0.56, "Not surveyed", fontsize=14)

    # export
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================================
# UI
# ============================================================================
st.title("🗺️ TZ CES Maps Generator")

uploaded = st.file_uploader("Upload Excel file", type=["xlsx"])

if uploaded:

    df = pd.read_excel(uploaded, sheet_name="CES_Surveyed_Regions")

    required = [
        "Region Name",
        "STH Surveyed (1=Yes, 0=No)",
        "SCH Surveyed (1=Yes, 0=No)"
    ]

    if any(c not in df.columns for c in required):
        st.error("Missing required columns")
        st.stop()

    with st.spinner("Loading map..."):
        regions = load_tanzania()

        sth_map = create_map(
            regions,
            df,
            "STH Surveyed (1=Yes, 0=No)",
            "STH Geographic Reach",
            COLOR_SURVEYED_STH
        )

        sch_map = create_map(
            regions,
            df,
            "SCH Surveyed (1=Yes, 0=No)",
            "SCH Geographic Reach",
            COLOR_SURVEYED_SCH
        )

    col1, col2 = st.columns(2)

    with col1:
        st.image(sth_map)
        st.download_button("Download STH Map", sth_map, "sth.png", "image/png")

    with col2:
        st.image(sch_map)
        st.download_button("Download SCH Map", sch_map, "sch.png", "image/png")

else:
    st.info("Upload an Excel file to generate maps.")