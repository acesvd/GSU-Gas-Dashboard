
"""
GSU Gas Station Dashboard
Interactive Google Maps Integration

Responsibilities:
    - Register the custom Google Maps component
    - Load the HTML, CSS, and JavaScript assets
    - Convert pandas station data into map-friendly records
    - Determine whether gas prices are eligible
    - Pass data to the JavaScript frontend
    - Read the selected radius from Streamlit session state

This module does NOT make Google Places API requests.
"""

from pathlib import Path

import pandas as pd
import streamlit as st


# ==================================================
# 1. CONFIGURATION
# ==================================================

# Streamlit component session-state key.
MAP_COMPONENT_KEY = "gsu_live_map"

# Default search radius.
DEFAULT_RADIUS = 2.00

# Allowed radius range.
MIN_RADIUS = 0.50
MAX_RADIUS = 3.00

# Maximum geographic coverage of our station dataset.
MAX_DATA_RADIUS = 3.00


# ==================================================
# 2. ASSET PATHS
# ==================================================

# Get the project's root directory.
#
# Example:
# GSU-Gas-Dashboard/
#     assets/
#     ui/
#         map.py

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ASSETS_DIR = PROJECT_ROOT / "assets"


def load_asset(filename):
    """
    Load the contents of an asset file.

    Parameters
    ----------
    filename : str
        Name of the file inside the assets directory.

    Returns
    -------
    str
        Contents of the asset file.
    """

    file_path = ASSETS_DIR / filename

    return file_path.read_text(encoding="utf-8")


# ==================================================
# 3. REGISTER CUSTOM MAP COMPONENT
# ==================================================

# Register the component once at module import.
#
# Streamlit will use:
#     map.html -> HTML structure
#     map.css  -> Visual styling
#     map.js   -> Interactive behavior

google_map_component = st.components.v2.component(

    name="gsu_gas_station_map",

    html=load_asset("map.html"),

    css=load_asset("map.css"),

    js=load_asset("map.js"),

    # Render in the main page DOM.
    # This also avoids the iframe referrer issue
    # encountered with our earlier map implementation.
    isolate_styles=False

)


# ==================================================
# 4. READ SELECTED RADIUS
# ==================================================

def get_selected_radius(default=DEFAULT_RADIUS):
    """
    Read the radius selected in the JavaScript slider.

    The slider sends its value to Streamlit when the
    user releases it.

    This function retrieves that value from
    Streamlit's session state.

    Parameters
    ----------
    default : float
        Radius to use before the user makes a selection.

    Returns
    -------
    float
        Selected radius, restricted to 0.50-3.00 miles.
    """

    component_state = st.session_state.get(
        MAP_COMPONENT_KEY,
        {}
    )

    selected_radius = component_state.get(
        "radius",
        default
    )

    # Handle missing or invalid values.
    try:
        radius = float(selected_radius)

    except (TypeError, ValueError):
        radius = float(default)

    # Restrict radius to allowed range.
    radius = max(
        MIN_RADIUS,
        min(MAX_RADIUS, radius)
    )

    return round(radius, 2)


# ==================================================
# 5. PREPARE STATION DATA
# ==================================================

def prepare_map_stations(df, max_age):
    """
    Convert a pandas DataFrame into station records
    that can be passed safely to JavaScript.

    Importantly, this function includes ALL stations
    within the maximum 3-mile data coverage.

    It does not filter by the currently selected
    radius because JavaScript handles that instantly
    while the user drags the slider.

    Parameters
    ----------
    df : pandas.DataFrame
        Station data returned by Google Places.

    max_age : int or float
        Maximum eligible price age in hours.

    Returns
    -------
    list[dict]
        JSON-compatible station records.
    """

    stations = []

    if df is None or df.empty:
        return stations

    for _, row in df.iterrows():

        # ------------------------------------------
        # REQUIRED STATION FIELDS
        # ------------------------------------------

        place_id = row["Place ID"]

        latitude = row["Latitude"]

        longitude = row["Longitude"]

        distance = row["Distance (miles)"]

        # Skip records that cannot be mapped.
        if (
            pd.isna(place_id)
            or pd.isna(latitude)
            or pd.isna(longitude)
            or pd.isna(distance)
        ):
            continue

        distance = float(distance)

        # Keep stations within the original
        # three-mile data coverage.
        if distance > MAX_DATA_RADIUS:
            continue


        # ------------------------------------------
        # STATION INFORMATION
        # ------------------------------------------

        station_id = str(place_id)

        station_name = str(row["Station"])

        latitude = float(latitude)

        longitude = float(longitude)


        # ------------------------------------------
        # REGULAR GAS PRICE
        # ------------------------------------------

        raw_price = row["Regular Price"]

        if pd.notna(raw_price):

            price = round(
                float(raw_price),
                2
            )

        else:

            price = None


        # ------------------------------------------
        # PRICE AGE
        # ------------------------------------------

        raw_age = row["Price Age (hours)"]

        if pd.notna(raw_age):

            age = float(raw_age)

        else:

            age = None


        # ------------------------------------------
        # PRICE ELIGIBILITY
        # ------------------------------------------

        # Match the existing dashboard filtering:
        #
        # 1. Price must exist.
        # 2. Price age must exist.
        # 3. Price age must be nonnegative.
        # 4. Price age cannot exceed max_age.

        eligible = (

            price is not None

            and age is not None

            and 0 <= age <= max_age

        )


        # ------------------------------------------
        # CREATE JAVASCRIPT-FRIENDLY RECORD
        # ------------------------------------------

        station_record = {

            "id": station_id,

            "name": station_name,

            "lat": latitude,

            "lng": longitude,

            "distance": distance,

            "price": price,

            "age": age,

            "eligible": bool(eligible)

        }

        stations.append(station_record)


    return stations


# ==================================================
# 6. RENDER INTERACTIVE GOOGLE MAP
# ==================================================

def render_map(
    df,
    radius,
    max_age,
    data_loaded,
    campus_lat,
    campus_lon
):
    """
    Render the interactive Google Map.

    Parameters
    ----------
    df : pandas.DataFrame
        Complete station dataset.

    radius : float
        Current selected radius in miles.

    max_age : int or float
        Maximum eligible price age in hours.

    data_loaded : bool
        Whether real station data is available.

    campus_lat : float
        Campus latitude.

    campus_lon : float
        Campus longitude.

    Returns
    -------
    ComponentResult
        Streamlit component result containing
        the current radius state.
    """

    # ----------------------------------------------
    # PREPARE MAP DATA
    # ----------------------------------------------

    if data_loaded:

        map_stations = prepare_map_stations(
            df=df,
            max_age=max_age
        )

    else:

        # Design preview:
        # Show the map and radius circle, but no
        # station markers or retrieved gas prices.
        map_stations = []


    # ----------------------------------------------
    # READ BROWSER API KEY
    # ----------------------------------------------

    # This must be the browser-restricted Maps
    # JavaScript API key.
    #
    # Do not use GOOGLE_PLACES_API_KEY here.

    maps_browser_key = st.secrets[
        "GOOGLE_MAPS_BROWSER_KEY"
    ]


    # ----------------------------------------------
    # DATA SENT TO JAVASCRIPT
    # ----------------------------------------------

    map_data = {

        "apiKey": maps_browser_key,

        "campus": {

            "lat": float(campus_lat),

            "lng": float(campus_lon)

        },

        "radius": float(radius),

        "hasData": bool(data_loaded),

        "stations": map_stations

    }


    # ----------------------------------------------
    # MOUNT MAP COMPONENT
    # ----------------------------------------------

    result = google_map_component(

        data=map_data,

        # Initialize radius state without requiring
        # an additional Streamlit rerun.
        default={
            "radius": DEFAULT_RADIUS
        },

        # Register callback for radius changes.
        on_radius_change=lambda: None,

        # A stable key allows the frontend map to
        # remain mounted between Streamlit reruns.
        key=MAP_COMPONENT_KEY,

        width="stretch",

        height=700

    )


    return result
