
from html import escape

import requests
import pandas as pd
import streamlit as st

from config import (
    CAMPUSES,
    DEFAULT_CAMPUS,
    CAMPUS_SEARCH_PROFILES,
    DEFAULT_SEARCH_PROFILE
)

# ============================================================
# IMPORT PROJECT MODULES
# ============================================================

# Google Places API
from services.google_places import (
    fetch_google_stations,
    STATION_COLUMNS,
)

# Data cleaning
from processing.cleaning import (
    clean_station_data,
    summarize_data_quality,
)

# Data filtering and recommendations
from processing.filtering import (
    filter_eligible_stations,
    get_best_station,
    get_cheapest_stations,
    summarize_stations,
)

# Interactive map
from ui.map import (
    get_selected_radius,
    render_map,
)

# Charts
from ui.charts import render_price_charts


# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="What is the best gas station to fill up near campus?",
    page_icon="⛽",
    layout="wide",
)

# Available campuses
available_campuses = [
    name
    for name, location in CAMPUSES.items()
    if location["lat"] is not None
    and location["lon"] is not None
]

# Campus selection
st.sidebar.header("Campus Selection")

selected_campus = st.sidebar.selectbox(
    "Select Campus",
    options=available_campuses,
    index=available_campuses.index(DEFAULT_CAMPUS),
    key="selected_campus",
)

# Selected campus coordinates
CAMPUS_LAT = CAMPUSES[selected_campus]["lat"]
CAMPUS_LON = CAMPUSES[selected_campus]["lon"]

# # Select the campus-specific search configuration
# selected_search_profile = CAMPUS_SEARCH_PROFILES.get(
#     selected_campus,
#     DEFAULT_SEARCH_PROFILE
# )

default_search_profile = CAMPUS_SEARCH_PROFILES.get(
    selected_campus,
    DEFAULT_SEARCH_PROFILE
)

selected_search_profile = default_search_profile

# Temporary developer testing controls
with st.sidebar.expander(
    "Developer Settings",
    expanded=False
):

    override_search_profile = st.checkbox(
        "Override default search profile",
        value=False
    )

    if override_search_profile:

        profile_options = [
            "sparse",
            "standard",
            "dense"
        ]

        selected_search_profile = st.selectbox(
            "Search Profile",
            options=profile_options,
            index=profile_options.index(
                default_search_profile
            ),
            key=f"search_profile_{selected_campus}"
        )

    st.caption(
        f"Active search profile: "
        f"{selected_search_profile.title()}"
    )

# ============================================================
# 2. DASHBOARD HEADER
# ============================================================

# Dashboard header styling
st.markdown(
    """
    <style>
      h1.story-title {
        color: #102A43;
        font-size: clamp(2.25rem, 5.8vw, 5rem);
        line-height: 1.05;
        letter-spacing: -0.04em;
        margin: 0 0 0.9rem 0;
        max-width: 1100px;
      }
      .story-accent {
        width: 64px;
        height: 4px;
        border-radius: 999px;
        background: linear-gradient(90deg, #2563eb 0%, #38bdf8 100%);
        margin-bottom: 1.35rem;
      }
      @media (max-width: 480px) {
        h1.story-title {
          font-size: clamp(26px, 8vw, 38px);
          line-height: 1.1;
          letter-spacing: -0.03em;
          max-width: 100%;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# Dynamic dashboard title
st.markdown(
    f"""
    <h1 class="story-title">
        What is the best gas station to fill up near
        {escape(selected_campus)} Campus?
    </h1>
    <div class="story-accent"></div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. SIDEBAR - DATA CONTROLS
# ============================================================

st.sidebar.header("Google Places Data")

st.sidebar.caption(
    f"Search location: GSU {selected_campus} Campus"
)

# Initialize campus-specific session storage
if "campus_data" not in st.session_state:
    st.session_state["campus_data"] = {}

preview_mode = st.sidebar.toggle(
    "Design preview (no live data)",
    value=False,
)

refresh_requested = st.sidebar.button(
    "Get Latest Gas Prices",
    type="primary",
    disabled=preview_mode,
)


# ============================================================
# 4. GOOGLE PLACES DATA RETRIEVAL
# ============================================================

# API requests ONLY happen when the refresh button
# is clicked.
#
# Adjusting the radius, price age, or other controls
# does not trigger additional Google Places requests.

if refresh_requested:

    try:

        with st.spinner("Retrieving gas station data..."):

            api_key = st.secrets["GOOGLE_PLACES_API_KEY"]

            station_data, search_metadata = (
                fetch_google_stations(
                    api_key=api_key,
                    campus_lat=CAMPUS_LAT,
                    campus_lon=CAMPUS_LON,
                    search_profile=selected_search_profile
                )
            )

            # Store retrieved data for the selected campus
            st.session_state["campus_data"][selected_campus] = {
                "station_data": station_data,
                "search_metadata": search_metadata,
                "retrieved_at": pd.Timestamp.now(tz="UTC"),
            }

        st.sidebar.success(
            "Gas station data retrieved!"
        )

    except requests.RequestException as error:

        st.sidebar.error(
            f"Google Places request failed: {error}"
        )

    except KeyError:

        st.sidebar.error(
            "Google Places API key not found. "
            "Check .streamlit/secrets.toml."
        )

    except ValueError as error:

        st.sidebar.error(
            f"Google Places data error: {error}"
        )

# Retrieve stored data for the selected campus
campus_record = st.session_state["campus_data"].get(
    selected_campus,
    {},
)

raw_data = campus_record.get("station_data")

search_metadata = campus_record.get("search_metadata")

retrieved_at = campus_record.get("retrieved_at")

if retrieved_at is not None and not preview_mode:

    local_time = retrieved_at.tz_convert(
        "America/New_York"
    )

    st.sidebar.caption(
        f"{selected_campus} Campus data retrieved: "
        f"{local_time:%b %d, %Y at %I:%M %p %Z}"
    )

elif not preview_mode:

    st.sidebar.info(
        f"No data retrieved for {selected_campus} "
        "Campus. Click Get Latest Gas Prices."
    )


# ============================================================
# 5. API SEARCH INFORMATION
# ============================================================

if search_metadata is not None and not preview_mode:

    unique_listings = search_metadata.get(
        "unique_listings",
        0,
    )

    capped_searches = search_metadata.get(
        "capped_searches",
        0,
    )

    requests_made = search_metadata.get(
        "requests_made",
        0,
    )

    st.sidebar.info(
        f"Considered {unique_listings} gas station "
        f"listings within 3 miles of "
        f"{selected_campus} Campus."
    )

    if capped_searches > 0:

        st.sidebar.warning(
            f"{capped_searches} searches reached "
            "Google's 20-result limit."
        )

    st.sidebar.caption(
        f"Google Places requests in last fetch: "
        f"{requests_made}"
    )
    
    
    # ----------------------------------------------
    # SEARCH AND CLEANING DIAGNOSTICS
    # ----------------------------------------------

    with st.sidebar.expander(
        "Search & Cleaning Diagnostics",
        expanded=False
    ):

        # API retrieval metrics
        st.markdown("**API Retrieval**")
              
        st.write(
            "Search profile:",
            search_metadata.get(
                "search_profile",
                "N/A"
            ).title()
        )

        grid_size = search_metadata.get(
            "search_grid_size"
        )

        if grid_size is not None:

            st.write(
                f"Search grid: {grid_size} × {grid_size}"
            )

        st.write(
            "Search circle radius (miles):",
            search_metadata.get(
                "search_circle_radius",
                "N/A"
            )
        )

        st.write(
            "API requests:",
            search_metadata.get("requests_made", "N/A")
        )

        st.write(
            "Searches reaching limit:",
            search_metadata.get("capped_searches", "N/A")
        )

        st.write(
            "Raw API records:",
            search_metadata.get("raw_results", "N/A")
        )

        st.write(
            "Unique Google Place IDs:",
            search_metadata.get("unique_google_ids", "N/A")
        )
        
        st.divider()

        # Data cleaning metrics
        st.markdown("**Data Cleaning**")

        st.write(
            "Missing Place IDs:",
            search_metadata.get("missing_place_ids", "N/A")
        )

        st.write(
            "Repeated Place IDs removed:",
            search_metadata.get("repeated_place_ids", "N/A")
        )

        st.write(
            "Closed businesses removed:",
            search_metadata.get("closed_businesses_removed", "N/A")
        )

        st.write(
            "Colocated duplicates removed:",
            search_metadata.get("colocated_duplicates_removed", "N/A")
        )

        st.write(
            "Unverified listings removed:",
            search_metadata.get("unverified_listings_removed", "N/A")
        )

        st.write(
            "Invalid locations removed:",
            search_metadata.get("invalid_locations_removed", "N/A")
        )

        st.write(
            "Outside maximum radius:",
            search_metadata.get("outside_radius_removed", "N/A")
        )

        st.divider()

        # Final retrieval results
        st.markdown("**Final Results**")

        st.write(
            "Retained station listings:",
            search_metadata.get("unique_listings", "N/A")
        )

        st.write(
            "Stations with regular prices:",
            search_metadata.get("stations_with_prices", "N/A")
        )

        st.write(
            "Stations without regular prices:",
            search_metadata.get("stations_without_prices", "N/A")
        )

        # Data integrity check
        difference = search_metadata.get(
            "reconciliation_difference"
        )

        if difference == 0:

            st.success("Record counts reconciled.")

        elif difference is not None:

            st.warning(
                f"Record count discrepancy: {difference}"
            )

        else:

            st.caption(
                "Refresh data to obtain reconciliation results."
            )
            
        st.divider()

        st.markdown("**Individual Search Areas**")

        search_details = search_metadata.get(
            "search_details",
            []
        )

        if search_details:

            search_df = pd.DataFrame(search_details)

            search_df.index = range(
                1,
                len(search_df) + 1
            )

            search_df.index.name = "Search"

            search_df = search_df.rename(
                columns={
                    "north_offset": "North Offset",
                    "east_offset": "East Offset",
                    "radius_miles": "Radius",
                    "returned": "Results",
                    "hit_cap": "Capped"
                }
            )

            st.dataframe(
                search_df,
                width="stretch"
            )


# ============================================================
# 6. LOAD AND CLEAN DATA
# ============================================================

data_loaded = (
    not preview_mode
    and isinstance(raw_data, pd.DataFrame)
    and not raw_data.empty
)

if data_loaded:

    # Clean the stored station data.
    #
    # Price ages are recalculated using the current
    # time without making another API request.

    df = clean_station_data(
        raw_data
    )

else:

    # Empty dataframe for design preview.
    df = clean_station_data(
        pd.DataFrame(columns=STATION_COLUMNS)
    )


# ============================================================
# 7. DATA QUALITY SUMMARY
# ============================================================

if data_loaded:

    quality = summarize_data_quality(df)

    with st.sidebar.expander("Data Quality"):

        st.write(
            "Total listings:",
            quality["total_listings"],
        )

        st.write(
            "Listings with prices:",
            quality["listings_with_prices"],
        )

        st.write(
            "Missing prices:",
            quality["missing_prices"],
        )

        st.write(
            "Missing timestamps:",
            quality["missing_timestamps"],
        )

        st.write(
            "Listings at shared addresses:",
            quality["shared_address_listings"],
        )

        st.write(
            "Unique brands:",
            quality["unique_brands"],
        )


# ============================================================
# 8. SEARCH PREFERENCES
# ============================================================

st.sidebar.header("Search Preferences")

# Read the radius from our custom map component.
radius = get_selected_radius()

st.sidebar.caption(
    f"Selected radius: {radius:.2f} miles"
)

st.sidebar.caption(
    "Adjust the radius using the slider above the map."
)

max_age = st.sidebar.slider(
    "Maximum time since update (hours)",
    min_value=12,
    max_value=72,
    value=48,
    step=12,
)

st.caption(
    "Station and fuel price data: Google Maps. "
    "Distances are straight-line estimates."
)


# ============================================================
# 9. FILTER STATIONS
# ============================================================

if data_loaded:

    # Filter stations by:
    # - Selected radius
    # - Available regular gas price
    # - Maximum acceptable price age

    filtered = filter_eligible_stations(
        df=df,
        radius=radius,
        max_age=max_age,
    )

    # Calculate the dashboard overview.
    overview = summarize_stations(
        df=df,
        eligible_df=filtered,
        radius=radius,
    )

else:

    filtered = df.copy()
    overview = None


# ============================================================
# 10. DASHBOARD OVERVIEW
# ============================================================

st.markdown(
    """
    <style>
      .overview-heading {
        color: #64748b;
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        margin: 0.45rem 0 1.35rem 0;
      }
      .overview-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 1.25rem;
        margin-bottom: 1.35rem;
      }
      .overview-stat {
        min-height: 150px;
        background: #ffffff;
        border: 1px solid #edf2f7;
        border-radius: 14px;
        padding: 1.15rem 1.25rem 1rem 1.25rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.035);
      }
      .overview-value {
        color: #171717;
        font-size: clamp(2.75rem, 4vw, 4rem);
        font-weight: 800;
        line-height: 0.95;
        letter-spacing: -0.055em;
        margin-bottom: 1.05rem;
        white-space: nowrap;
      }
      .overview-label {
        color: #64748b;
        font-size: clamp(1.25rem, 1.8vw, 1.5rem);
        line-height: 1.2;
      }
      .overview-callout {
        border-left: 7px solid #2563eb;
        background: linear-gradient(90deg, #eff6ff 0%, #ffffff 100%);
        border-radius: 4px;
        color: #111827;
        font-size: clamp(1.25rem, 1.8vw, 1.5rem);
        line-height: 1.45;
        padding: 0.95rem 1.25rem;
        margin: 0 0 1.35rem 0;
      }
      .overview-callout strong {
        font-weight: 800;
      }
      @media (max-width: 800px) {
        .overview-grid {
          grid-template-columns: 1fr;
        }
      }
    </style>
    <div class="overview-heading">Overview</div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)

if data_loaded:

    stations_found = overview["stations_found"]

    eligible_count = overview["eligible_count"]

    lowest_price = overview["lowest_price"]

    if lowest_price is not None:

        cheapest_price = f"${lowest_price:.2f}/gal"

    else:

        cheapest_price = "—"

else:

    stations_found = "—"
    eligible_count = "—"
    lowest_price = None
    cheapest_price = "—"


if lowest_price is not None:
    lowest_display = f"${lowest_price:.2f}"
else:
    lowest_display = "—"

st.markdown(
    '<div class="overview-grid">'
    f'<div class="overview-stat"><div class="overview-value">{stations_found}</div>'
    '<div class="overview-label">Stations within radius</div></div>'
    f'<div class="overview-stat"><div class="overview-value">{eligible_count}</div>'
    '<div class="overview-label">With an eligible price</div></div>'
    f'<div class="overview-stat"><div class="overview-value">{lowest_display}</div>'
    '<div class="overview-label">Lowest gas price</div></div>'
    "</div>",
    unsafe_allow_html=True,
)

if data_loaded and not filtered.empty:
    best_station = get_best_station(filtered)
    cheapest_stations = get_cheapest_stations(filtered)

    st.markdown(
        '<div class="overview-callout">'
        "<strong>Closest station with the lowest price:</strong> "
        f"{best_station['Station']} "
        f"({best_station['Brand']}), "
        f"${best_station['Regular Price']:.2f}/gal, "
        f"{best_station['Distance (miles)']:.2f} miles away."
        "</div>",
        unsafe_allow_html=True,
    )

elif not data_loaded:
    st.markdown(
        '<div class="overview-callout">'
        "<strong>Best station:</strong> "
        "Load gas station data to see the closest lowest-priced option."
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# 12. DETOUR VALUE CALCULATOR
# ============================================================

st.markdown(
    """
    <style>
      .decision-eyebrow {
        color: #2563eb;
        font-size: 0.95rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin: 1.9rem 0 0.35rem 0;
      }
      .decision-title {
        color: #102a43;
        font-size: clamp(2rem, 3vw, 3rem);
        line-height: 1.08;
        letter-spacing: -0.03em;
        margin: 0 0 0.45rem 0;
      }
      .decision-description {
        color: #64748b;
        font-size: 1.12rem;
        line-height: 1.45;
        max-width: 760px;
        margin: 0 0 1.1rem 0;
      }
      .detour-metrics {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 1rem;
        margin: 1rem 0;
      }
      .detour-metric {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-radius: 14px;
        padding: 1rem 1.15rem;
      }
      .detour-metric-label {
        color: #2563eb;
        font-size: 0.9rem;
        font-weight: 800;
        margin-bottom: 0.35rem;
      }
      .detour-metric-value {
        color: #102a43;
        font-size: clamp(1.7rem, 2.5vw, 2.4rem);
        font-weight: 800;
        line-height: 1.1;
      }
      .detour-verdict {
        border-left: 7px solid #16a34a;
        background: #f0fdf4;
        border-radius: 8px;
        color: #14532d;
        font-size: 1.15rem;
        line-height: 1.5;
        padding: 1rem 1.2rem;
      }
      .detour-verdict.not-worth {
        border-left-color: #ea580c;
        background: #fff7ed;
        color: #9a3412;
      }
      .detour-footnote {
        color: #64748b;
        font-size: 0.92rem;
        margin-top: 0.65rem;
      }
      @media (max-width: 800px) {
        .detour-metrics {
          grid-template-columns: 1fr;
        }
      }
    </style>
    <div class="decision-eyebrow">Make the call</div>
    <h2 class="decision-title">Is the detour worth it?</h2>
    <p class="decision-description">
      Compare fuel savings at the pump with the extra fuel needed to reach
      the cheapest eligible station.
    </p>
    """,
    unsafe_allow_html=True,
)

gallons_col, efficiency_col = st.columns(2)

with gallons_col:
    gallons_per_fill = st.number_input(
        "Gallons per fill-up",
        min_value=1.0,
        max_value=50.0,
        value=12.0,
        step=1.0,
        format="%.0f",
        key="detour_gallons",
    )

with efficiency_col:
    car_efficiency = st.number_input(
        "Car efficiency (mpg)",
        min_value=1.0,
        max_value=100.0,
        value=25.0,
        step=1.0,
        format="%.0f",
        key="detour_efficiency",
    )

if not data_loaded:
    st.info("Load station data to calculate whether a lower price is worth the detour.")

elif filtered.empty:
    st.info("No stations with eligible prices are available in the selected radius.")

else:
    best_station = get_best_station(filtered)
    nearest_station = filtered.sort_values(
        "Distance (miles)"
    ).iloc[0]

    nearest_price = float(nearest_station["Regular Price"])
    best_price = float(best_station["Regular Price"])
    nearest_distance = float(nearest_station["Distance (miles)"])
    best_distance = float(best_station["Distance (miles)"])

    pump_savings = max(
        0.0,
        (nearest_price - best_price) * gallons_per_fill,
    )
    extra_round_trip_miles = max(
        0.0,
        (best_distance - nearest_distance) * 2,
    )
    extra_fuel_cost = (
        extra_round_trip_miles
        / car_efficiency
        * best_price
    )
    net_savings = pump_savings - extra_fuel_cost

    st.markdown(
        '<div class="detour-metrics">'
        '<div class="detour-metric"><div class="detour-metric-label">'
        "Savings at the pump</div>"
        f'<div class="detour-metric-value">${pump_savings:.2f}</div></div>'
        '<div class="detour-metric"><div class="detour-metric-label">'
        "Extra fuel for the detour</div>"
        f'<div class="detour-metric-value">${extra_fuel_cost:.2f}</div></div>'
        '<div class="detour-metric"><div class="detour-metric-label">'
        "Net savings</div>"
        f'<div class="detour-metric-value">${net_savings:.2f}</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    nearest_name = escape(str(nearest_station["Brand"]))
    best_name = escape(str(best_station["Brand"]))

    if extra_round_trip_miles == 0:
        verdict = (
            f"<strong>{best_name}</strong> is the closest eligible "
            "station with the lowest price, so no detour is needed."
        )
        verdict_class = "detour-verdict"
    elif net_savings >= 0:
        verdict = (
            f"Compared with the nearest eligible station, "
            f"<strong>{nearest_name}</strong> "
            f"({nearest_distance:.2f} mi, ${nearest_price:.2f}/gal), "
            f"<strong>{best_name}</strong> saves "
            f"<strong>${pump_savings:.2f}</strong> on "
            f"{gallons_per_fill:.0f} gallons. The extra estimated "
            f"{extra_round_trip_miles:.2f} round-trip miles cost about "
            f"${extra_fuel_cost:.2f} in fuel, leaving "
            f"<strong>${net_savings:.2f} net savings</strong>—the "
            "detour pays off."
        )
        verdict_class = "detour-verdict"
    else:
        verdict = (
            f"The lower pump price saves ${pump_savings:.2f}, but the "
            f"estimated detour fuel costs ${extra_fuel_cost:.2f}. "
            f"That is about ${abs(net_savings):.2f} more overall, so "
            "the detour does not pay off for this fill-up."
        )
        verdict_class = "detour-verdict not-worth"

    st.markdown(
        f'<div class="{verdict_class}">{verdict}</div>'
        '<div class="detour-footnote">Detour distance is estimated as '
        "twice the difference in straight-line distances; fuel cost uses "
        "the cheapest station's listed price.</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# 13. GAS PRICE VISUALIZATIONS
# ============================================================

# All chart creation and formatting now happens
# inside ui/charts.py.
#
# This includes:
# - Individual station price comparison
# - Price vs. distance
# - Average price by brand
#
# Duplicate station names are handled by charts.py.

render_price_charts(
    eligible_df=filtered
)



# ============================================================
# 14. INTERACTIVE GAS STATION MAP
# ============================================================

# Map section styling
st.markdown(
    """
    <style>
      .map-section-eyebrow {
        color: #2563eb;
        font-size: 0.95rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin: 1.9rem 0 0.35rem 0;
      }
      .map-section-title {
        color: #102a43;
        font-size: clamp(2rem, 3vw, 3rem);
        line-height: 1.08;
        letter-spacing: -0.03em;
        margin: 0 0 0.45rem 0;
      }
      .map-section-description {
        color: #64748b;
        font-size: 1.12rem;
        line-height: 1.45;
        max-width: 760px;
        margin: 0 0 1.1rem 0;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# Dynamic map heading
st.markdown(
    f"""
    <div class="map-section-eyebrow">
        Explore the area
    </div>

    <h2 class="map-section-title">
        Gas Stations Near {escape(selected_campus)} Campus
    </h2>

    <p class="map-section-description">
        Adjust the search radius and compare eligible
        stations around {escape(selected_campus)} Campus.
    </p>
    """,
    unsafe_allow_html=True,
)

# The map and smooth radius slider are managed
# by ui/map.py and the assets/ folder.
#
# Moving the slider locally filters the station
# data without requesting new Google Places data.

# Render interactive map
render_map(
    df=df,
    radius=radius,
    max_age=max_age,
    data_loaded=data_loaded,
    campus_lat=CAMPUS_LAT,
    campus_lon=CAMPUS_LON,
    campus_name=selected_campus,
)


# ============================================================
# 15. AVAILABLE GAS STATIONS TABLE
# ============================================================

st.markdown(
    """
    <style>
      .table-section-eyebrow {
        color: #2563eb;
        font-size: 0.95rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin: 1.9rem 0 0.35rem 0;
      }
      .table-section-title {
        color: #102a43;
        font-size: clamp(2rem, 3vw, 3rem);
        line-height: 1.08;
        letter-spacing: -0.03em;
        margin: 0 0 0.45rem 0;
      }
      .table-section-description {
        color: #64748b;
        font-size: 1.12rem;
        line-height: 1.45;
        max-width: 760px;
        margin: 0 0 1.1rem 0;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# Dynamic table heading
st.markdown(
    f"""
    <h2 class="table-section-title">
        Available Gas Stations Near
        {escape(selected_campus)} Campus
    </h2>

    <p class="table-section-description">
        Review station details, regular gas prices,
        and reported freshness for stations near
        {escape(selected_campus)} Campus.
    </p>
    """,
    unsafe_allow_html=True,
)

if filtered.empty:
    if data_loaded:
        st.info(
            "No eligible prices match the current radius and update window. "
            "Try expanding either setting."
        )
    else:
        st.info(
            "Load gas station data from the sidebar to see station prices here."
        )
else:
    # Identify the best station and all lowest-price stations.
    best_station = get_best_station(filtered)

    cheapest_stations = get_cheapest_stations(filtered)

    best_id = best_station["Place ID"]

    cheapest_ids = set(cheapest_stations["Place ID"])


    # Create a separate display dataframe.
    display_df = filtered.copy()


    def get_recommendation(row):

        if row["Place ID"] == best_id:
            return "★ Best Value"

        if row["Place ID"] in cheapest_ids:
            return "Lowest Price"

        return ""


    display_df["Recommendation"] = display_df.apply(
        get_recommendation,
        axis=1
    )


    # Highlight recommendation and price cells.
    def highlight_recommendation(row):

        if row["Place ID"] == best_id:

            style = (
                "background-color: #dcfce7; "
                "color: #166534; "
                "font-weight: 800;"
            )

        elif row["Place ID"] in cheapest_ids:

            style = (
                "background-color: #ccfbf1; "
                "color: #115e59; "
                "font-weight: 700;"
            )

        else:

            style = "color: #1d4ed8; font-weight: 700;"

        return [
            style if col in ["Regular Price", "Recommendation"]
            else ""
            for col in row.index
        ]

    table_styles = [
        {
            "selector": "thead th",
            "props": [
                ("background-color", "#2563eb"),
                ("color", "#ffffff"),
                ("font-weight", "800"),
                ("border-bottom", "2px solid #1d4ed8"),
                ("padding", "0.75rem"),
            ],
        },
        {
            "selector": "tbody tr:nth-child(even)",
            "props": [("background-color", "#eff6ff")],
        },
        {
            "selector": "tbody td",
            "props": [
                ("padding", "0.65rem 0.75rem"),
                ("border-bottom", "1px solid #dbeafe"),
            ],
        },
    ]

    styled_table = (
        display_df.style
        .set_table_styles(table_styles)
        .apply(highlight_recommendation, axis=1)
    )

    st.container(border=True).dataframe(
        styled_table,
        width="stretch",
        hide_index=True,
    )

    st.download_button(
        "Download filtered stations (CSV)",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name=(
            f"gsu_gas_stations_"
            f"{selected_campus.lower().replace(' ', '_')}_"
            f"{pd.Timestamp.now():%Y-%m-%d}.csv"
        ),
        mime="text/csv",
    )

st.caption(
    "Gas prices may not reflect prices currently "
    "posted at the pump. Verify prices before traveling."
)


