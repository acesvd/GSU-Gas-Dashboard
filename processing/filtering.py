
"""
GSU Gas Station Dashboard
Station Filtering and Recommendation Logic

Responsibilities:
    - Filter stations by geographic radius
    - Filter stations by gas price availability
    - Filter prices by freshness
    - Identify the cheapest eligible stations
    - Break price ties using distance
    - Calculate overview statistics
    - Calculate average gas prices by brand

This module does NOT make API requests.
This module does NOT contain Streamlit UI code.
"""

import pandas as pd

from services.google_places import STATION_COLUMNS


# ==================================================
# 1. EMPTY DATAFRAME HELPER
# ==================================================

def empty_station_dataframe():
    """
    Return an empty station DataFrame with
    the expected column structure.
    """

    return pd.DataFrame(
        columns=STATION_COLUMNS
    )


# ==================================================
# 2. FILTER STATIONS BY RADIUS
# ==================================================

def stations_within_radius(df, radius):
    """
    Return every station located within the
    selected radius.

    Stations without gas prices are included.

    Parameters
    ----------
    df : pandas.DataFrame
        Cleaned station dataset.

    radius : float
        Maximum distance from campus in miles.

    Returns
    -------
    pandas.DataFrame
        Stations within the selected radius.
    """

    if df is None or df.empty:

        return empty_station_dataframe()


    # ----------------------------------------------
    # CALCULATE DISTANCE CONDITION
    # ----------------------------------------------

    distance = pd.to_numeric(
        df["Distance (miles)"],
        errors="coerce"
    )

    within_radius = distance.between(
        0,
        float(radius),
        inclusive="both"
    )


    # ----------------------------------------------
    # FILTER DATA
    # ----------------------------------------------

    result = df.loc[
        within_radius
    ].copy()


    # ----------------------------------------------
    # SORT BY DISTANCE
    # ----------------------------------------------

    result = result.sort_values(
        "Distance (miles)"
    )


    return result.reset_index(
        drop=True
    )


# ==================================================
# 3. FILTER ELIGIBLE GAS STATIONS
# ==================================================

def filter_eligible_stations(
    df,
    radius,
    max_age
):
    """
    Return stations with eligible regular gas prices.

    A station is eligible when:

        1. It is within the selected radius.
        2. Its regular gas price is available.
        3. Its gas price is greater than zero.
        4. Its price age is between 0 and max_age.

    Parameters
    ----------
    df : pandas.DataFrame
        Cleaned station dataset.

    radius : float
        Selected radius in miles.

    max_age : float
        Maximum eligible price age in hours.

    Returns
    -------
    pandas.DataFrame
        Eligible stations sorted by price,
        then by distance.
    """

    # ----------------------------------------------
    # FILTER BY RADIUS
    # ----------------------------------------------

    nearby = stations_within_radius(
        df=df,
        radius=radius
    )


    if nearby.empty:

        return empty_station_dataframe()


    # ----------------------------------------------
    # PREPARE NUMERIC VALUES
    # ----------------------------------------------

    prices = pd.to_numeric(
        nearby["Regular Price"],
        errors="coerce"
    )

    price_ages = pd.to_numeric(
        nearby["Price Age (hours)"],
        errors="coerce"
    )


    # ----------------------------------------------
    # CHECK PRICE AVAILABILITY
    # ----------------------------------------------

    valid_price = (
        prices.notna()
        & (prices > 0)
    )


    # ----------------------------------------------
    # CHECK PRICE FRESHNESS
    # ----------------------------------------------

    recent_price = price_ages.between(
        0,
        float(max_age),
        inclusive="both"
    )


    # ----------------------------------------------
    # APPLY ELIGIBILITY REQUIREMENTS
    # ----------------------------------------------

    eligible = nearby.loc[

        valid_price
        & recent_price

    ].copy()


    # ----------------------------------------------
    # SORT BY PRICE AND DISTANCE
    # ----------------------------------------------

    eligible = eligible.sort_values(

        by=[
            "Regular Price",
            "Distance (miles)"
        ],

        ascending=[
            True,
            True
        ]

    )


    return eligible.reset_index(
        drop=True
    )


# ==================================================
# 4. IDENTIFY CHEAPEST STATIONS
# ==================================================

def get_cheapest_stations(eligible_df):
    """
    Return all stations tied for the lowest
    eligible regular gas price.

    Stations are sorted by distance so that
    the closest tied station appears first.

    Parameters
    ----------
    eligible_df : pandas.DataFrame
        Already-filtered eligible stations.

    Returns
    -------
    pandas.DataFrame
        Stations offering the lowest price.
    """

    if eligible_df is None or eligible_df.empty:

        return empty_station_dataframe()


    # ----------------------------------------------
    # IDENTIFY LOWEST PRICE
    # ----------------------------------------------

    lowest_price = eligible_df[
        "Regular Price"
    ].min()


    # ----------------------------------------------
    # HANDLE FLOATING-POINT PRECISION
    # ----------------------------------------------

    # Use a small tolerance so equivalent prices
    # are recognized as ties.

    price_difference = (
        eligible_df["Regular Price"]
        - lowest_price
    ).abs()

    cheapest = eligible_df.loc[
        price_difference <= 0.000001
    ].copy()


    # ----------------------------------------------
    # SORT TIED STATIONS BY DISTANCE
    # ----------------------------------------------

    cheapest = cheapest.sort_values(
        ["Distance (miles)", "Place ID"]
    )


    return cheapest.reset_index(
        drop=True
    )


# ==================================================
# 5. IDENTIFY THE BEST STATION
# ==================================================

def get_best_station(eligible_df):
    """
    Select the closest station offering the
    lowest eligible regular gas price.

    Returns
    -------
    pandas.Series or None
        Best station record.
    """

    cheapest = get_cheapest_stations(
        eligible_df
    )


    if cheapest.empty:

        return None


    # The cheapest stations are already sorted
    # by distance.
    return cheapest.iloc[0]


# ==================================================
# 6. CALCULATE OVERVIEW METRICS
# ==================================================

def summarize_stations(
    df,
    eligible_df,
    radius
):
    """
    Calculate overview metrics for the
    selected search radius.

    Parameters
    ----------
    df : pandas.DataFrame
        Complete cleaned station dataset.

    eligible_df : pandas.DataFrame
        Stations satisfying all eligibility rules.

    radius : float
        Selected radius in miles.

    Returns
    -------
    dict
        Overview statistics.
    """

    # ----------------------------------------------
    # COUNT STATIONS WITHIN RADIUS
    # ----------------------------------------------

    nearby = stations_within_radius(
        df=df,
        radius=radius
    )

    stations_found = len(nearby)


    # ----------------------------------------------
    # COUNT ELIGIBLE STATIONS
    # ----------------------------------------------

    eligible_count = (
        len(eligible_df)
        if eligible_df is not None
        else 0
    )


    # ----------------------------------------------
    # IDENTIFY CHEAPEST STATIONS
    # ----------------------------------------------

    cheapest = get_cheapest_stations(
        eligible_df
    )


    # ----------------------------------------------
    # LOWEST PRICE
    # ----------------------------------------------

    if cheapest.empty:

        lowest_price = None

        best_station = None

        tie_count = 0

    else:

        lowest_price = float(
            cheapest.iloc[0]["Regular Price"]
        )

        best_station = cheapest.iloc[0].to_dict()

        tie_count = len(cheapest)


    # ----------------------------------------------
    # RETURN METRICS
    # ----------------------------------------------

    return {

        "stations_found": stations_found,

        "eligible_count": eligible_count,

        "lowest_price": lowest_price,

        "best_station": best_station,

        "tie_count": tie_count

    }


# ==================================================
# 7. BRAND PRICE SUMMARY
# ==================================================

def summarize_brand_prices(eligible_df):
    """
    Calculate average regular gas prices
    for each brand.

    Only stations with eligible prices
    are included.

    Parameters
    ----------
    eligible_df : pandas.DataFrame
        Eligible station dataset.

    Returns
    -------
    pandas.DataFrame
        Brand-level price statistics.
    """

    if eligible_df is None or eligible_df.empty:

        return pd.DataFrame(
            columns=[
                "Brand",
                "Regular Price",
                "Station Count"
            ]
        )


    # ----------------------------------------------
    # GROUP STATIONS BY BRAND
    # ----------------------------------------------

    brand_summary = (

        eligible_df.groupby(
            "Brand",
            as_index=False
        )

        .agg(
            **{
                "Regular Price": (
                    "Regular Price",
                    "mean"
                ),

                "Station Count": (
                    "Regular Price",
                    "count"
                )
            }
        )

    )


    # ----------------------------------------------
    # SORT BY AVERAGE PRICE
    # ----------------------------------------------

    brand_summary = brand_summary.sort_values(
        "Regular Price"
    )


    return brand_summary.reset_index(
        drop=True
    )
