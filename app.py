
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
    page_title="GSU Gas Price Dashboard",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# 2. DASHBOARD HEADER
# ============================================================

st.markdown(
    """
    <style>
      .dashboard-title {
        color: #102a43;
        font-size: clamp(2.2rem, 4vw, 3.5rem);
        font-weight: 800;
        line-height: 1.1;
        letter-spacing: -0.04em;
        margin: 0 0 0.65rem 0;
      }

      .story-accent {
        width: 64px;
        height: 4px;
        border-radius: 999px;
        background: #2563eb;
        margin-bottom: 1.25rem;
      }

      .dashboard-question {
        color: #102a43;
        font-size: clamp(1.5rem, 2.5vw, 2.2rem);
        font-weight: 700;
        line-height: 1.2;
        letter-spacing: -0.025em;
        margin: 0 0 0.5rem 0;
      }

      .dashboard-description {
        color: #64748b;
        font-size: 1.1rem;
        line-height: 1.5;
        margin-bottom: 1rem;
      }
    </style>

    <h1 class="dashboard-title">
        GSU Gas Price Dashboard
    </h1>

    <div class="story-accent"></div>

    <h2 class="dashboard-question">
        What are the best gas stations to fill up
        near campus?
    </h2>

    <p class="dashboard-description">
        Find and compare nearby gas stations based
        on regular gas prices and distance from
        your campus.
    </p>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. PRIMARY DASHBOARD CONTROLS
# ============================================================

available_campuses = [
    name
    for name, location in CAMPUSES.items()
    if location["lat"] is not None
    and location["lon"] is not None
]

# Create a single row for the main controls.
campus_col, refresh_col, api_col = st.columns(
    [3, 2, 1.1],
    vertical_alignment="bottom",
    gap="small"
)

with campus_col:

    selected_campus = st.selectbox(
        "Select your campus",
        options=available_campuses,
        index=available_campuses.index(DEFAULT_CAMPUS),
        key="selected_campus",
    )


# Selected campus coordinates.
CAMPUS_LAT = CAMPUSES[selected_campus]["lat"]
CAMPUS_LON = CAMPUSES[selected_campus]["lon"]


# Initialize campus-specific session storage.
if "campus_data" not in st.session_state:

    st.session_state["campus_data"] = {}


# ============================================================
# DEVELOPER SETTINGS
# ============================================================

st.sidebar.header("Dashboard Debug")

st.sidebar.caption(
    "Technical diagnostics and development controls."
)

default_search_profile = CAMPUS_SEARCH_PROFILES.get(
    selected_campus,
    DEFAULT_SEARCH_PROFILE,
)

selected_search_profile = default_search_profile


with st.sidebar.expander(
    "Developer Settings",
    expanded=False,
):

    preview_mode = st.toggle(
        "Design preview (no live data)",
        value=False,
    )

    override_search_profile = st.checkbox(
        "Override default search profile",
        value=False,
    )

    if override_search_profile:

        profile_options = [
            "sparse",
            "standard",
            "dense",
        ]

        selected_search_profile = st.selectbox(
            "Search Profile",
            options=profile_options,
            index=profile_options.index(
                default_search_profile
            ),
            key=f"search_profile_{selected_campus}",
        )

    st.caption(
        f"Active search profile: "
        f"{selected_search_profile.title()}"
    )


# ============================================================
# GAS PRICE REFRESH BUTTON
# ============================================================


# ============================================================
# API KEY CONFIGURATION
# ============================================================

# Determine whether default keys are permitted.

use_default_places_key = st.secrets.get(
    "USE_DEFAULT_PLACES_KEY",
    False
)

use_default_maps_key = st.secrets.get(
    "USE_DEFAULT_MAPS_KEY",
    False
)


# Retrieve default keys only when permitted.

default_places_key = (
    st.secrets.get("GOOGLE_PLACES_API_KEY", "").strip()
    if use_default_places_key
    else ""
)

default_maps_key = (
    st.secrets.get("GOOGLE_MAPS_BROWSER_KEY", "").strip()
    if use_default_maps_key
    else ""
)


# ------------------------------------------------------------
# API CONFIGURATION POPOVER
# ------------------------------------------------------------

with api_col.popover(
    "🔑 API Configuration",
    width="stretch"
):

    # Google Places API

    visitor_places_key = st.text_input(
        "Google Places API Key",
        type="password",
        key="visitor_places_api_key",
        placeholder="Enter your Places API key"
    ).strip()

    st.caption(
        "Required to retrieve gas station "
        "information and fuel prices."
    )

    st.divider()

    # Google Maps JavaScript API

    visitor_maps_key = st.text_input(
        "Google Maps Browser API Key",
        type="password",
        key="visitor_maps_api_key",
        placeholder="Enter your Maps API key"
    ).strip()

    st.caption(
        "Required to display the interactive "
        "Google Map."
    )

    st.divider()

    # Determine which API keys to use.

    api_key = (
        visitor_places_key or default_places_key
    )

    maps_browser_key = (
        visitor_maps_key or default_maps_key
    )

    keys_ready = bool(
        api_key and maps_browser_key
    )

    # Configuration status

    if keys_ready:

        st.success("Both API keys are configured.")

    elif not api_key and not maps_browser_key:

        st.info("Both API keys are required.")

    elif not api_key:

        st.info("Google Places API key is required.")

    else:

        st.info("Google Maps API key is required.")

    st.caption(
        "Keys are used during your current session. "
        "API usage is billed to the associated "
        "Google Cloud project."
    )

    st.caption(
        "Use a dedicated, restricted API key. "
        "Reload the page before switching Maps keys."
    )

    st.markdown(
        "[Get a Places API key]"
        "(https://developers.google.com/maps/"
        "documentation/places/web-service/get-api-key)"
    )

    st.markdown(
        "[Get a Maps JavaScript API key]"
        "(https://developers.google.com/maps/"
        "documentation/javascript/get-api-key)"
    )



with refresh_col:

    refresh_requested = st.button(
        "Get Latest Gas Prices",
        type="primary",
        disabled=preview_mode or not keys_ready,
        width="stretch",
        help=(
            "Retrieve live gas prices."
            if keys_ready
            else
            "Enter both API keys in API Configuration."
        )
    )


# Reserve positions for the data status and map.
status_area = st.container()

# Side-by-side overview and interactive map.
overview_col, map_col = st.columns(
    [2, 3],
    gap="large",
    vertical_alignment="top",
)

overview_area = overview_col.container()

map_area = map_col.container()


# ============================================================
# 4. GOOGLE PLACES DATA RETRIEVAL
# ============================================================

# API requests ONLY happen when the refresh button
# is clicked.
#
# Adjusting the radius, price age, or other controls
# does not trigger additional Google Places requests.

if refresh_requested and keys_ready:

    try:

        with st.spinner("Retrieving gas station data..."):

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

    except requests.RequestException as error:

        status_area.error(
            f"Google Places request failed: {error}"
        )

    except KeyError:

        status_area.error(
            "Google Places API key not found. "
            "Check .streamlit/secrets.toml."
        )

    except ValueError as error:

        status_area.error(
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

if preview_mode:

    status_area.caption(
        "Design preview — live gas prices are not displayed."
    )

elif not keys_ready:

    status_area.info(
        "Enter both Google API keys under "
        "API Configuration to get started."
    )

elif retrieved_at is not None:

    local_time = retrieved_at.tz_convert(
        "America/New_York"
    )

    status_area.caption(
        f"{selected_campus} Campus · "
        f"Data retrieved {local_time:%b %d, %Y at %I:%M %p %Z}"
    )

else:

    status_area.info(
        f"Click Get Latest Gas Prices to explore "
        f"stations near {selected_campus} Campus."
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

# Read the radius from the custom map component.
radius = get_selected_radius()


# Secondary search preferences.
with st.popover("Price freshness"):

    max_age = st.slider(
        "Price updated within (hours)",
        min_value=12,
        max_value=72,
        value=48,
        step=12,
    )

    st.caption(
        "Only prices reported within this time "
        "window are eligible for recommendations."
    )


st.caption(
    f"Considering prices updated within {max_age} hours. "
    "Distances are straight-line estimates."
)


# ============================================================
# INTERACTIVE MAP AND RADIUS SLIDER
# ============================================================

# The map and smooth radius slider are managed
# by ui/map.py and the assets/ folder.
#
# Moving the slider locally filters the station
# data without requesting new Google Places data.


with map_area:

    if keys_ready:

        render_map(
            df=df,
            radius=radius,
            max_age=max_age,
            data_loaded=data_loaded,
            campus_lat=CAMPUS_LAT,
            campus_lon=CAMPUS_LON,
            campus_name=selected_campus,
            maps_browser_key=maps_browser_key
        )

    else:

        st.html("""
            <div style="
                min-height: 400px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                text-align: center;
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 24px;
                color: #64748b;
                box-sizing: border-box;
            ">

                <div style="font-size: 38px;">
                    🗺️
                </div>

                <div style="
                    font-size: 19px;
                    font-weight: 700;
                    color: #102a43;
                    margin: 12px 0 8px;
                ">
                    Interactive Gas Station Map
                </div>

                <div style="
                    font-size: 14px;
                    max-width: 320px;
                    line-height: 1.5;
                ">
                    Enter both Google API keys under
                    API Configuration to enable the
                    interactive map.
                </div>

            </div>
        """)



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

with overview_area:

    st.html(
        """
        <style>

          .overview-heading {
            color: #102a43;
            font-size: 1.75rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            margin-bottom: 1rem;
          }

          .best-value-card {
            background: #ffffff;
            border: 1px solid #bbf7d0;
            border-left: 5px solid #16a34a;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
          }

          .best-value-label {
            color: #166534;
            font-size: 0.9rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.75rem;
          }

          .best-value-price {
            color: #166534;
            font-size: clamp(2.5rem, 4vw, 4rem);
            font-weight: 800;
            line-height: 1.1;
            letter-spacing: -0.04em;
            margin-bottom: 0.75rem;
          }

          .best-value-unit {
            font-size: 1.1rem;
            font-weight: 600;
            letter-spacing: 0;
          }

          .best-value-name {
            color: #102a43;
            font-size: 1.4rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
          }

          .best-value-distance {
            color: #475569;
            font-size: 1.1rem;
            margin-bottom: 0.75rem;
          }

          .best-value-description {
            color: #64748b;
            font-size: 0.95rem;
            line-height: 1.5;
          }

          .best-value-empty {
            border-color: #e2e8f0;
          }

          .best-value-empty .best-value-label,
          .best-value-empty .best-value-price {
            color: #64748b;
          }

          .overview-grid {
            display: grid;
            grid-template-columns:
                repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin-bottom: 1rem;
          }

          .overview-stat {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 1rem;
          }

          .overview-value {
            color: #102a43;
            font-size: clamp(1.8rem, 3vw, 2.8rem);
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.5rem;
          }

          .overview-label {
            color: #64748b;
            font-size: 0.95rem;
            line-height: 1.3;
          }

        </style>

        <div class="overview-heading">
            Overview
        </div>
        """,
    )

    # ----------------------------------------------
    # PREPARE OVERVIEW METRICS
    # ----------------------------------------------

    if data_loaded:

        stations_found = overview["stations_found"]

        eligible_count = overview["eligible_count"]

    else:

        stations_found = "—"

        eligible_count = "—"


    # ----------------------------------------------
    # BEST VALUE RECOMMENDATION
    # ----------------------------------------------

    if data_loaded and not filtered.empty:

        best_station = get_best_station(filtered)

        best_name = escape(
            str(best_station["Station"])
        )

        best_price = float(
            best_station["Regular Price"]
        )

        best_distance = float(
            best_station["Distance (miles)"]
        )

        st.html(
            f"""
            <div class="best-value-card">

                <div class="best-value-label">
                    ★ Best Value
                </div>

                <div class="best-value-price">
                    ${best_price:.2f}
                    <span class="best-value-unit">
                        /gal
                    </span>
                </div>

                <div class="best-value-name">
                    {best_name}
                </div>

                <div class="best-value-distance">
                    {best_distance:.2f} miles from campus
                </div>

                <div class="best-value-description">
                    Closest station offering the
                    lowest eligible regular gas price.
                </div>

            </div>
            """,
        )

    else:

        if not data_loaded:

            message = (
                "Retrieve gas prices to find the "
                "best station near your campus."
            )

        else:

            message = (
                "No eligible prices match your "
                "current search preferences."
            )

        st.html(
            f"""
            <div class="best-value-card best-value-empty">

                <div class="best-value-label">
                    Best Value
                </div>

                <div class="best-value-price">
                    —
                </div>

                <div class="best-value-description">
                    {message}
                </div>

            </div>
            """,
        )


    # ----------------------------------------------
    # SUPPORTING OVERVIEW STATISTICS
    # ----------------------------------------------

    st.html(
        f"""
        <div class="overview-grid">

            <div class="overview-stat">

                <div class="overview-value">
                    {stations_found}
                </div>

                <div class="overview-label">
                    Stations within radius
                </div>

            </div>

            <div class="overview-stat">

                <div class="overview-value">
                    {eligible_count}
                </div>

                <div class="overview-label">
                    Stations with eligible prices
                </div>

            </div>

        </div>
        """,
    )

    st.caption(
        f"Considering gas prices reported within "
        f"the past {max_age} hours."
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
            "Click Get Latest Gas Prices above to compare nearby stations."
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

        if row["Recommendation"] == "★ Best Value":

            style = (
                "background-color: #dcfce7; "
                "color: #166534; "
                "font-weight: 800;"
            )

        elif row["Recommendation"] == "Lowest Price":

            style = (
                "background-color: #ccfbf1; "
                "color: #115e59; "
                "font-weight: 700;"
            )

        else:

            style = (
                "color: #1d4ed8; "
                "font-weight: 700;"
            )

        return [
            style if col in [
                "Regular Price",
                "Recommendation"
            ]
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

    # ----------------------------------------------
    # PREPARE USER-FACING TABLE
    # ----------------------------------------------

    display_df["Last Updated"] = pd.to_datetime(
        display_df["Last Updated"],
        utc=True,
        errors="coerce"
    ).dt.tz_convert("America/New_York")


    # Select and order the displayed columns.
    display_columns = [
        "Station",
        "Recommendation",
        "Regular Price",
        "Distance (miles)",
        "Address",
        "Last Updated",
    ]

    display_df = display_df[display_columns].copy()

    styled_table = (
        display_df.style
        .set_table_styles(table_styles)
        .apply(highlight_recommendation, axis=1)
    )

    st.container(border=True).dataframe(

        styled_table,

        width="stretch",

        hide_index=True,

        column_config={

            "Station": st.column_config.TextColumn(
                "Station",
                width="medium",
            ),

            "Recommendation": st.column_config.TextColumn(
                "Recommendation",
                width="medium",
            ),

            "Regular Price": st.column_config.NumberColumn(
                "Price / gal",
                format="$%.2f",
            ),

            "Distance (miles)": st.column_config.NumberColumn(
                "Distance",
                format="%.2f mi",
                help="Straight-line distance from campus.",
            ),

            "Address": st.column_config.TextColumn(
                "Address",
                width="large",
            ),

            "Last Updated": st.column_config.DatetimeColumn(
                "Last Updated (ET)",
                format="MMM D, h:mm A",
                timezone="America/New_York",
                width="medium",
                help="Time the gas price was last reported.",
            ),

        },
    )

    st.download_button(
        "Download filtered stations (CSV)",
        data=display_df.to_csv(index=False).encode("utf-8"),
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


