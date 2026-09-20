"""Locations (step 1): load neighborhoods, then see where demand is."""

import numpy as np
import pandas as pd
import streamlit as st

from core.data_model import REQUIRED_COLUMNS, load_demo_data, validate_neighborhoods_df
from ui.charts import CHART_CONFIG
from ui.components import button, card, card_header, kpi_grid, legend, page_header, stepper, stretch
from ui.maps import build_area_map, build_demand_map
from ui.state import STATUS_PILLS, flash, get_data, has_result, plan_state
from ui.theme import TRAFFIC_COLORS
from ui.views import nav_button

TRAFFIC_OPTIONS = ["Low", "Medium", "High"]


def _template_csv() -> str:
    """A tiny valid example (first two demo rows) for people who want to start from a file."""
    return load_demo_data()[REQUIRED_COLUMNS].head(2).to_csv(index=False)


def _apply(new_df: pd.DataFrame, message: str) -> None:
    st.session_state.neighborhoods_df = new_df
    flash("success", message)
    st.rerun()


def _demo_tab(df) -> None:
    st.markdown("A fictional Bengaluru-style city with 12 neighborhoods and about 14,800 orders a day. "
                "Good for seeing how the tool works before you bring your own data.")
    if button("Load demo data", key="loc_demo", kind="secondary" if df is not None else "primary",
              icon=":material/database:"):
        _apply(load_demo_data(), "Demo data loaded")


def _upload_tab() -> None:
    st.markdown("Upload a CSV with one row per neighborhood. **All six columns are required.**")
    st.caption("Columns: name, lat, lon, area_m2, daily_orders, traffic_level (Low, Medium or High).")
    uploaded = st.file_uploader("CSV file", type=["csv"], key="loc_upload", label_visibility="collapsed")
    st.download_button("Download a CSV template", data=_template_csv(), file_name="gridpoint_template.csv",
                       mime="text/csv", icon=":material/download:", key="loc_template")
    if uploaded is None:
        return
    # Only apply a file once. Otherwise a still-attached file would overwrite
    # demo or manual data every time the page reruns.
    signature = (uploaded.name, uploaded.size)
    if st.session_state.get("_last_upload") == signature:
        return
    try:
        parsed = validate_neighborhoods_df(pd.read_csv(uploaded))
    except ValueError as exc:
        st.error(str(exc), icon=":material/error:")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError):
        st.error("That file could not be read as a CSV. Check that it is comma-separated and saved as UTF-8.",
                 icon=":material/error:")
    else:
        st.session_state["_last_upload"] = signature
        _apply(parsed, f"Loaded {len(parsed)} neighborhoods")


def _manual_tab(df) -> None:
    st.markdown("Add or edit rows, then save. Fields marked required must be filled in.")
    start = df[REQUIRED_COLUMNS].copy() if df is not None else pd.DataFrame(columns=REQUIRED_COLUMNS)
    edited = stretch(
        st.data_editor, start, num_rows="dynamic", hide_index=True, key="loc_editor",
        column_config={
            "name": st.column_config.TextColumn("Neighborhood", required=True, help="Any name you will recognise."),
            "lat": st.column_config.NumberColumn("Latitude", required=True, min_value=-90.0, max_value=90.0,
                                                 format="%.4f", help="Decimal degrees, e.g. 12.9716"),
            "lon": st.column_config.NumberColumn("Longitude", required=True, min_value=-180.0, max_value=180.0,
                                                 format="%.4f", help="Decimal degrees, e.g. 77.5946"),
            "area_m2": st.column_config.NumberColumn("Area (m\u00b2)", required=True, min_value=1, format="%d"),
            "daily_orders": st.column_config.NumberColumn("Orders per day", required=True, min_value=0, step=1,
                                                          format="%d"),
            "traffic_level": st.column_config.SelectboxColumn("Traffic", required=True, options=TRAFFIC_OPTIONS),
        },
    )
    # Validate as they type so problems are named before they press Save.
    rows = edited.dropna(how="all")
    problem, cleaned = None, None
    try:
        cleaned = validate_neighborhoods_df(rows)
    except ValueError as exc:
        problem = str(exc)
    if problem and len(rows) > 0:
        st.warning(problem, icon=":material/warning:")
    elif cleaned is not None:
        st.caption(f"{len(cleaned)} neighborhood{'s' if len(cleaned) != 1 else ''} ready to save.")
    if button("Save neighborhoods", key="loc_save", kind="primary", icon=":material/save:",
              disabled=cleaned is None, help=None if cleaned is not None else "Fix the issue above to save."):
        _apply(cleaned, f"Saved {len(cleaned)} neighborhoods")


def render() -> None:
    df = get_data()
    stepper("locations", {"locations": df is not None, "optimization": has_result()})
    page_header(
        "Locations",
        "Load the neighborhoods you deliver to. Each one needs a position, an area, daily orders and a traffic level.",
        status=STATUS_PILLS[plan_state()],
    )

    with card("source"):
        card_header("Data source", "Choose one. Loading new data replaces the current neighborhoods.")
        demo, upload, manual = st.tabs(["Demo data", "Upload CSV", "Enter manually"])
        with demo:
            _demo_tab(df)
        with upload:
            _upload_tab()
        with manual:
            _manual_tab(df)

    df = get_data()
    if df is None:
        st.info("Once you load neighborhoods, a map of your demand appears here.", icon=":material/info:")
        return

    # --- Summary --------------------------------------------------------------
    total = int(df["daily_orders"].sum())
    top = df.loc[df["daily_orders"].idxmax()]
    top_n = max(1, int(np.ceil(len(df) * 0.2)))
    concentration = df["daily_orders"].sort_values(ascending=False).head(top_n).sum() / total * 100 if total else 0
    st.write("")
    kpi_grid([
        {"label": "Neighborhoods", "value": f"{len(df):,}"},
        {"label": "Orders per day", "value": f"{total:,}", "sub": f"{total / len(df):,.0f} per neighborhood on average"},
        {"label": "Busiest neighborhood", "value": str(top["name"]), "sub": f"{int(top['daily_orders']):,} orders per day",
         "text": True},
        {"label": "Demand concentration", "value": f"{concentration:.0f}%",
         "sub": f"From the top {top_n} neighborhood{'s' if top_n != 1 else ''}",
         "help": "Share of all orders that come from the top 20% of neighborhoods by demand."},
    ], cols=4)

    # --- Map ------------------------------------------------------------------
    with card("map"):
        card_header("Where your demand is",
                    "Bubble size shows orders per day. Colour shows how congested the neighborhood's roads are. "
                    "Hover for details.")
        map_tab, area_tab = st.tabs(["Map", "Area view"])
        with map_tab:
            stretch(st.plotly_chart, build_demand_map(df), config=CHART_CONFIG, theme=None, key="loc_map")
            legend([("dot", f"{lvl} traffic", TRAFFIC_COLORS[lvl]) for lvl in TRAFFIC_OPTIONS])
        with area_tab:
            stretch(st.plotly_chart, build_area_map(df), config=CHART_CONFIG, theme=None, key="loc_area")
            st.caption("Patch size follows each neighborhood's area; darker means more orders per day. "
                       "Shapes are illustrative, not survey boundaries.")

    with st.expander("View neighborhood data"):
        show = df.drop(columns=["id"], errors="ignore").rename(columns={
            "name": "Neighborhood", "lat": "Latitude", "lon": "Longitude", "area_m2": "Area (m\u00b2)",
            "daily_orders": "Orders/day", "traffic_level": "Traffic"})
        stretch(st.dataframe, show, hide_index=True)

    st.write("")
    _, cta = st.columns([2.2, 1])
    with cta:
        nav_button("Continue to Optimization", "optimization", key="loc_next", kind="primary",
                   icon=":material/arrow_forward:")


render()
