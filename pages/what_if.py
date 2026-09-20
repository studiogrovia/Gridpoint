"""What-if simulator: change assumptions, re-optimize, compare with the current plan."""

import numpy as np
import streamlit as st

from core.optimizer import optimize_network
from ui.charts import CHART_CONFIG
from ui.components import (button, card, card_header, kpi_grid, legend, page_header, skeleton_kpis,
                           stretch)
from ui.format import inr
from ui.maps import build_network_map
from ui.state import STATUS_PILLS, plan_state
from ui.theme import UNSERVED_COLOR, WAREHOUSE_COLORS
from ui.views import require_result

TRAFFIC_SCENARIOS = ["As configured", "All Low", "All Medium", "All High"]


def _delta_tone(delta: float):
    """Costs and distances: up is bad, down is good."""
    if abs(delta) < 0.5:
        return None
    return "negative" if delta > 0 else "positive"


def _run(df, base_cfg, sim_cfg, growth, traffic) -> None:
    sim_df = df.copy()
    if growth != 0:
        sim_df["daily_orders"] = (sim_df["daily_orders"] * (1 + growth / 100)).round().astype(int)
    if traffic != "As configured":
        sim_df["traffic_level"] = traffic.replace("All ", "")
    placeholder = skeleton_kpis(4)
    try:
        with st.spinner("Re-running optimization\u2026"):
            result = optimize_network(
                sim_df,
                num_warehouses=sim_cfg["num_warehouses"],
                capacity_per_warehouse=sim_cfg["capacity_per_warehouse"],
                max_radius_km=sim_cfg["max_radius_km"],
                cost_per_warehouse=sim_cfg["cost_per_warehouse"],
                fuel_index=sim_cfg["fuel_index"],
                priority=sim_cfg["priority"],
            )
    except Exception as exc:  # noqa: BLE001
        placeholder.empty()
        st.error("The scenario could not be calculated. Check the inputs and try again.", icon=":material/error:")
        with st.expander("Technical details"):
            st.code(str(exc))
        return
    placeholder.empty()
    st.session_state.whatif = {"df": sim_df, "result": result, "growth": growth, "traffic": traffic}
    st.toast("Scenario complete", icon=":material/check_circle:")


def _show(base_result: dict) -> None:
    data = st.session_state.get("whatif")
    if not data:
        st.info("Adjust the inputs above, then choose **Run scenario** to compare against your current plan.",
                icon=":material/info:")
        return
    sim, sim_df = data["result"], data["df"]
    d_cost = sim["total_cost"] - base_result["total_cost"]
    d_dist = sim["total_distance_km"] - base_result["total_distance_km"]
    util = float(np.mean([w["utilization"] for w in sim["warehouses"]])) * 100
    st.markdown("#### Scenario vs. current plan")
    kpi_grid([
        {"label": "Warehouses", "value": str(sim["num_warehouses"]),
         "sub": f"Current plan: {base_result['num_warehouses']}"},
        {"label": "Total cost change", "value": f"{inr(d_cost, signed=True)}/day", "tone": _delta_tone(d_cost),
         "sub": f"Scenario total {inr(sim['total_cost'])}/day"},
        {"label": "Distance change", "value": f"{d_dist:+,.0f} km/day", "tone": _delta_tone(d_dist)},
        {"label": "Avg. utilization", "value": f"{util:.0f}%"},
    ], cols=4)

    if not sim["feasible"]:
        st.error(f"{len(sim['unserved_ids'])} neighborhood(s) go unserved in this scenario "
                 f"({sim['unserved_orders']:,} orders/day).", icon=":material/warning:")

    with card("map"):
        card_header("Recommended layout for this scenario",
                    f"Demand {data['growth']:+d}%, traffic: {data['traffic'].lower()}.")
        stretch(st.plotly_chart, build_network_map(sim_df, sim, height=440), config=CHART_CONFIG, theme=None,
                key="wi_map")
        items = [("hub", "Proposed warehouse"), ("dots", "Neighborhood, coloured by its warehouse", WAREHOUSE_COLORS[:3])]
        if not sim["feasible"]:
            items.append(("dot", "Unserved neighborhood", UNSERVED_COLOR))
        legend(items)
    for w in sim["warehouses"]:
        st.caption(f"{w['warehouse_id']}: {w['lat']:.4f}, {w['lon']:.4f} \u2014 {w['assigned_orders']:,} orders/day, "
                   f"{w['utilization'] * 100:.0f}% utilization")


def render() -> None:
    page_header("What-if simulator",
                "Change demand, costs or network size and see how the recommended layout responds. "
                "Your current plan stays untouched.", status=STATUS_PILLS[plan_state()])
    if not require_result("Run an optimization first. Scenarios are compared against your current plan."):
        return

    df = st.session_state.neighborhoods_df
    base_cfg, base_result = st.session_state.config, st.session_state.optimized_result
    sim_cfg = base_cfg.copy()
    max_k = min(6, len(df))

    with card("inputs"):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("**Demand and network**")
            if max_k >= 2:
                sim_cfg["num_warehouses"] = st.slider("Number of warehouses", 1, max_k,
                                                      min(int(base_cfg["num_warehouses"]), max_k), key="wi_k")
            growth = st.slider("Demand growth (%)", -50, 200, 0, step=5, key="wi_growth",
                               help="Scales every neighborhood's daily orders.")
            sim_cfg["max_radius_km"] = st.slider("Longest delivery distance (km)", 1.0, 40.0,
                                                 float(base_cfg["max_radius_km"]), step=0.5, key="wi_radius")
        with c2:
            st.markdown("**Costs and traffic**")
            sim_cfg["fuel_index"] = st.slider("Fuel price index", 0.5, 2.0, float(base_cfg["fuel_index"]),
                                              step=0.05, key="wi_fuel", help="1.0 is today's baseline price.")
            sim_cfg["cost_per_warehouse"] = st.number_input(
                "Rent per warehouse (\u20b9 per month)", min_value=0, step=10_000,
                value=int(base_cfg["cost_per_warehouse"]), key="wi_rent")
            traffic = st.selectbox("Traffic scenario", TRAFFIC_SCENARIOS, key="wi_traffic",
                                   help="Overrides the traffic level of every neighborhood.")
        run = button("Run scenario", key="wi_run", kind="primary", icon=":material/play_arrow:")

    st.write("")
    if run:
        _run(df, base_cfg, sim_cfg, growth, traffic)
    _show(base_result)


render()
