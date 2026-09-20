"""Cost trade-off: sweep warehouse counts and find where rent and delivery balance."""

import streamlit as st

from core.tradeoff import recommend_k, tradeoff_curve
from ui.charts import CHART_CONFIG, tradeoff_chart
from ui.components import button, card, card_header, kpi_grid, page_header, skeleton_block, stretch
from ui.format import inr
from ui.state import STATUS_PILLS, get_data, plan_state
from ui.views import require_data


def _run(df, cfg, k_min: int, k_max: int) -> None:
    placeholder = skeleton_block(420)
    try:
        with st.spinner(f"Optimizing {k_max - k_min + 1} network designs\u2026"):
            curve = tradeoff_curve(
                df, k_min, k_max,
                capacity_per_warehouse=cfg["capacity_per_warehouse"],
                max_radius_km=cfg["max_radius_km"],
                cost_per_warehouse=cfg["cost_per_warehouse"],
                fuel_index=cfg["fuel_index"],
                priority=cfg["priority"],
            )
    except Exception as exc:  # noqa: BLE001
        placeholder.empty()
        st.error("The analysis could not be calculated. Check your data and settings.", icon=":material/error:")
        with st.expander("Technical details"):
            st.code(str(exc))
        return
    placeholder.empty()
    st.session_state.tradeoff_curve = curve
    st.toast("Analysis complete", icon=":material/check_circle:")


def _show(curve) -> None:
    rec = recommend_k(curve)
    kpi_grid([
        {"label": "Recommended warehouses", "value": str(rec["k"]), "tone": "positive" if rec["feasible"] else None},
        {"label": "Total cost at that point", "value": f"{inr(rec['total_cost'])}/day"},
        {"label": "Delivery share", "value": f"{inr(rec['delivery_cost'])}/day"},
        {"label": "Infrastructure share", "value": f"{inr(rec['infrastructure_cost'])}/day"},
    ], cols=4)

    with card("chart"):
        card_header("Cost by number of warehouses",
                    "Delivery cost falls as you add warehouses; rent rises. The lowest total is the sweet spot.")
        stretch(st.plotly_chart, tradeoff_chart(curve, rec), config=CHART_CONFIG, theme=None, key="to_chart")

    if not rec["any_feasible"]:
        st.error("No warehouse count in this range serves every neighborhood within your capacity and radius limits. "
                 "Widen the range, raise capacity, or increase the radius.", icon=":material/warning:")
    elif rec["marginal"]:
        m = rec["marginal"]
        verdict = "is not worth building" if m["net"] >= 0 else "would still pay for itself"
        st.info(f"Warehouse #{m['next_k']} {verdict}: it adds about {inr(m['extra_infra'])}/day in rent but saves "
                f"{inr(m['delivery_saved'])}/day in delivery, a net {inr(m['net'], signed=True)}/day. "
                "All figures are estimates.", icon=":material/info:")
    else:
        st.info("Extend the top of the range to test whether another warehouse would still pay off.",
                icon=":material/info:")

    with st.expander("Full results table"):
        table = curve.rename(columns={
            "warehouses": "Warehouses", "delivery_cost": "Delivery (\u20b9/day)",
            "infrastructure_cost": "Infrastructure (\u20b9/day)", "penalty_cost": "Unserved penalty (\u20b9/day)",
            "total_cost": "Total (\u20b9/day)", "distance_km": "Distance (km)",
            "avg_delivery_minutes": "Avg. delivery (min)", "co2_kg": "CO\u2082 (kg)", "fuel_litres": "Fuel (L)",
            "feasible": "Feasible", "unserved_orders": "Unserved orders",
        }).round(0)
        stretch(st.dataframe, table, hide_index=True)


def render() -> None:
    page_header("Cost trade-off",
                "More warehouses mean cheaper deliveries but higher rent. GRIDPOINT re-runs the full optimization "
                "for each count and shows where the two balance.", status=STATUS_PILLS[plan_state()])
    if not require_data():
        return
    df, cfg = get_data(), st.session_state.config

    with card("inputs"):
        c1, c2 = st.columns([2, 1], gap="large", vertical_alignment="bottom")
        with c1:
            max_k = min(10, len(df))
            if max_k >= 2:
                k_min, k_max = st.slider("Warehouse counts to test", 1, max_k, (1, min(6, max_k)), key="to_range")
            else:
                k_min = k_max = 1
                st.caption("With one neighborhood there is only one option to test.")
        with c2:
            run = button("Run trade-off analysis", key="to_run", kind="primary", icon=":material/play_arrow:")
        st.caption(f"Uses your current settings: {int(cfg['capacity_per_warehouse']):,} orders/day capacity, "
                   f"{cfg['max_radius_km']:g} km radius, {inr(cfg['cost_per_warehouse'])} rent per month.")

    st.write("")
    if run:
        _run(df, cfg, k_min, k_max)
    curve = st.session_state.get("tradeoff_curve")
    if curve is None:
        st.info("Choose a range, then run the analysis.", icon=":material/info:")
        return
    _show(curve)


render()
