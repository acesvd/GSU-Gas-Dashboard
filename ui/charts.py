
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from processing.filtering import summarize_brand_prices


# ============================================================
# 1. CHART CONFIGURATION
# ============================================================

# Keep brand colors consistent across all charts.

BRAND_COLORS = {
    "QuikTrip": "#1565C0",
    "Chevron": "#64B5F6",
    "Texaco": "#EF5350",
    "Shell": "#FFB74D",
    "Exxon": "#26A69A",
    "Mobil": "#66BB6A",
    "BP": "#FB8C00",
    "ARCO": "#AB47BC",
    "Citgo": "#EC407A",
    "Amoco": "#8D6E63",
}

CHART_TEMPLATE = "plotly_white"


# ============================================================
# 2. EMPTY CHART PLACEHOLDER
# ============================================================

def empty_chart(title, height=350):
    """
    Create an empty chart placeholder.

    Used when:
    - The dashboard first opens.
    - Design preview is enabled.
    - No stations meet the selected filters.
    """

    fig = go.Figure()

    fig.update_layout(
        title=title,
        template=CHART_TEMPLATE,
        height=height,

        xaxis=dict(
            visible=False,
            showgrid=False,
        ),

        yaxis=dict(
            visible=False,
            showgrid=False,
        ),

        annotations=[
            dict(
                text="No data loaded",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(
                    size=16,
                    color="gray",
                ),
            )
        ],

        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20,
        ),
    )

    return fig


# ============================================================
# 3. PRICE PER GALLON BY STATION
# ============================================================

def create_station_price_chart(eligible_df):
    """
    Create a horizontal bar chart comparing gas
    prices at individual stations.

    Each row gets a unique category label so that
    multiple stations with the same brand name
    DO NOT get stacked together.
    """

    title = "Price per Gallon by Station"

    if eligible_df is None or eligible_df.empty:
        return empty_chart(title)

    chart_df = (
        eligible_df
        .sort_values(
            by=[
                "Regular Price",
                "Distance (miles)",
            ],
            ascending=[
                True,
                True,
            ],
        )
        .copy()
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Create a unique display label for every station.
    #
    # Example:
    # Chevron — 0.86 mi (#1)
    # Chevron — 1.72 mi (#2)
    #
    # The numbered suffix guarantees that labels remain
    # unique, even if brand and distance are identical.
    # --------------------------------------------------------

    chart_df["_station_label"] = [
        (
            f"{row['Station']} — "
            f"{row['Distance (miles)']:.2f} mi "
            f"(#{index + 1})"
        )
        for index, row in chart_df.iterrows()
    ]

    # Preserve the intended price ranking.
    station_order = chart_df["_station_label"].tolist()

    # Allow enough height to show each station separately.
    chart_height = max(
        400,
        150 + 38 * len(chart_df),
    )

    fig = px.bar(
        chart_df,

        x="Regular Price",
        y="_station_label",

        color="Brand",
        color_discrete_map=BRAND_COLORS,

        orientation="h",
        barmode="group",

        hover_name="Station",

        hover_data={
            "_station_label": False,
            "Address": True,
            "Distance (miles)": ":.2f",
            "Price Age (hours)": ":.1f",
            "Place ID": False,
        },

        title=title,

        labels={
            "Regular Price": "Regular Gas Price ($/gal)",
            "_station_label": "Gas Station",
        },

        template=CHART_TEMPLATE,
        height=chart_height,
    )

    # Display the cheapest station at the top.
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=station_order[::-1],
    )

    # Add an individual price label to each bar.
    fig.update_traces(
        texttemplate="$%{x:.2f}",
        textposition="outside",
        cliponaxis=False,
    )

    # Leave room for the labels at the end of each bar.
    max_price = chart_df["Regular Price"].max()

    fig.update_xaxes(
        range=[
            0,
            max_price * 1.20,
        ],
        tickprefix="$",
        tickformat=".2f",
    )

    fig.update_layout(
        legend_title_text="Brand",
        bargap=0.20,

        margin=dict(
            l=30,
            r=60,
            t=60,
            b=50,
        ),
    )

    return fig


# ============================================================
# 4. GAS PRICE VS. DISTANCE
# ============================================================

def create_price_distance_chart(eligible_df):
    """
    Create a scatter plot comparing station distance
    with regular gas price.

    Each dot represents one individual station.
    """

    title = "Gas Price vs. Distance"

    if eligible_df is None or eligible_df.empty:
        return empty_chart(title)

    chart_df = eligible_df.copy()

    fig = px.scatter(
        chart_df,

        x="Distance (miles)",
        y="Regular Price",

        color="Brand",
        color_discrete_map=BRAND_COLORS,

        hover_name="Station",

        hover_data={
            "Address": True,
            "Price Age (hours)": ":.1f",
            "Place ID": False,
        },

        title=title,

        labels={
            "Distance (miles)": "Distance from Campus (miles)",
            "Regular Price": "Regular Gas Price ($/gal)",
        },

        template=CHART_TEMPLATE,
        height=400,
    )

    fig.update_traces(
        marker=dict(
            size=11,
            opacity=0.85,
            line=dict(
                width=1,
                color="white",
            ),
        )
    )

    fig.update_yaxes(
        tickprefix="$",
        tickformat=".2f",
    )

    fig.update_layout(
        legend_title_text="Brand",

        margin=dict(
            l=40,
            r=20,
            t=60,
            b=50,
        ),
    )

    return fig


# ============================================================
# 5. AVERAGE GAS PRICE BY BRAND
# ============================================================

def create_brand_price_chart(eligible_df):
    """
    Compare average regular gas prices by brand.

    Averages are computed using the already-filtered
    eligible gas stations.
    """

    title = "Average Regular Gas Price by Brand"

    if eligible_df is None or eligible_df.empty:
        return empty_chart(title)

    # Use our processing module for aggregation.
    brand_df = summarize_brand_prices(
        eligible_df
    )

    if brand_df.empty:
        return empty_chart(title)

    # Sort brands from cheapest average to highest.
    brand_df = (
        brand_df
        .sort_values("Regular Price")
        .reset_index(drop=True)
    )

    fig = px.bar(
        brand_df,

        x="Brand",
        y="Regular Price",

        color="Brand",
        color_discrete_map=BRAND_COLORS,

        hover_data={
            "Station Count": True,
        },

        title=title,

        labels={
            "Regular Price": "Average Regular Gas Price ($/gal)",
        },

        template=CHART_TEMPLATE,
        height=400,
    )

    # Display the average price on each bar.
    fig.update_traces(
        texttemplate="$%{y:.2f}",
        textposition="outside",
        cliponaxis=False,
    )

    max_average = brand_df["Regular Price"].max()

    fig.update_yaxes(
        range=[
            0,
            max_average * 1.20,
        ],
        tickprefix="$",
        tickformat=".2f",
    )

    fig.update_layout(
        showlegend=False,
        bargap=0.25,

        margin=dict(
            l=40,
            r=20,
            t=60,
            b=50,
        ),
    )

    return fig


# ============================================================
# 6. RENDER DASHBOARD CHARTS
# ============================================================

def render_price_charts(eligible_df):
    """
    Display all gas price comparison charts.

    This is the main function that app.py will call.

    It handles:
    1. Price by individual station
    2. Price vs. distance
    3. Average price by brand
    """

    # --------------------------------------------------------
    # Station-level comparisons
    # --------------------------------------------------------

    st.subheader("Gas Price Comparisons")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:

        fig_station = create_station_price_chart(
            eligible_df
        )

        st.plotly_chart(
            fig_station,
            use_container_width=True,
        )

    with chart_col2:

        fig_distance = create_price_distance_chart(
            eligible_df
        )

        st.plotly_chart(
            fig_distance,
            use_container_width=True,
        )

    # --------------------------------------------------------
    # Brand-level comparison
    # --------------------------------------------------------

    st.subheader("Average Gas Price by Brand")

    fig_brand = create_brand_price_chart(
        eligible_df
    )

    st.plotly_chart(
        fig_brand,
        use_container_width=True,
    )
