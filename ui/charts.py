
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from processing.filtering import (
    summarize_brand_prices,
    get_best_station,
    get_cheapest_stations,
)


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

def empty_chart(height=350):
    """
    Create an empty chart placeholder.

    Used when:
    - The dashboard first opens.
    - Design preview is enabled.
    - No stations meet the selected filters.
    """

    fig = go.Figure()

    fig.update_layout(
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
            t=20,
            b=20,
        ),
    )

    return fig


# ============================================================
# 3. PRICE DISTRIBUTION
# ============================================================


def create_price_distribution_chart(eligible_df):
    """
    Display the frequency of regular gas prices
    across eligible gas stations.
    """

    if eligible_df is None or eligible_df.empty:
        return empty_chart()

    # ----------------------------------------------
    # GROUP STATIONS BY PRICE
    # ----------------------------------------------

    chart_df = (
        eligible_df["Regular Price"]
        .round(2)
        .value_counts()
        .sort_index()
        .rename_axis("Regular Price")
        .reset_index(name="Station Count")
    )

    lowest_price = chart_df["Regular Price"].min()

    # Create readable categorical price labels.
    chart_df["Price Label"] = chart_df[
        "Regular Price"
    ].map(lambda price: f"${price:.2f}")

    # Highlight the lowest price category.
    colors = [
        "#0d9488" if price == lowest_price
        else "#2563eb"
        for price in chart_df["Regular Price"]
    ]

    # ----------------------------------------------
    # CREATE BAR CHART
    # ----------------------------------------------

    fig = px.bar(
        chart_df,

        x="Price Label",
        y="Station Count",

        text="Station Count",

        labels={
            "Price Label": "Regular Gas Price ($/gal)",
            "Station Count": "Number of Stations",
        },

        template=CHART_TEMPLATE,
        height=400,
    )

    # ----------------------------------------------
    # FORMAT BARS AND COUNT LABELS
    # ----------------------------------------------

    fig.update_traces(
        marker_color=colors,

        textposition="outside",

        textfont=dict(
            size=15,
            color="#334155",
        ),

        constraintext="none",

        cliponaxis=False,

        hovertemplate=(
            "Price: %{x}/gal<br>"
            "Stations: %{y}"
            "<extra></extra>"
        ),
    )

    # ----------------------------------------------
    # FORMAT X-AXIS
    # ----------------------------------------------

    fig.update_xaxes(
        type="category",

        categoryorder="array",

        categoryarray=chart_df["Price Label"].tolist(),

        tickfont=dict(
            size=12,
            color="#475569",
        ),

        title_font=dict(
            size=14,
            color="#334155",
        ),

        tickangle=0 if len(chart_df) <= 10 else -45,

        automargin=True,
    )

    # ----------------------------------------------
    # FORMAT Y-AXIS
    # ----------------------------------------------

    fig.update_yaxes(
        rangemode="tozero",

        range=[
            0,
            chart_df["Station Count"].max() * 1.15
        ],

        tickformat="d",

        dtick=1 if chart_df["Station Count"].max() <= 10
        else None,

        tickfont=dict(
            size=12,
            color="#475569",
        ),

        title_font=dict(
            size=14,
            color="#334155",
        ),

        gridcolor="#e2e8f0",
    )

    # ----------------------------------------------
    # OVERALL CHART APPEARANCE
    # ----------------------------------------------

    fig.update_layout(
        showlegend=False,

        bargap=0.25,

        uniformtext=dict(
            minsize=13,
            mode="show",
        ),

        margin=dict(
            l=30,
            r=20,
            t=20,
            b=50,
        ),
    )

    return fig


# ============================================================
# 4. GAS PRICE VS. DISTANCE
# ============================================================


def create_price_distance_chart(eligible_df):
    """
    Compare regular gas prices and distance from
    campus using consistent recommendation colors.

    Each point represents one eligible gas station.
    """

    if eligible_df is None or eligible_df.empty:
        return empty_chart(height=400)

    chart_df = eligible_df.copy()

    # ----------------------------------------------
    # IDENTIFY RECOMMENDATION CATEGORIES
    # ----------------------------------------------

    best_station = get_best_station(chart_df)

    cheapest_stations = get_cheapest_stations(
        chart_df
    )

    best_id = best_station["Place ID"]

    cheapest_ids = set(
        cheapest_stations["Place ID"]
    )

    # Assign the default category.
    chart_df["Recommendation"] = (
        "Other eligible stations"
    )

    # Identify all lowest-price stations.
    chart_df.loc[
        chart_df["Place ID"].isin(cheapest_ids),
        "Recommendation"
    ] = "Other lowest-price options"

    # Identify the single Best Value station.
    chart_df.loc[
        chart_df["Place ID"] == best_id,
        "Recommendation"
    ] = "Best Value"

    # ----------------------------------------------
    # CONFIGURE MARKER APPEARANCE
    # ----------------------------------------------

    marker_styles = {

        "Other eligible stations": {
            "color": "#2563eb",
            "size": 10,
            "symbol": "circle",
            "opacity": 0.65,
        },

        "Other lowest-price options": {
            "color": "#0d9488",
            "size": 12,
            "symbol": "circle",
            "opacity": 0.95,
        },

        "Best Value": {
            "color": "#16a34a",
            "size": 23,
            "symbol": "star",
            "opacity": 1.0,
        },

    }

    # ----------------------------------------------
    # CREATE SCATTERPLOT
    # ----------------------------------------------

    fig = go.Figure()

    # Plot Best Value last so that its marker
    # appears above the other station markers.

    for category, style in marker_styles.items():

        subset = chart_df.loc[
            chart_df["Recommendation"] == category
        ]

        if subset.empty:
            continue

        fig.add_trace(

            go.Scatter(

                x=subset["Distance (miles)"],

                y=subset["Regular Price"],

                mode="markers",

                name=category,

                marker=dict(
                    **style,
                    line=dict(
                        color="white",
                        width=1,
                    ),
                ),

                customdata=subset[
                    [
                        "Station",
                        "Address",
                        "Price Age (hours)",
                    ]
                ].to_numpy(),

                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Price: $%{y:.2f}/gal<br>"
                    "Distance: %{x:.2f} mi<br>"
                    "Updated: %{customdata[2]:.1f} "
                    "hours ago<br>"
                    "%{customdata[1]}"
                    "<extra>%{fullData.name}</extra>"
                ),

            )
        )

    # ----------------------------------------------
    # ADD MINIMUM PRICE REFERENCE LINE
    # ----------------------------------------------

    lowest_price = chart_df["Regular Price"].min()

    fig.add_hline(
        y=lowest_price,
        line_color="#0d9488",
        line_width=1.5,
        line_dash="dot",
        opacity=0.6,
        layer="below",
    )

    # ----------------------------------------------
    # ANNOTATE BEST VALUE STATION
    # ----------------------------------------------

    best_price = float(
        best_station["Regular Price"]
    )

    best_distance = float(
        best_station["Distance (miles)"]
    )

    fig.add_annotation(

        x=best_distance,
        y=best_price,

        text=(
            "<b>Best Value</b><br>"
            f"${best_price:.2f}/gal<br>"
            f"{best_distance:.2f} mi"
        ),

        showarrow=True,

        arrowhead=0,
        arrowwidth=1.5,
        arrowcolor="#16a34a",

        ax=0,
        ay=-65,

        bgcolor="#f0fdf4",
        bordercolor="#86efac",
        borderwidth=1,
        borderpad=6,

        font=dict(
            size=12,
            color="#166534",
        ),

        align="center",

    )

    # ----------------------------------------------
    # FORMAT AXIS RANGES
    # ----------------------------------------------

    highest_price = chart_df[
        "Regular Price"
    ].max()

    price_range = highest_price - lowest_price

    # Maintain readable axis ranges even when
    # every station charges exactly the same price.

    lower_padding = max(
        price_range * 0.10,
        0.03,
    )

    upper_padding = max(
        price_range * 0.15,
        0.08,
    )

    max_distance = chart_df[
        "Distance (miles)"
    ].max()

    # ----------------------------------------------
    # FORMAT X-AXIS
    # ----------------------------------------------

    fig.update_xaxes(

        title_text="Distance from Campus (miles)",

        range=[
            0,
            max_distance + 0.15,
        ],

        tickformat=".1f",

        tickfont=dict(
            size=12,
            color="#475569",
        ),

        title_font=dict(
            size=14,
            color="#334155",
        ),

        gridcolor="#e2e8f0",

        automargin=True,

    )

    # ----------------------------------------------
    # FORMAT Y-AXIS
    # ----------------------------------------------

    fig.update_yaxes(

        title_text="Regular Gas Price ($/gal)",

        range=[
            lowest_price - lower_padding,
            highest_price + upper_padding,
        ],

        tickprefix="$",
        tickformat=".2f",

        tickfont=dict(
            size=12,
            color="#475569",
        ),

        title_font=dict(
            size=14,
            color="#334155",
        ),

        gridcolor="#e2e8f0",

        automargin=True,

    )

    # ----------------------------------------------
    # OVERALL CHART APPEARANCE
    # ----------------------------------------------

    fig.update_layout(

        template=CHART_TEMPLATE,

        height=400,

        legend=dict(

            title_text="",

            orientation="h",

            traceorder="reversed",

            x=0,
            xanchor="left",

            y=-0.25,
            yanchor="top",

            font=dict(size=11),

        ),

        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_color="#334155",
        ),

        margin=dict(
            l=35,
            r=20,
            t=25,
            b=90,
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

    if eligible_df is None or eligible_df.empty:
        return empty_chart()

    # Use our processing module for aggregation.
    brand_df = summarize_brand_prices(
        eligible_df
    )

    if brand_df.empty:
        return empty_chart()

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
            t=20,
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

    st.markdown(
        """
        <style>
          .comparison-header {
            margin: 1.9rem 0 1.1rem 0;
          }
          .comparison-eyebrow {
            color: #2563eb;
            font-size: 0.95rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
          }
          .comparison-title {
            color: #102a43;
            font-size: clamp(2rem, 3vw, 3rem);
            line-height: 1.08;
            letter-spacing: -0.03em;
            margin: 0 0 0.45rem 0;
          }
          .comparison-description {
            color: #64748b;
            font-size: 1.12rem;
            line-height: 1.45;
            max-width: 760px;
            margin: 0;
          }
          .chart-card-label {
            color: #334155;
            font-size: 1.05rem;
            font-weight: 800;
            margin: 0.15rem 0 0.5rem 0;
          }
        </style>
        <div class="comparison-header">
          <div class="comparison-eyebrow">Compare the options</div>
          <h2 class="comparison-title">Gas Price Comparisons</h2>
          <p class="comparison-description">
            See how each station compares on price, and whether a lower
            price is worth the extra distance.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:

        with st.container(border=True):

            st.html(
                '<div class="chart-card-label">'
                'Distribution of Gas Prices'
                '</div>'
            )

            fig_distribution = create_price_distribution_chart(
                eligible_df
            )

            st.plotly_chart(
                fig_distribution,
                width="stretch",
                key="price-distribution-chart",
            )
            
            if eligible_df is not None and not eligible_df.empty:

                displayed_prices = eligible_df["Regular Price"].round(2)

                lowest_price = displayed_prices.min()

                lowest_count = int(
                    displayed_prices.eq(lowest_price).sum()
                )

                total_count = len(eligible_df)

                lowest_percentage = (
                    lowest_count / total_count
                ) * 100

                st.markdown(
                    f"**{lowest_count} of {total_count} eligible stations "
                    f"({lowest_percentage:.0f}%)** offer the lowest "
                    f"displayed price of **${lowest_price:.2f}/gal**."
                )


    with chart_col2:

        with st.container(border=True):

            st.html(
                '<div class="chart-card-label">'
                'Price vs. Distance'
                '</div>'
            )

            fig_distance = create_price_distance_chart(
                eligible_df
            )

            st.plotly_chart(
                fig_distance,
                width="stretch",
                key="price-distance-chart",
            )

            # ------------------------------------------
            # DYNAMIC ANALYTICAL TAKEAWAY
            # ------------------------------------------

            if eligible_df is not None and not eligible_df.empty:

                best_station = get_best_station(
                    eligible_df
                )

                nearest_station = eligible_df.sort_values(
                    [
                        "Distance (miles)",
                        "Regular Price",
                        "Place ID",
                    ]
                ).iloc[0]

                price_difference = (

                    nearest_station["Regular Price"]
                    - best_station["Regular Price"]

                )

                distance_difference = (

                    best_station["Distance (miles)"]
                    - nearest_station["Distance (miles)"]

                )

                best_name = best_station["Station"]

                if (
                    best_station["Place ID"]
                    == nearest_station["Place ID"]
                ):

                    st.markdown(
                        f"**{best_name}** offers the lowest "
                        "eligible price and is also the "
                        "closest eligible station."
                    )

                elif price_difference > 0.000001:

                    st.markdown(
                        f"Traveling approximately "
                        f"**{distance_difference:.2f} miles "
                        f"farther** to {best_name} offers "
                        f"a price reduction of "
                        f"**${price_difference:.2f}/gal** "
                        "compared with the closest eligible "
                        "station."
                    )

                else:

                    st.markdown(
                        "The closest eligible station "
                        "already offers a price equivalent "
                        "to the lowest eligible price."
                    )


    # --------------------------------------------------------
    # Brand-level comparison
    # --------------------------------------------------------

    with st.container(border=True):
        st.markdown(
            '<div class="chart-card-label">Average price by brand</div>',
            unsafe_allow_html=True,
        )

        fig_brand = create_brand_price_chart(
            eligible_df
        )

        st.plotly_chart(
            fig_brand,
            width='stretch',
            key="brand-price-chart",
        )
