"""Disruption mode: knock a warehouse offline and see the recovery plan."""

import streamlit as st

from core.explain import explain_disruption
from core.optimizer import simulate_disruption
from ui.charts import CHART_CONFIG
from ui.components import button, card, card_header, kpi_grid, legend, page_header, stretch
from ui.format import inr
from ui.maps import build_network_map
from ui.state import STATUS_PILLS, plan_state
from ui.theme import DANGER, UNSERVED_COLOR, WAREHOUSE_COLORS
from ui.views import require_result, stale_banner


def _simulate(df, cfg, result, failed_id: str) -> None:
    try:
        with st.spinner("Simulating failure\u2026"):
            outcome = simulate_disruption(
                df, result, failed_id,
                capacity_per_warehouse=cfg["capacity_per_warehouse"],
                max_radius_km=cfg["max_radius_km"],
                cost_per_warehouse=cfg["cost_per_warehouse"],
                fuel_index=cfg["fuel_index"],
            )
    except Exception as exc:  # noqa: BLE001
        st.error("The simulation could not be calculated. Check your data and settings.", icon=":material/error:")
        with st.expander("Technical details"):
            st.code(str(exc))
        return
    st.session_state.disruption = {"failed": failed_id, "outcome": outcome}
    if "error" not in outcome:
        st.toast("Simulation complete", icon=":material/check_circle:")


def _show(df, result) -> None:
    data = st.session_state.get("disruption")
    if not data:
        st.info("Choose a warehouse and run the simulation to see the impact and the recovery plan.",
                icon=":material/info:")
        return
    failed_id, outcome = data["failed"], data["outcome"]
    if "error" in outcome:
        st.error(outcome["error"], icon=":material/error:")
        return

    st.error(f"{failed_id} is offline.", icon=":material/error:")
    kpi_grid([
        {"label": "Orders affected", "value": f"{outcome['affected_orders']:,}", "sub": "Per day"},
        {"label": "Neighborhoods affected", "value": str(len(outcome["affected_neighborhoods"]))},
        {"label": "Extra cost", "value": f"{inr(outcome['additional_daily_cost'])}/day",
         "tone": "negative" if outcome["additional_daily_cost"] > 0.5 else None,
         "sub": f"{outcome['additional_distance_km']:+.1f} km of daily distance"},
    ], cols=3)
    st.info(explain_disruption(outcome), icon=":material/lightbulb:")

    new_net = outcome["new_network"]
    offline = next((w for w in result["warehouses"] if w["warehouse_id"] == failed_id), None)
    with card("map"):
        card_header("Network after the failure",
                    "Affected neighborhoods are reassigned to the surviving warehouses within capacity and radius limits.")
        fig = build_network_map(df, new_net, offline=offline, height=460)
        stretch(st.plotly_chart, fig, config=CHART_CONFIG, theme=None, key="dis_map")
        items = [("hub", "Surviving warehouse"), ("dots", "Neighborhood, coloured by its warehouse", WAREHOUSE_COLORS[:3]),
                 ("dot", f"{failed_id} (offline)", DANGER)]
        if outcome["still_unserved_ids"]:
            items.append(("dot", "Unserved neighborhood", UNSERVED_COLOR))
        legend(items)

    st.markdown("**Recovery plan**")
    if outcome["reassigned_to"]:
        st.write(f"Affected neighborhoods move to: {', '.join(outcome['reassigned_to'])}.")
    else:
        st.write("No surviving warehouse has room to take on the affected neighborhoods.")
    if outcome["still_unserved_ids"]:
        st.warning(f"Still unserved after reassignment: {', '.join(outcome['still_unserved_ids'])}. "
                   "Consider extra capacity or a backup facility for resilience.", icon=":material/warning:")


def render() -> None:
    page_header("Disruption mode", "Simulate a warehouse going offline and see how the network recovers.",
                status=STATUS_PILLS[plan_state()])
    if not require_result("Run an optimization first. Disruptions are simulated against your current plan."):
        return
    stale_banner()

    df = st.session_state.neighborhoods_df
    cfg, result = st.session_state.config, st.session_state.optimized_result
    ids = [w["warehouse_id"] for w in result["warehouses"]]

    with card("pick"):
        card_header("Choose what fails", "Pick a warehouse to take offline.")
        c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
        with c1:
            failed = st.selectbox("Warehouse to take offline", ids, key="dis_pick")
        with c2:
            run = button("Simulate failure", key="dis_run", kind="primary", icon=":material/play_arrow:",
                         disabled=len(ids) < 2,
                         help="A network needs at least two warehouses to simulate a failure." if len(ids) < 2 else None)
    st.write("")
    if run:
        _simulate(df, cfg, result, failed)
    _show(df, result)


render()
