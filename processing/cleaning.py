
"""
GSU Gas Station Dashboard
Data Cleaning and Quality Control

Responsibilities:
    - Standardize station data types
    - Handle missing values
    - Validate geographic coordinates
    - Validate gas prices
    - Remove duplicate Google Place IDs
    - Recalculate gas price freshness
    - Preserve distinct stations at shared addresses
    - Summarize data quality

This module does NOT make API requests.
"""

import pandas as pd

from services.google_places import STATION_COLUMNS


# ==================================================
# 1. DATA CLEANING
# ==================================================

def clean_station_data(df, reference_time=None):
    """
    Clean and standardize station data.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw station DataFrame returned by the
        Google Places service.

    reference_time : datetime-like, optional
        Time used when calculating price age.
        Defaults to the current UTC time.

        This parameter is also useful for testing.

    Returns
    -------
    pandas.DataFrame
        Cleaned station data.
    """

    # ----------------------------------------------
    # HANDLE EMPTY INPUT
    # ----------------------------------------------

    if df is None:

        return pd.DataFrame(
            columns=STATION_COLUMNS
        )

    if not isinstance(df, pd.DataFrame):

        raise TypeError(
            "Station data must be a pandas DataFrame."
        )


    # ----------------------------------------------
    # COPY DATA
    # ----------------------------------------------

    # Avoid modifying the original DataFrame.
    cleaned = df.reindex(
        columns=STATION_COLUMNS
    ).copy()


    # ==================================================
    # 2. STANDARDIZE TEXT FIELDS
    # ==================================================

    # ----------------------------------------------
    # STATION NAME
    # ----------------------------------------------

    cleaned["Station"] = (
        cleaned["Station"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    cleaned["Station"] = (
        cleaned["Station"]
        .replace("", "Unknown")
    )


    # ----------------------------------------------
    # STATION BRAND
    # ----------------------------------------------

    cleaned["Brand"] = (
        cleaned["Brand"]
        .fillna("Unverified")
        .astype(str)
        .str.strip()
    )

    cleaned["Brand"] = (
        cleaned["Brand"]
        .replace("", "Unverified")
    )


    # ----------------------------------------------
    # GOOGLE PLACE ID
    # ----------------------------------------------

    cleaned["Place ID"] = (
        cleaned["Place ID"]
        .astype("string")
        .str.strip()
    )

    cleaned["Place ID"] = (
        cleaned["Place ID"]
        .replace("", pd.NA)
    )


    # ----------------------------------------------
    # STATION ADDRESS
    # ----------------------------------------------

    cleaned["Address"] = (
        cleaned["Address"]
        .astype("string")
        .str.strip()
    )

    cleaned["Address"] = (
        cleaned["Address"]
        .replace("", pd.NA)
    )


    # ==================================================
    # 3. STANDARDIZE NUMERIC FIELDS
    # ==================================================

    numeric_columns = [
        "Latitude",
        "Longitude",
        "Distance (miles)",
        "Regular Price",
        "Price Age (hours)"
    ]


    for column in numeric_columns:

        cleaned[column] = pd.to_numeric(
            cleaned[column],
            errors="coerce"
        )


    # ==================================================
    # 4. VALIDATE GEOGRAPHIC COORDINATES
    # ==================================================

    valid_latitude = (
        cleaned["Latitude"].between(
            -90,
            90
        )
    )

    valid_longitude = (
        cleaned["Longitude"].between(
            -180,
            180
        )
    )

    valid_distance = (
        cleaned["Distance (miles)"].notna()
        & (cleaned["Distance (miles)"] >= 0)
    )


    # Exclude records without usable locations.
    cleaned = cleaned.loc[

        valid_latitude
        & valid_longitude
        & valid_distance

    ].copy()


    # ==================================================
    # 5. VALIDATE GAS PRICES
    # ==================================================

    # A valid retail gas price must be positive.
    # Treat zero or negative prices as unavailable.
    #
    # Do not remove the station itself because its
    # location may still be useful on the map.

    invalid_prices = (
        cleaned["Regular Price"].notna()
        & (cleaned["Regular Price"] <= 0)
    )

    cleaned.loc[
        invalid_prices,
        "Regular Price"
    ] = float("nan")


    # ==================================================
    # 6. REMOVE DUPLICATE GOOGLE PLACE IDS
    # ==================================================

    # Important:
    #
    # We deduplicate by Google Place ID only.
    #
    # Two listings can share an address but represent
    # separate Google Places records. We should not
    # automatically remove those listings.

    duplicate_ids = (

        cleaned["Place ID"].notna()

        & cleaned["Place ID"].duplicated(
            keep="first"
        )

    )

    cleaned = cleaned.loc[
        ~duplicate_ids
    ].copy()


    # ==================================================
    # 7. STANDARDIZE PRICE TIMESTAMPS
    # ==================================================

    cleaned["Last Updated"] = pd.to_datetime(
        cleaned["Last Updated"],
        utc=True,
        errors="coerce"
    )


    # ==================================================
    # 8. DETERMINE REFERENCE TIME
    # ==================================================

    if reference_time is None:

        current_time = pd.Timestamp.now(
            tz="UTC"
        )

    else:

        current_time = pd.Timestamp(
            reference_time
        )

        # Interpret timezone-naive supplied values
        # as UTC.
        if current_time.tzinfo is None:

            current_time = current_time.tz_localize(
                "UTC"
            )

        else:

            current_time = current_time.tz_convert(
                "UTC"
            )


    # ==================================================
    # 9. RECALCULATE PRICE AGE
    # ==================================================

    # Price age is calculated from the timestamp
    # returned by Google Places.
    #
    # This calculation is entirely local and does
    # not require an additional API request.

    cleaned["Price Age (hours)"] = (

        current_time
        - cleaned["Last Updated"]

    ).dt.total_seconds() / 3600


    # Missing timestamps naturally produce NaN
    # price ages.
    #
    # We preserve these missing values so that
    # filtering.py can determine eligibility.


    # ==================================================
    # 10. RESET DATAFRAME INDEX
    # ==================================================

    cleaned = cleaned.reset_index(
        drop=True
    )


    return cleaned


# ==================================================
# 11. DATA QUALITY SUMMARY
# ==================================================

def summarize_data_quality(df):
    """
    Generate basic data-quality statistics.

    This function does not modify the dataset.

    Parameters
    ----------
    df : pandas.DataFrame
        Cleaned station data.

    Returns
    -------
    dict
        Data-quality summary statistics.
    """

    # ----------------------------------------------
    # HANDLE EMPTY DATA
    # ----------------------------------------------

    if df is None or df.empty:

        return {

            "total_listings": 0,

            "listings_with_prices": 0,

            "missing_prices": 0,

            "missing_timestamps": 0,

            "shared_address_listings": 0,

            "unique_brands": 0

        }


    # ----------------------------------------------
    # TOTAL LISTINGS
    # ----------------------------------------------

    total_listings = len(df)


    # ----------------------------------------------
    # PRICE COVERAGE
    # ----------------------------------------------

    listings_with_prices = int(
        df["Regular Price"].notna().sum()
    )

    missing_prices = (
        total_listings
        - listings_with_prices
    )


    # ----------------------------------------------
    # MISSING TIMESTAMPS
    # ----------------------------------------------

    missing_timestamps = int(
        df["Last Updated"].isna().sum()
    )


    # ----------------------------------------------
    # SHARED ADDRESSES
    # ----------------------------------------------

    # Count listings associated with addresses
    # appearing more than once.
    #
    # Missing addresses are excluded.

    addresses = (
        df["Address"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    addresses = addresses[
        addresses != ""
    ]

    shared_address_listings = int(
        addresses.duplicated(
            keep=False
        ).sum()
    )


    # ----------------------------------------------
    # UNIQUE BRANDS
    # ----------------------------------------------

    unique_brands = int(
        df["Brand"].nunique()
    )


    # ----------------------------------------------
    # RETURN SUMMARY
    # ----------------------------------------------

    return {

        "total_listings": total_listings,

        "listings_with_prices": listings_with_prices,

        "missing_prices": missing_prices,

        "missing_timestamps": missing_timestamps,

        "shared_address_listings":
            shared_address_listings,

        "unique_brands": unique_brands

    }
