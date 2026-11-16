
"""
GSU Gas Station Dashboard
Google Places API Service

Responsibilities:
    - Retrieve gas station data from Google Places API (New)
    - Search nine overlapping geographic areas
    - Deduplicate Google Place IDs
    - Restrict results to the campus search area
    - Extract regular unleaded gasoline prices
    - Calculate price freshness
    - Classify station brands
    - Return structured station data and search metadata

This module contains no Streamlit UI elements.

IMPORTANT:
    API requests occur ONLY when fetch_google_stations()
    is explicitly called.
"""

import math

import pandas as pd
import requests


# ==================================================
# 1. GOOGLE PLACES API CONFIGURATION
# ==================================================

GOOGLE_PLACES_URL = (
    "https://places.googleapis.com/v1/"
    "places:searchNearby"
)

GOOGLE_PLACES_FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.fuelOptions"
)

MILES_TO_METERS = 1609.344

EARTH_RADIUS_MILES = 3958.7613

MAX_RESULT_COUNT = 20

MAX_SEARCH_DISTANCE_MILES = 3.0

SEARCH_CIRCLE_RADIUS_MILES = 1.7

SEARCH_OFFSETS_MILES = [-1.5, 0.0, 1.5]


# ==================================================
# 2. STATION DATA SCHEMA
# ==================================================

STATION_COLUMNS = [
    "Station",
    "Brand",
    "Latitude",
    "Longitude",
    "Distance (miles)",
    "Regular Price",
    "Price Age (hours)",
    "Last Updated",
    "Place ID",
    "Address"
]


# ==================================================
# 3. KNOWN GAS STATION BRANDS
# ==================================================

KNOWN_BRANDS = [
    "QuikTrip",
    "Shell",
    "Chevron",
    "BP",
    "Texaco",
    "ARCO",
    "Citgo",
    "Exxon",
    "Mobil",
    "Amoco"
]


# ==================================================
# 4. GEOGRAPHIC DISTANCE CALCULATION
# ==================================================

def distance_miles(lat1, lon1, lat2, lon2):
    """
    Calculate straight-line distance between two
    geographic coordinates using the Haversine formula.

    Parameters
    ----------
    lat1, lon1 : float
        First geographic coordinate.

    lat2, lon2 : float
        Second geographic coordinate.

    Returns
    -------
    float
        Distance in miles.
    """

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    dlat = lat2 - lat1
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return (
        2
        * EARTH_RADIUS_MILES
        * math.asin(min(1, math.sqrt(a)))
    )


# ==================================================
# 5. STATION BRAND CLASSIFICATION
# ==================================================

def identify_brand(station_name):
    """
    Identify a station's provisional brand
    using its Google Places display name.

    Returns 'Unverified' when no known brand
    is identified.
    """

    station_name = str(station_name)

    for brand in KNOWN_BRANDS:

        if brand.lower() in station_name.lower():

            return brand

    return "Unverified"


# ==================================================
# 6. REGULAR UNLEADED PRICE EXTRACTION
# ==================================================

def extract_regular_price(place):
    """
    Extract regular unleaded gasoline price
    and its update timestamp from a Google
    Places response.

    Parameters
    ----------
    place : dict
        Google Places station record.

    Returns
    -------
    tuple
        (price, update_time)

        price : float or None
        update_time : str or None
    """

    fuel_prices = place.get(
        "fuelOptions",
        {}
    ).get(
        "fuelPrices",
        []
    )


    # Find regular unleaded gasoline.
    regular = next(
        (
            fuel
            for fuel in fuel_prices
            if fuel.get("type") == "REGULAR_UNLEADED"
        ),
        None
    )


    if regular is None:

        return None, None


    # ----------------------------------------------
    # EXTRACT PRICE
    # ----------------------------------------------

    money = regular.get("price")

    price = None

    if money is not None:

        units = int(
            money.get("units", 0)
        )

        nanos = int(
            money.get("nanos", 0)
        )

        price = (
            units
            + nanos / 1e9
        )


    # ----------------------------------------------
    # EXTRACT UPDATE TIMESTAMP
    # ----------------------------------------------

    update_time = regular.get(
        "updateTime"
    )


    return price, update_time


# ==================================================
# 7. GENERATE GEOGRAPHIC SEARCH AREAS
# ==================================================

def generate_search_areas():
    """
    Generate nine overlapping geographic search areas.

    Each search circle has a radius of 1.7 miles.

    Search centers are shifted north/south and
    east/west using offsets of:

        -1.5 miles
         0.0 miles
         1.5 miles

    Returns
    -------
    list[tuple]
        (north_offset, east_offset, radius_miles)
    """

    search_areas = []

    for north in SEARCH_OFFSETS_MILES:

        for east in SEARCH_OFFSETS_MILES:

            search_areas.append(
                (
                    north,
                    east,
                    SEARCH_CIRCLE_RADIUS_MILES
                )
            )

    return search_areas


# ==================================================
# 8. CONVERT GOOGLE PLACE TO STATION RECORD
# ==================================================

def parse_station(
    place,
    campus_lat,
    campus_lon,
    current_time
):
    """
    Convert a Google Places station response
    into a standardized dashboard record.

    Returns None if required location
    information is missing.
    """

    # ----------------------------------------------
    # IDENTIFY STATION
    # ----------------------------------------------

    place_id = place.get("id")

    display_name = place.get(
        "displayName"
    ) or {}

    station_name = display_name.get(
        "text",
        "Unknown"
    )


    # ----------------------------------------------
    # GET STATION COORDINATES
    # ----------------------------------------------

    location = place.get(
        "location"
    ) or {}

    latitude = location.get(
        "latitude"
    )

    longitude = location.get(
        "longitude"
    )

    if latitude is None or longitude is None:

        return None


    # ----------------------------------------------
    # CALCULATE DISTANCE
    # ----------------------------------------------

    distance = distance_miles(
        campus_lat,
        campus_lon,
        latitude,
        longitude
    )


    # ----------------------------------------------
    # GET REGULAR UNLEADED PRICE
    # ----------------------------------------------

    price, update_time = extract_regular_price(
        place
    )


    # ----------------------------------------------
    # CONVERT TIMESTAMP
    # ----------------------------------------------

    timestamp = pd.to_datetime(
        update_time,
        utc=True,
        errors="coerce"
    )


    # ----------------------------------------------
    # CALCULATE PRICE AGE
    # ----------------------------------------------

    age_hours = None

    if pd.notna(timestamp):

        age_hours = (
            current_time - timestamp
        ).total_seconds() / 3600


    # ----------------------------------------------
    # IDENTIFY BRAND
    # ----------------------------------------------

    brand = identify_brand(
        station_name
    )


    # ----------------------------------------------
    # CREATE STANDARDIZED RECORD
    # ----------------------------------------------

    station_record = {

        "Station": station_name,

        "Brand": brand,

        "Latitude": latitude,

        "Longitude": longitude,

        "Distance (miles)": round(
            distance,
            3
        ),

        "Regular Price": price,

        "Price Age (hours)": age_hours,

        "Last Updated": timestamp,

        "Place ID": place_id,

        "Address": place.get(
            "formattedAddress"
        )

    }


    return station_record


# ==================================================
# 9. MAIN GOOGLE PLACES RETRIEVAL FUNCTION
# ==================================================

def fetch_google_stations(
    api_key,
    campus_lat,
    campus_lon
):
    """
    Retrieve and process gas station data.

    This function:

        1. Generates nine overlapping search areas.
        2. Makes nine Nearby Search requests.
        3. Collects unique Google Place IDs.
        4. Filters stations to within 3 miles.
        5. Extracts regular gasoline prices.
        6. Calculates price freshness.
        7. Returns a DataFrame and search metadata.

    Parameters
    ----------
    api_key : str
        Server-side Google Places API key.

    campus_lat : float
        Campus latitude.

    campus_lon : float
        Campus longitude.

    Returns
    -------
    tuple
        stations_df : pandas.DataFrame
        search_metadata : dict

    Notes
    -----
    Calling this function incurs Google Places
    API requests.

    Do not call this function automatically
    when Streamlit reruns.
    """

    if not api_key:

        raise ValueError(
            "A Google Places API key is required."
        )


    # ----------------------------------------------
    # CONFIGURE REQUEST HEADERS
    # ----------------------------------------------

    headers = {

        "Content-Type": "application/json",

        "X-Goog-Api-Key": api_key,

        "X-Goog-FieldMask":
            GOOGLE_PLACES_FIELD_MASK

    }


    # ----------------------------------------------
    # GENERATE SEARCH AREAS
    # ----------------------------------------------

    search_areas = generate_search_areas()


    # ----------------------------------------------
    # PREPARE SEARCH TRACKING
    # ----------------------------------------------

    unique_places = {}

    capped_searches = 0

    requests_made = 0

    search_details = []


    # ----------------------------------------------
    # CALCULATE COORDINATE CONVERSIONS
    # ----------------------------------------------

    lat_miles_per_degree = 69.0

    lon_miles_per_degree = (
        69.172
        * math.cos(math.radians(campus_lat))
    )


    # ----------------------------------------------
    # EXECUTE NINE NEARBY SEARCHES
    # ----------------------------------------------

    for north, east, search_radius in search_areas:

        center_lat = (
            campus_lat
            + north / lat_miles_per_degree
        )

        center_lon = (
            campus_lon
            + east / lon_miles_per_degree
        )


        # ------------------------------------------
        # CREATE REQUEST PAYLOAD
        # ------------------------------------------

        payload = {

            "includedTypes": [
                "gas_station"
            ],

            "maxResultCount": MAX_RESULT_COUNT,

            "rankPreference": "DISTANCE",

            "locationRestriction": {

                "circle": {

                    "center": {

                        "latitude": center_lat,

                        "longitude": center_lon

                    },

                    "radius": (
                        search_radius
                        * MILES_TO_METERS
                    )

                }

            }

        }


        # ------------------------------------------
        # MAKE GOOGLE PLACES REQUEST
        # ------------------------------------------

        requests_made += 1

        response = requests.post(

            GOOGLE_PLACES_URL,

            headers=headers,

            json=payload,

            timeout=30

        )

        response.raise_for_status()


        # ------------------------------------------
        # PROCESS RESPONSE
        # ------------------------------------------

        results = response.json().get(
            "places",
            []
        )

        hit_cap = (
            len(results) == MAX_RESULT_COUNT
        )

        if hit_cap:

            capped_searches += 1


        # ------------------------------------------
        # RECORD SEARCH INFORMATION
        # ------------------------------------------

        search_details.append({

            "north_offset": north,

            "east_offset": east,

            "radius_miles": search_radius,

            "returned": len(results),

            "hit_cap": hit_cap

        })


        # ------------------------------------------
        # COLLECT UNIQUE PLACE IDS
        # ------------------------------------------

        for place in results:

            place_id = place.get("id")

            if place_id:

                unique_places[place_id] = place


    # ==================================================
    # 10. PROCESS UNIQUE STATIONS
    # ==================================================

    rows = []

    current_time = pd.Timestamp.now(
        tz="UTC"
    )


    for place in unique_places.values():

        station = parse_station(

            place=place,

            campus_lat=campus_lat,

            campus_lon=campus_lon,

            current_time=current_time

        )


        if station is None:

            continue


        # ------------------------------------------
        # KEEP STATIONS WITHIN THREE MILES
        # ------------------------------------------

        if (
            station["Distance (miles)"]
            <= MAX_SEARCH_DISTANCE_MILES
        ):

            rows.append(station)


    # ----------------------------------------------
    # BUILD DATAFRAME
    # ----------------------------------------------

    stations_df = pd.DataFrame(
        rows,
        columns=STATION_COLUMNS
    )


    # ==================================================
    # 11. SEARCH METADATA
    # ==================================================

    search_metadata = {

        "unique_listings": len(stations_df),

        "unique_google_ids": len(unique_places),

        "capped_searches": capped_searches,

        "requests_made": requests_made,

        "search_details": search_details

    }


    return stations_df, search_metadata
