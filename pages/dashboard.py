"""Dashboard: the whole plan at a glance, most important numbers first."""

import streamlit as st

from ui.charts import CHART_CONFIG, cost_compare_chart, demand_chart, utilization_chart
from ui.components import (card, card_header, kpi_grid, legend, page_header, savings_panel,
                           stretch, welcome_panel)
from ui.format import inr
from ui.maps import build_demand_map, build_network_map
from ui.metrics import plan_savings
from ui.state import STATUS_PILLS, get_data, has_result, plan_state
from ui.theme import TRAFFIC_COLORS, UNSERVED_COLOR, WAREHOUSE_COLORS
from ui.views import error_banner, infeasible_banner, load_demo_button, nav_button, run_button, stale_banner


def _status_kpi(state: str, result: dict):
    label = STATUS_PILLS[state][1]
    if state == "feasible":
        return {"label": "Optimization status", "value": label, "sub": "Every neighborhood is served",
                "tone": "positive", "text": True}
    if state == "infeasible":
        n = len(result["unserved_ids"])
        return {"label": "Optimization status", "value": label,
                "sub": f"{n} neighborhood{'s' if n != 1 else ''} not served", "tone": "negative", "text": True}
    if state == "stale":
        return {"label": "Optimization status", "value": label,
                "sub": "Data or settings changed since the last run", "text": True}
    return {"label": "Optimization status", "value": label, "sub": "Set options, then run", "text": True}


def render() -> None:
    df = get_data()
    if df is None:
        welcome_panel()
        a, b, _ = st.columns([1.1, 1.1, 1.6])
        with a:
            load_demo_button("welcome_demo", kind="primary")
        with b:
            nav_button("Add your own data", "locations", key="welcome_locations", icon=":material/upload_file:")
        st.caption("Every cost, CO\u2082 and time figure in GRIDPOINT is an estimate from adjustable assumptions.")
        return

    state = plan_state()
    cfg = st.session_state.config
    ready = has_result()
    result = st.session_state.optimized_result if ready else None
    baseline = st.session_state.baseline_result if ready else None

    head, action = st.columns([3, 1.2], vertical_alignment="center")
    with head:
        page_header("Dashboard", "Your warehouse network at a glance.", status=STATUS_PILLS[state])
    with action:
        run_button("dash_run")

    error_banner()
    stale_banner()
    if result:
        infeasible_banner(result)

    # --- KPI row: neighborhoods, orders, warehouses, delivery cost, status -----
    total_orders = int(df["daily_orders"].sum())
    if result:
        warehouses_kpi = {"label": "Warehouses", "value": f"{result['num_warehouses']}",
                          "sub": f"{int(result['warehouses'][0]['capacity']):,} orders/day capacity each"}
        cost_kpi = {"label": "Est. delivery cost", "value": f"{inr(result['total_transport_cost'])}/day",
                    "sub": f"{result['avg_km_per_order']:.1f} km per order on average",
                    "help": "Daily transportation cost of the recommended network: fuel, drivers and vehicle running costs."}
    else:
        warehouses_kpi = {"label": "Warehouses", "value": f"{cfg['num_warehouses']}", "sub": "Planned, not optimized yet"}
        cost_kpi = {"label": "Est. delivery cost", "value": "\u2014", "sub": "Run the optimization to estimate"}
    kpi_grid([
        {"label": "Neighborhoods", "value": f"{len(df):,}", "sub": "In your network"},
        {"label": "Orders per day", "value": f"{total_orders:,}", "sub": "Total demand"},
        warehouses_kpi,
        cost_kpi,
        _status_kpi(state, result),
    ], cols=5)

    # --- Map + savings ---------------------------------------------------
    main, side = st.columns([2, 1], gap="large")
    with main:
        with card("map"):
            if result:
                card_header("Proposed network",
                            "Where to build, and which neighborhoods each warehouse serves. Hover any marker for details.")
                fig = build_network_map(df, result, baseline=baseline, height=460)
                items = [("hub", "Proposed warehouse"),
                         ("dots", "Neighborhood, coloured by its warehouse", WAREHOUSE_COLORS[:3]),
                         ("line", "Delivery assignment", WAREHOUSE_COLORS[0])]
                if not result["feasible"]:
                    items.append(("dot", "Unserved neighborhood", UNSERVED_COLOR))
            else:
                card_header("Neighborhood demand",
                            "Bubble size shows orders per day; colour shows traffic. Run the optimization to see proposed warehouses.")
                fig = build_demand_map(df, height=460)
                items = [("dot", f"{lvl} traffic", TRAFFIC_COLORS[lvl]) for lvl in ("Low", "Medium", "High")]
            stretch(st.plotly_chart, fig, config=CHART_CONFIG, theme=None, key="dash_map")
            legend(items)

    with side:
        if result:
            sv = plan_savings(baseline, result)
            if sv["daily"] >= 0:
                savings_panel("Estimated savings vs. current network", f"{inr(sv['monthly'])} / month",
                              f"{inr(sv['daily'])} per day, {sv['pct']:.0f}% lower total cost than placing "
                              "warehouses in the busiest neighborhoods.", good=True)
            else:
                savings_panel("Compared with the current network", f"{inr(-sv['monthly'])} more / month",
                              f"The optimized layout costs {inr(-sv['daily'])} more per day than the naive one. "
                              "The Results page shows the full comparison.", good=False)
            st.write("")
            with card("util"):
                card_header("Warehouse utilization", "How full each proposed warehouse is against its capacity.")
                stretch(st.plotly_chart, utilization_chart(result), config=CHART_CONFIG, theme=None, key="dash_util")
        else:
            with card("next"):
                card_header("Next step", "Set how many warehouses you want, their capacity and the longest "
                                         "delivery radius, then run the optimization.")
                st.write("")
                nav_button("Set optimization options", "optimization", key="dash_to_opt", kind="primary",
                           icon=":material/tune:")
                nav_button("Review locations", "locations", key="dash_to_loc", icon=":material/pin_drop:")

    # --- Supporting charts -----------------------------------------------
    left, right = st.columns(2, gap="large")
    with left:
        with card("demand"):
            card_header("Demand by neighborhood", "Orders per day, highest first.")
            stretch(st.plotly_chart, demand_chart(df), config=CHART_CONFIG, theme=None, key="dash_demand")
    with right:
        if result:
            with card("cost"):
                card_header("Total cost per day",
                            "Transportation plus rent, as a daily equivalent, compared with the current (naive) layout.")
                stretch(st.plotly_chart, cost_compare_chart(baseline, result), config=CHART_CONFIG,
                        theme=None, key="dash_cost")
                nav_button("See full comparison", "results", key="dash_to_results", icon=":material/arrow_forward:")


render()
