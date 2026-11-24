
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
    page_title="What is the best gas station to fill up near campus?",
    page_icon="⛽",
    layout="wide",
)

# Georgia State University - Buckhead Campus
CAMPUS_LAT = 33.848057
CAMPUS_LON = -84.370042


# ============================================================
# 2. DASHBOARD HEADER
# ============================================================

st.markdown(
    """
    <style>
      .story-eyebrow {
        color: #64748b;
        font-size: 1rem;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        margin: 0.25rem 0 0.55rem 0;
      }
      .story-title {
        color: #102A43;
        font-size: clamp(3.75rem, 6vw, 5.5rem);
        line-height: 1.08;
        letter-spacing: -0.035em;
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
      .story-card {
        background: linear-gradient(135deg, #eff6ff 0%, #ffffff 72%);
        border: 1px solid #bfdbfe;
        border-left: 7px solid #2563eb;
        border-radius: 14px;
        padding: 1.15rem 1.25rem;
        margin: 0 0 1.25rem 0;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.035);
      }
      .story-kicker {
        color: #1d4ed8;
        font-size: 1rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
      }
      .story-sentence {
        color: #1e293b;
        font-size: clamp(1.35rem, 2vw, 1.65rem);
        line-height: 1.45;
        margin: 0;
      }
      .story-price {
        color: #ea580c;
        font-size: 1.45em;
        font-weight: 800;
        white-space: nowrap;
      }
      .story-context-card {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-radius: 14px;
        min-height: 112px;
        padding: 1rem 1.05rem;
        margin-bottom: 1.35rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.025);
      }
      .story-context-label {
        color: #2563eb;
        font-size: 1rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
      }
      .story-context-value {
        color: #334155;
        font-size: 1.25rem;
        line-height: 1.42;
      }
    </style>
    <div class="story-eyebrow">Campus decision guide · Nov 23, 2026</div>
    <h1 class="story-title">What is the best gas station to fill up near campus?</h1>
    <div class="story-accent"></div>
    """,
    unsafe_allow_html=True,
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
# 10. DASHBOARD HEADER
# ============================================================

if data_loaded and not filtered.empty:

    prices = pd.to_numeric(
        filtered["Regular Price"],
        errors="coerce",
    ).dropna()

    price_spread = (
        float(prices.max()) - float(prices.min())
        if not prices.empty
        else 0.0
    )

    ten_gallon_difference = price_spread * 10

    st.markdown(
        '<div class="story-card">'
        '<div class="story-kicker">The cost of choosing</div>'
        '<p class="story-sentence">The same gallon costs up to '
        f'<span class="story-price">${price_spread:.2f}</span> more '
        "depending on where you stop. "
        "That can mean "
        f'<span class="story-price">${ten_gallon_difference:.2f}</span> '
        "on a 10-gallon fill-up.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

else:

    st.markdown(
        '<div class="story-card">'
        '<div class="story-kicker">The cost of choosing</div>'
        '<p class="story-sentence">The same gallon can cost more '
        "depending on where you stop. "
        "Compare the price spread below to see the difference "
        "on a 10-gallon fill-up.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

question_col, audience_col, scope_col = st.columns(3)

with question_col:
    st.markdown(
        '<div class="story-context-card">'
        '<div class="story-context-label">The question</div>'
        '<div class="story-context-value">Which nearby station is '
        "the best value, balancing price, distance and price "
        "freshness?</div></div>",
        unsafe_allow_html=True,
    )

with audience_col:
    st.markdown(
        '<div class="story-context-card">'
        '<div class="story-context-label">The decision</div>'
        '<div class="story-context-value">Students and staff driving '
        "to campus who need regular unleaded gas.</div></div>",
        unsafe_allow_html=True,
    )

with scope_col:
    st.markdown(
        '<div class="story-context-card">'
        '<div class="story-context-label">The scope</div>'
        f'<div class="story-context-value">Stations within '
        f"{radius:.2f} miles, using one Google Maps snapshot.</div></div>",
        unsafe_allow_html=True,
    )


# ============================================================
# 11. DASHBOARD OVERVIEW
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
    <div class="map-section-eyebrow">Explore the area</div>
    <h2 class="map-section-title">Gas Stations Near Campus</h2>
    <p class="map-section-description">
      Adjust the search radius and compare eligible stations around campus.
    </p>
    """,
    unsafe_allow_html=True,
)

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
    <div class="table-section-eyebrow">Review every option</div>
    <h2 class="table-section-title">Available Gas Stations</h2>
    <p class="table-section-description">
      Review station details, regular gas prices and reported freshness
      within the selected radius.
    </p>
    """,
    unsafe_allow_html=True,
)

def highlight_lowest_price(prices):
    numeric_prices = pd.to_numeric(prices, errors="coerce")
    lowest_price = numeric_prices.min()

    return [
        (
            "background-color: #dcfce7; color: #166534; font-weight: 800"
            if pd.notna(price) and price == lowest_price
            else "color: #1d4ed8; font-weight: 700"
            if pd.notna(price)
            else ""
        )
        for price in numeric_prices
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
    filtered.style
    .set_table_styles(table_styles)
    .apply(highlight_lowest_price, subset=["Regular Price"])
)

st.container(border=True).dataframe(
    styled_table,
    width="stretch",
    hide_index=True,
)

st.caption(
    "Gas prices may not reflect prices currently "
    "posted at the pump. Verify prices before traveling."
)
