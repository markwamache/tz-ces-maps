import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import requests
import io
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="TZ CES Maps Generator",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Colors
COLOR_SURVEYED_STH = "#E600A0"      # EA Magenta
COLOR_SURVEYED_SCH = "#05545A"      # Kale Green
COLOR_NOT_SURVEYED = "#E8E8E8"      # Light Grey
COLOR_BORDERS = "#FFFFFF"            # White
COLOR_TITLE = "#1a1a1a"              # Dark Grey
COLOR_LEGEND_TEXT = "#222222"        # Dark Grey
COLOR_FOOTNOTE = "#444444"           # Medium Grey
COLOR_LABEL_OUTLINE = "#00000066"    # Black (semi-transparent)

# Typography
TITLE_FONT = "DejaVu Sans"
TITLE_SIZE = 34
TITLE_WEIGHT = "bold"

LABEL_FONT = "DejaVu Sans"
LABEL_SIZE = 15
LABEL_WEIGHT = "bold"

LEGEND_FONT = "DejaVu Sans"
LEGEND_SIZE = 20
LEGEND_WEIGHT = "bold"

FOOTNOTE_FONT = "DejaVu Sans"
FOOTNOTE_SIZE = 12
FOOTNOTE_STYLE = "italic"

# Figure dimensions (16:9 aspect ratio)
FIGURE_WIDTH = 19.2   # inches
FIGURE_HEIGHT = 10.8  # inches
DPI = 200

# Regional label position nudges (offset in degrees lon/lat)
LABEL_NUDGES = {
    "Kagera": (-0.20, 0.10),
    "Mara": (0.10, 0.00),
    "Mtwara": (0.00, 0.25),
    "Lindi": (0.15, 0.10),
    "Njombe": (0.00, -0.15),
    "Simiyu": (0.00, -0.10),
    "Shinyanga": (0.00, 0.10),
    "Katavi": (-0.10, 0.00),
    "Rukwa": (0.10, -0.10),
    "Mbeya": (0.00, -0.15),
}

# Natural Earth GeoJSON source
GEOJSON_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

@st.cache_resource
def fetch_tanzania_boundaries():
    """Fetch Tanzania boundaries from Natural Earth."""
    try:
        response = requests.get(GEOJSON_URL, timeout=10)
        response.raise_for_status()
        
        geojson_data = response.json()
        
        # Filter for Tanzania using adm0_a3 country code
        tanzania_features = [
            feature for feature in geojson_data['features']
            if feature['properties'].get('adm0_a3') == 'TZA'
        ]
        
        # Create GeoDataFrame
        #gdf = gpd.GeoDataFrame.from_features(tanzania_features)
        from shapely.geometry import shape
        records = []
        for feature in tanzania_features:
            row = feature["properties"].copy()
            row["geometry"] = shape(feature["geometry"])
            records.append(row)
        gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
        
        # Rename 'name' column to 'Region Name' for consistency
        if 'name' in gdf.columns:
            gdf = gdf.rename(columns={'name': 'Region Name'})
        
        return gdf
    except Exception as e:
        st.error(f"Error fetching boundaries: {str(e)}")
        return None


def merge_data(survey_df, gdf):
    """Merge survey data with geographic boundaries."""
    # Merge on Region Name
    merged = gdf.merge(
        survey_df,
        on="Region Name",
        how="left"
    )
    
    # Fill NaN survey indicators with 0 (not surveyed)
    sth_col = 'STH Surveyed (1=Yes, 0=No)'
    sch_col = 'SCH Surveyed (1=Yes, 0=No)'
    
    if sth_col in merged.columns:
        merged[sth_col] = merged[sth_col].fillna(0).astype(int)
    if sch_col in merged.columns:
        merged[sch_col] = merged[sch_col].fillna(0).astype(int)
    
    return merged


def count_surveyed(merged_gdf, intervention):
    """Count surveyed regions for an intervention."""
    col = f"{intervention} Surveyed (1=Yes, 0=No)"
    if col in merged_gdf.columns:
        return int(merged_gdf[col].sum())
    return 0


def get_label_position(geometry, region_name):
    """Get label position for a region, applying nudges if needed."""
    centroid = geometry.centroid
    lon, lat = centroid.x, centroid.y
    
    # Apply nudge if specified
    if region_name in LABEL_NUDGES:
        dlon, dlat = LABEL_NUDGES[region_name]
        lon += dlon
        lat += dlat
    
    return lon, lat


def create_map(merged_gdf, intervention_type):
    """Create and return a geographic reach map."""
    
    # Determine colors and title
    if intervention_type == "STH":
        surveyed_color = COLOR_SURVEYED_STH
        title_text = "STH Geographic Reach"
    else:  # SCH
        surveyed_color = COLOR_SURVEYED_SCH
        title_text = "SCH Geographic Reach"
    
    # Count surveyed regions
    surveyed_count = count_surveyed(merged_gdf, intervention_type)
    
    # Create figure and axis
    fig = plt.figure(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT), dpi=DPI)
    fig.patch.set_facecolor('white')
    
    # Create main axis for map (left side)
    ax_map = fig.add_axes([0.03, 0.095, 0.49, 0.85])
    ax_map.set_facecolor('white')
    
    # Get data bounds
    bounds = merged_gdf.total_bounds
    minx, miny, maxx, maxy = bounds
    
    # Add padding
    padding = 0.4
    minx -= padding
    maxy += padding
    maxx += padding
    miny -= padding
    
    ax_map.set_xlim(minx, maxx)
    ax_map.set_ylim(miny, maxy)
    ax_map.set_aspect('equal')
    
    # Remove axes
    ax_map.axis('off')
    
    # Draw all regions
    col_name = f"{intervention_type} Surveyed (1=Yes, 0=No)"
    
    for idx, row in merged_gdf.iterrows():
        # Determine color
        #if col_name in row and row[col_name] == 1:
        if row.get(col_name, 0) == 1:
            facecolor = surveyed_color
            is_surveyed = True
        else:
            facecolor = COLOR_NOT_SURVEYED
            is_surveyed = False
        
        # Draw region
        gpd.GeoSeries(row.geometry).plot(
            ax=ax_map,
            facecolor=facecolor,
            edgecolor=COLOR_BORDERS,
            linewidth=1.5
        )
        
        # Add label for surveyed regions
        if is_surveyed:
            region_name = row['Region Name']
            lon, lat = get_label_position(row.geometry, region_name)
            
            # Add text with outline for readability
            text = ax_map.text(
                lon, lat, region_name,
                fontsize=LABEL_SIZE,
                fontweight=LABEL_WEIGHT,
                fontfamily=LABEL_FONT,
                ha='center',
                va='center',
                color='white',
                zorder=10
            )
            
            # Add outline
            text.set_path_effects([
                pe.Stroke(linewidth=3.5, foreground=COLOR_LABEL_OUTLINE),
                pe.Normal()
            ])
    
    # Add title
    fig.text(
        (0.03 + (0.03 + 0.49)) / 2,
        0.95,
        title_text,
        fontsize=TITLE_SIZE,
        fontweight=TITLE_WEIGHT,
        fontfamily=TITLE_FONT,
        color=COLOR_TITLE,
        ha='center',
        va='top'
    )
    
    # Create legend with rectangle patches for color swatches
    import matplotlib.patches as mpatches
    
    legend_x = 0.52
    legend_y_top = 0.57
    legend_y_bottom = 0.38
    
    swatch_width = 0.04
    swatch_height = 0.055
    
    # Surveyed swatch
    surveyed_patch = mpatches.Rectangle(
        (legend_x, legend_y_top),
        swatch_width,
        swatch_height,
        facecolor=surveyed_color,
        edgecolor='#333333',
        linewidth=1.5,
        transform=fig.transFigure,
        clip_on=False,
        zorder=100
    )
    fig.patches.append(surveyed_patch)
    
    # Wrapped text for surveyed legend
    fig.text(
        legend_x + swatch_width + 0.03,
        legend_y_top + swatch_height / 2 + 0.015,
        "CES Surveyed",
        fontsize=LEGEND_SIZE,
        fontweight=LEGEND_WEIGHT,
        fontfamily=LEGEND_FONT,
        color=COLOR_LEGEND_TEXT,
        va='center'
    )
    fig.text(
        legend_x + swatch_width + 0.03,
        legend_y_top + swatch_height / 2 - 0.015,
        f"({surveyed_count} regions shown)",
        fontsize=LEGEND_SIZE - 2,
        fontweight=LEGEND_WEIGHT,
        fontfamily=LEGEND_FONT,
        color=COLOR_LEGEND_TEXT,
        va='center'
    )
    
    # Not surveyed swatch
    not_surveyed_patch = mpatches.Rectangle(
        (legend_x, legend_y_bottom),
        swatch_width,
        swatch_height,
        facecolor=COLOR_NOT_SURVEYED,
        edgecolor='#999999',
        linewidth=1.5,
        transform=fig.transFigure,
        clip_on=False,
        zorder=100
    )
    fig.patches.append(not_surveyed_patch)
    
    fig.text(
        legend_x + swatch_width + 0.03,
        legend_y_bottom + swatch_height / 2,
        "Not surveyed",
        fontsize=LEGEND_SIZE,
        fontweight=LEGEND_WEIGHT,
        fontfamily=LEGEND_FONT,
        color=COLOR_LEGEND_TEXT,
        va='center'
    )
    
    # Add footnote
    footnote_line1 = "Source: Evidence Action Coverage Evaluation Survey 2026 | Boundaries: Natural Earth admin-1"
    footnote_line2 = "Note: Songwe was surveyed but is not shown due to boundary data limitations."
    
    fig.text(
        0.5,
        0.03,
        f"{footnote_line1}\n{footnote_line2}",
        fontsize=FOOTNOTE_SIZE,
        fontstyle=FOOTNOTE_STYLE,
        fontfamily=FOOTNOTE_FONT,
        color=COLOR_FOOTNOTE,
        ha='center',
        va='bottom',
        linespacing=1.6
    )
    
    # Return figure as bytes
    img_bytes = io.BytesIO()
    plt.savefig(
        img_bytes,
        dpi=DPI,
        facecolor='white',
        edgecolor='none',
        bbox_inches='tight',
        pad_inches=0
    )
    plt.close(fig)
    img_bytes.seek(0)
    return img_bytes

# ============================================================================
# STREAMLIT APP
# ============================================================================

st.title("🗺️ TZ CES Maps Generator")
st.markdown("Generate professional geographic reach maps for Tanzania regional health surveys")

# Sidebar
with st.sidebar:
    st.header("About")
    st.markdown("""
    This app generates professional 16:9 PNG maps showing which Tanzania regions were surveyed for:
    - **STH** (Soil-Transmitted Helminth) interventions
    - **SCH** (Schistosomiasis) interventions
    
    **Features:**
    - 200 DPI resolution
    - Publication-ready quality
    - Automatic legend generation
    - Professional typography
    """)
    
    st.divider()
    st.header("File Format")
    st.markdown("""
    Your Excel file needs:
    - **Sheet:** `CES_Surveyed_Regions`
    - **Column 1:** `Region Name`
    - **Column 2:** `STH Surveyed (1=Yes, 0=No)`
    - **Column 3:** `SCH Surveyed (1=Yes, 0=No)`
    """)

# Main content
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📁 Upload Your Data")
    uploaded_file = st.file_uploader(
        "Choose an Excel file",
        type=['xlsx', 'xls'],
        help="Must contain 'CES_Surveyed_Regions' sheet"
    )

if uploaded_file is not None:
    try:
        # Read Excel file
        df = pd.read_excel(uploaded_file, sheet_name="CES_Surveyed_Regions")
        
        # Validate columns
        required_cols = ['Region Name', 'STH Surveyed (1=Yes, 0=No)', 'SCH Surveyed (1=Yes, 0=No)']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"❌ Missing columns: {', '.join(missing_cols)}")
        else:
            with st.spinner("🔄 Loading boundaries and generating maps..."):
                # Fetch boundaries
                gdf_bounds = fetch_tanzania_boundaries()
                
                if gdf_bounds is None:
                    st.error("Could not fetch geographic boundaries")
                else:
                    # Merge data
                    merged_gdf = merge_data(df, gdf_bounds)
                    
                    # Generate maps
                    sth_map = create_map(merged_gdf, "STH")
                    sch_map = create_map(merged_gdf, "SCH")
                    
                    # Display results
                    st.success("✅ Maps generated successfully!")
                    
                    st.divider()
                    
                    # Display maps
                    map_col1, map_col2 = st.columns(2)
                    
                    with map_col1:
                        st.subheader("STH Geographic Reach")
                        st.image(sth_map, use_column_width=True)
                        sth_count = count_surveyed(merged_gdf, "STH")
                        st.caption(f"📍 {sth_count} regions surveyed for STH")
                        
                        st.download_button(
                            label="⬇️ Download STH Map",
                            data=sth_map,
                            file_name="STH_Geographic_Reach.png",
                            mime="image/png",
                            use_container_width=True
                        )
                    
                    with map_col2:
                        st.subheader("SCH Geographic Reach")
                        st.image(sch_map, use_column_width=True)
                        sch_count = count_surveyed(merged_gdf, "SCH")
                        st.caption(f"📍 {sch_count} regions surveyed for SCH")
                        
                        st.download_button(
                            label="⬇️ Download SCH Map",
                            data=sch_map,
                            file_name="SCH_Geographic_Reach.png",
                            mime="image/png",
                            use_container_width=True
                        )
                    
                    st.divider()
                    
                    # Display data summary
                    st.subheader("📊 Data Summary")
                    
                    summary_col1, summary_col2, summary_col3 = st.columns(3)
                    
                    with summary_col1:
                        st.metric("Total Regions", len(df))
                    
                    with summary_col2:
                        st.metric("STH Surveyed", sth_count)
                    
                    with summary_col3:
                        st.metric("SCH Surveyed", sch_count)
                    
                    # Show data table
                    with st.expander("📋 View Detailed Data"):
                        display_df = df.copy()
                        display_df.columns = ['Region', 'STH', 'SCH']
                        display_df['STH'] = display_df['STH'].apply(lambda x: '✓ Yes' if x == 1 else '✗ No')
                        display_df['SCH'] = display_df['SCH'].apply(lambda x: '✓ Yes' if x == 1 else '✗ No')
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
        st.info("Make sure your Excel file has a sheet named 'CES_Surveyed_Regions' with the correct columns.")

else:
    st.info("👆 Upload an Excel file to get started")
    
    # Show example
    with st.expander("📝 See Example Data Format"):
        example_df = pd.DataFrame({
            'Region Name': ['Geita', 'Kagera', 'Katavi', 'Lindi', 'Mara'],
            'STH Surveyed (1=Yes, 0=No)': [0, 1, 1, 1, 1],
            'SCH Surveyed (1=Yes, 0=No)': [1, 1, 1, 1, 1]
        })
        st.dataframe(example_df, use_container_width=True, hide_index=True)
        st.caption("This is what your Excel file should look like")

st.divider()

# Footer
st.markdown("""
---
**Tanzania CES 2026 Geographic Reach Maps** | Version 1.0  
Built with ❤️ using Streamlit | Maps generated at 200 DPI in 16:9 format
""")
