
import requests
import pandas as pd
import streamlit as st

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
    page_title="GSU Gas Station Dashboard",
    page_icon="⛽",
    layout="wide",
)

# Georgia State University - Buckhead Campus
CAMPUS_LAT = 33.848057
CAMPUS_LON = -84.370042


# ============================================================
# 2. DASHBOARD HEADER
# ============================================================

st.title("⛽ GSU Gas Station Dashboard")

st.write(
    "Find and compare affordable gas stations near "
    "Georgia State University's Buckhead Campus."
)


# ============================================================
# 3. SIDEBAR - DATA CONTROLS
# ============================================================

st.sidebar.header("Google Places Data")

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
                )
            )

            # Store retrieved data in session state.
            st.session_state["station_data"] = station_data

            st.session_state["search_metadata"] = (
                search_metadata
            )

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


# ============================================================
# 5. API SEARCH INFORMATION
# ============================================================

search_metadata = st.session_state.get(
    "search_metadata"
)

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
        f"Found {unique_listings} unique Google listings "
        "within 3 miles."
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


# ============================================================
# 6. LOAD AND CLEAN DATA
# ============================================================

raw_data = st.session_state.get(
    "station_data"
)

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
    "Maximum price age (hours)",
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

st.subheader("Overview")

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
    cheapest_price = "—"


with col1:

    st.metric(
        label="Stations within radius",
        value=stations_found,
    )

with col2:

    st.metric(
        label="Stations with eligible prices",
        value=eligible_count,
    )

with col3:

    st.metric(
        label="Lowest gas price",
        value=cheapest_price,
    )


# ============================================================
# 11. BEST GAS STATION RECOMMENDATIONS
# ============================================================

st.subheader("🏆 Best Gas Station Options")

if not data_loaded:

    st.info(
        "— Gas station recommendations will appear "
        "after loading data."
    )

elif not filtered.empty:

    # Find the closest station offering
    # the lowest eligible price.

    best_station = get_best_station(
        filtered
    )

    # Identify any stations tied for the lowest price.
    cheapest_stations = get_cheapest_stations(
        filtered
    )

    st.success(
        "Closest station offering the lowest price: "
        f"{best_station['Station']} "
        f"({best_station['Brand']}) — "
        f"${best_station['Regular Price']:.2f}/gal, "
        f"{best_station['Distance (miles)']:.2f} "
        "miles away."
    )

    if len(cheapest_stations) > 1:

        st.info(
            f"{len(cheapest_stations)} stations "
            "are tied for the lowest gas price."
        )

else:

    st.warning(
        "No stations with eligible gas prices were "
        "found within your selected radius."
    )


# ============================================================
# 12. GAS PRICE VISUALIZATIONS
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
# 13. INTERACTIVE GAS STATION MAP
# ============================================================

st.subheader("🗺️ Gas Stations Near Campus")

# The map and smooth radius slider are managed
# by ui/map.py and the assets/ folder.
#
# Moving the slider locally filters the station
# data without requesting new Google Places data.

render_map(
    df=df,
    radius=radius,
    max_age=max_age,
    data_loaded=data_loaded,
    campus_lat=CAMPUS_LAT,
    campus_lon=CAMPUS_LON,
)


# ============================================================
# 14. AVAILABLE GAS STATIONS TABLE
# ============================================================

st.subheader("Available Gas Stations")

st.dataframe(
    filtered,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Gas prices may not reflect prices currently "
    "posted at the pump. Verify prices before traveling."
)
