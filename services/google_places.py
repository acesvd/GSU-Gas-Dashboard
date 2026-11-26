
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
import re
import logging

logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)


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
    "places.primaryType,"
    "places.types,"
    "places.businessStatus,"
    "places.fuelOptions"
)

MILES_TO_METERS = 1609.344

EARTH_RADIUS_MILES = 3958.7613

MAX_RESULT_COUNT = 20

# MAX_SEARCH_DISTANCE_MILES = 3.0

# # SEARCH_CIRCLE_RADIUS_MILES = 1.7

# # SEARCH_OFFSETS_MILES = [-1.5, 0.0, 1.5]

# SEARCH_CIRCLE_RADIUS_MILES = 1.15

# SEARCH_OFFSETS_MILES = [
#     -2.25,
#     -0.75,
#      0.75,
#      2.25
# ]

MAX_SEARCH_DISTANCE_MILES = 3.0

SEARCH_PROFILES = {

    "sparse": {
        "radius": 2.2,
        "offsets": [-1.5, 1.5]
    },

    "standard": {
        "radius": 1.7,
        "offsets": [-1.5, 0.0, 1.5]
    },

    "dense": {
        "radius": 1.15,
        "offsets": [-2.25, -0.75, 0.75, 2.25]
    }

}


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
    "Amoco",
    "Valero",
    "76",
    "Kroger Fuel Center",
    "Costco",
    "Sam's Club",
    "RaceTrac",
    "RaceWay",
    "Murphy USA",
    "Murphy Express",
    "Marathon",
    "Sunoco",
    "Speedway",
    "Circle K",
    "Wawa",
    "7-Eleven",
    "Gulf",
    "Love's",
    "Pilot",
    "Flying J",
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
    using whole-word matching.
    """

    station_name = str(station_name)

    for brand in KNOWN_BRANDS:

        pattern = (
            r"(?<!\w)"
            + re.escape(brand)
            + r"(?!\w)"
        )

        if re.search(
            pattern,
            station_name,
            flags=re.IGNORECASE
        ):
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
# 6A. DUPLICATE PLACE RECORD SELECTION
# ==================================================

def select_preferred_place(existing_place, new_place):
    """
    Select the preferred record when multiple API
    searches return the same Google Place ID.

    Prioritize:
        1. Availability of regular unleaded price
        2. Most recent regular price timestamp
        3. Completeness of fuel price information
    """

    existing_price, existing_time = (
        extract_regular_price(existing_place)
    )

    new_price, new_time = (
        extract_regular_price(new_place)
    )

    existing_has_price = pd.notna(existing_price)
    new_has_price = pd.notna(new_price)

    # ----------------------------------------------
    # PRIORITIZE REGULAR PRICE AVAILABILITY
    # ----------------------------------------------

    if new_has_price and not existing_has_price:
        return new_place

    if existing_has_price and not new_has_price:
        return existing_place

    # ----------------------------------------------
    # PRIORITIZE REGULAR PRICE FRESHNESS
    # ----------------------------------------------

    if existing_has_price and new_has_price:

        existing_timestamp = pd.to_datetime(
            existing_time,
            utc=True,
            errors="coerce"
        )

        new_timestamp = pd.to_datetime(
            new_time,
            utc=True,
            errors="coerce"
        )

        if pd.notna(new_timestamp):

            if pd.isna(existing_timestamp):
                return new_place

            if new_timestamp > existing_timestamp:
                return new_place

            if new_timestamp < existing_timestamp:
                return existing_place

        elif pd.notna(existing_timestamp):
            return existing_place

    # ----------------------------------------------
    # PRIORITIZE FUEL INFORMATION COMPLETENESS
    # ----------------------------------------------

    existing_fuels = (
        existing_place.get("fuelOptions") or {}
    ).get("fuelPrices") or []

    new_fuels = (
        new_place.get("fuelOptions") or {}
    ).get("fuelPrices") or []

    if len(new_fuels) > len(existing_fuels):
        return new_place

    # Retain existing record if neither is preferable
    return existing_place


# ==================================================
# 7. GENERATE GEOGRAPHIC SEARCH AREAS
# ==================================================

def generate_search_areas(search_profile="dense"):
    """
    Generate overlapping geographic search areas
    using the specified search profile.

    Parameters
    ----------
    search_profile : str
        Name of the geographic search configuration.

    Returns
    -------
    list[tuple]
        (north_offset, east_offset, radius_miles)
    """

    if search_profile not in SEARCH_PROFILES:

        raise ValueError(
            f"Unknown search profile: {search_profile}"
        )

    profile = SEARCH_PROFILES[search_profile]

    offsets = profile["offsets"]

    radius = profile["radius"]

    search_areas = []

    for north in offsets:

        for east in offsets:

            search_areas.append(
                (
                    north,
                    east,
                    radius
                )
            )

    return search_areas


# ==================================================
# VALIDATE GAS STATION CLASSIFICATION
# ==================================================

def is_valid_gas_station(place):
    """
    Retain high-confidence and likely gas stations
    using business status, fuel information,
    and provisional brand identification.
    """

    primary_type = place.get("primaryType")

    business_status = place.get("businessStatus")

    station_name = (
        place.get("displayName") or {}
    ).get("text", "Unknown")

    fuel_options = place.get("fuelOptions") or {}

    fuel_prices = fuel_options.get("fuelPrices") or []

    brand = identify_brand(station_name)

    # 1. Exclude closed businesses
    if business_status in {
        "CLOSED_PERMANENTLY",
        "CLOSED_TEMPORARILY"
    }:
        return False

    # 2. Require gas station classification
    if primary_type != "gas_station":
        return False

    # 3. Accept stations with fuel price information
    if fuel_prices:
        return True

    # 4. Accept likely branded gas stations,
    # even when fuel prices are missing
    if brand != "Unverified":
        return True

    # 5. Exclude unsupported listings
    return False

# Initial physical-location matching threshold
DUPLICATE_DISTANCE_METERS = 50

def has_fuel_prices(place):

    fuel_options = place.get("fuelOptions") or {}

    return bool(fuel_options.get("fuelPrices"))


def normalize_address(place):

    address = place.get("formattedAddress") or ""

    address = address.casefold()

    address = re.sub(r"[^\w\s]", " ", address)

    return " ".join(address.split())


def remove_colocated_listings(places):
    """
    Remove likely duplicate listings that have
    no fuel prices but share an address and
    location with a listing that has fuel prices.
    """

    priced_places = [
        place for place in places
        if has_fuel_prices(place)
    ]

    retained_places = []

    duplicate_places = []

    for place in places:

        # Always retain listings with fuel data
        # at this stage.
        if has_fuel_prices(place):

            retained_places.append(place)

            continue

        location = place.get("location") or {}

        lat = location.get("latitude")
        lon = location.get("longitude")

        address = normalize_address(place)

        # Insufficient information to match safely
        if lat is None or lon is None or not address:

            retained_places.append(place)

            continue

        matches = []

        for priced_place in priced_places:

            # Require matching addresses
            if address != normalize_address(priced_place):

                continue

            priced_location = (
                priced_place.get("location") or {}
            )

            priced_lat = priced_location.get("latitude")
            priced_lon = priced_location.get("longitude")

            if priced_lat is None or priced_lon is None:

                continue

            distance = distance_miles(
                lat,
                lon,
                priced_lat,
                priced_lon
            ) * MILES_TO_METERS

            if distance <= DUPLICATE_DISTANCE_METERS:

                matches.append(priced_place)

        # Suppress a likely duplicate only when
        # exactly one priced listing matches.
        if len(matches) == 1:

            duplicate_places.append(place)

            logger.debug(
                "Likely duplicate: %s | Matched with: %s",
                (place.get("displayName") or {}).get("text"),
                (matches[0].get("displayName") or {}).get("text")
            )

        else:

            retained_places.append(place)

    return retained_places, duplicate_places


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
    
    # Validate business classification
    if not is_valid_gas_station(place):
        return None

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
    campus_lon,
    search_profile="dense"
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

    search_areas = generate_search_areas(
        search_profile=search_profile
    )


    # ----------------------------------------------
    # PREPARE SEARCH TRACKING
    # ----------------------------------------------

    unique_places = {}

    capped_searches = 0

    requests_made = 0

    search_details = []

    # Additional retrieval diagnostics
    raw_results_count = 0

    missing_place_id_count = 0

    repeated_place_id_count = 0


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

            "includedPrimaryTypes": [
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
        
        if not response.ok:

            try:
                error_data = response.json().get("error", {})

                logger.error(
                    "Google Places API error: %s",
                    error_data
                )

            except ValueError:

                logger.error(
                    "Google Places API returned HTTP %s",
                    response.status_code
                )

        response.raise_for_status()


        # ------------------------------------------
        # PROCESS RESPONSE
        # ------------------------------------------

        results = response.json().get(
            "places",
            []
        )
        
        raw_results_count += len(results)
        
        for place in results:

            logger.debug({
                "place_id": place.get("id"),

                "name": (
                    place.get("displayName") or {}
                ).get("text"),

                "address": place.get("formattedAddress"),

                "latitude": (
                    place.get("location") or {}
                ).get("latitude"),

                "longitude": (
                    place.get("location") or {}
                ).get("longitude"),

                "primary_type": place.get("primaryType"),

                "types": place.get("types"),

                "business_status": place.get("businessStatus"),

                "fuel_options": place.get("fuelOptions", {})
            })

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

            # Track records without Place IDs
            if not place_id:

                missing_place_id_count += 1

                continue

            # Store newly encountered Place IDs
            if place_id not in unique_places:

                unique_places[place_id] = place

            else:

                # Track repeated Place IDs
                repeated_place_id_count += 1

                # Retain the preferred record
                unique_places[place_id] = (
                    select_preferred_place(
                        unique_places[place_id],
                        place
                    )
                )


    # ==================================================
    # 10. PROCESS UNIQUE STATIONS
    # ==================================================

    rows = []

    current_time = pd.Timestamp.now(
        tz="UTC"
    )

    # ----------------------------------------------
    # INITIALIZE CLEANING DIAGNOSTICS
    # ----------------------------------------------

    closed_business_count = 0

    unverified_listing_count = 0

    invalid_location_count = 0

    outside_radius_count = 0


    # ----------------------------------------------
    # EXCLUDE CLOSED BUSINESSES
    # ----------------------------------------------

    candidate_places = []

    for place in unique_places.values():

        if place.get("businessStatus") in {
            "CLOSED_TEMPORARILY",
            "CLOSED_PERMANENTLY"
        }:

            closed_business_count += 1

            continue

        candidate_places.append(place)


    # ----------------------------------------------
    # REMOVE LIKELY COLOCATED DUPLICATES
    # ----------------------------------------------

    deduplicated_places, duplicate_places = (
        remove_colocated_listings(candidate_places)
    )

    colocated_duplicate_count = len(duplicate_places)


    # ----------------------------------------------
    # VALIDATE AND PROCESS STATIONS
    # ----------------------------------------------

    for place in deduplicated_places:

        # Validate station classification
        if not is_valid_gas_station(place):

            unverified_listing_count += 1

            continue

        # Convert API response into station record
        station = parse_station(

            place=place,

            campus_lat=campus_lat,

            campus_lon=campus_lon,

            current_time=current_time

        )

        # Track invalid location records
        if station is None:

            invalid_location_count += 1

            continue

        # Exclude stations outside maximum radius
        if (
            station["Distance (miles)"]
            > MAX_SEARCH_DISTANCE_MILES
        ):

            outside_radius_count += 1

            continue

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
    
    # ----------------------------------------------
    # VALIDATE RECORD COUNT RECONCILIATION
    # ----------------------------------------------

    total_removed = (

        missing_place_id_count

        + repeated_place_id_count

        + closed_business_count

        + colocated_duplicate_count

        + unverified_listing_count

        + invalid_location_count

        + outside_radius_count

    )

    reconciliation_difference = (

        raw_results_count

        - total_removed

        - len(stations_df)

    )

    search_metadata = {

        # API retrieval information
        "requests_made": requests_made,

        "capped_searches": capped_searches,

        "raw_results": raw_results_count,

        "search_details": search_details,

        # Place ID diagnostics
        "missing_place_ids": missing_place_id_count,

        "repeated_place_ids": repeated_place_id_count,

        "unique_google_ids": len(unique_places),

        # Cleaning diagnostics
        "closed_businesses_removed": closed_business_count,

        "colocated_duplicates_removed": colocated_duplicate_count,

        "unverified_listings_removed": unverified_listing_count,

        "invalid_locations_removed": invalid_location_count,

        "outside_radius_removed": outside_radius_count,

        # Final results
        "unique_listings": len(stations_df),

        "stations_with_prices": int(
            stations_df["Regular Price"].notna().sum()
        ),

        "stations_without_prices": int(
            stations_df["Regular Price"].isna().sum()
        ),
        
        "total_removed": total_removed,

        "reconciliation_difference": reconciliation_difference,
        
        "search_profile": search_profile,

        "search_circle_radius": (
            SEARCH_PROFILES[search_profile]["radius"]
        ),

        "search_grid_size": len(
            SEARCH_PROFILES[search_profile]["offsets"]
        ),
    }

    return stations_df, search_metadata
