"""Results (step 3): the recommended network and why it beats the naive one."""

import streamlit as st

from core.explain import explain_warehouse
from ui.charts import CHART_CONFIG
from ui.components import (card, card_header, comparison_table, delta_chip, kpi_grid, legend,
                           page_header, stepper, stretch, summary_rows)
from ui.format import inr
from ui.maps import build_network_map
from ui.metrics import plan_savings
from ui.state import STATUS_PILLS, get_data, has_result, plan_state
from ui.tables import assignments_frame
from ui.theme import CURRENT_SITE_COLOR, UNSERVED_COLOR, WAREHOUSE_COLORS
from ui.views import (error_banner, infeasible_banner, nav_button, require_result, run_button,
                      stale_banner)


def _kpis(result: dict, baseline: dict) -> None:
    sv = plan_savings(baseline, result)
    if sv["daily"] >= 0:
        hero = {"label": "Estimated monthly savings", "value": inr(sv["monthly"]), "hero": True, "tone": "positive",
                "sub": f"{inr(sv['daily'])} per day, {sv['pct']:.0f}% below the current layout",
                "help": "Total cost (transport + rent + unserved-order penalty) of the naive layout minus GRIDPOINT's, times 30."}
    else:
        hero = {"label": "Compared with current layout", "value": f"{inr(-sv['monthly'])} more", "hero": True,
                "tone": "negative", "sub": f"{inr(-sv['daily'])} more per day than the naive layout"}
    kpi_grid([
        hero,
        {"label": "Distance per order", "value": f"{result['avg_km_per_order']:.1f} km",
         "sub": f"{sv['dist_pct']:.0f}% shorter than current" if sv["dist_pct"] >= 0 else f"{-sv['dist_pct']:.0f}% longer than current",
         "help": "Order-weighted average road distance from warehouse to neighborhood."},
        {"label": "Avg. delivery time", "value": f"{result['avg_delivery_minutes']:.0f} min",
         "sub": f"Slowest lane {result['worst_delivery_minutes']:.0f} min",
         "help": "Includes traffic and handling time, weighted by orders."},
        {"label": "Warehouses", "value": str(result["num_warehouses"]),
         "sub": f"{sv['avg_util']:.0f}% average utilization"},
    ], cols=5)
    kpi_grid([
        {"label": "Transportation", "value": f"{inr(result['total_transport_cost'])}/day"},
        {"label": "Infrastructure", "value": f"{inr(result['total_infra_cost'])}/month"},
        {"label": "Fuel", "value": f"{result['total_fuel_litres']:,.0f} L/day"},
        {"label": "CO\u2082", "value": f"{result['total_co2_kg']:,.0f} kg/day"},
    ], cols=4, compact=True)


def _map_card(df, result, baseline) -> None:
    with card("map"):
        card_header("Recommended network",
                    "Each colour is one warehouse and the neighborhoods it serves. Hover any marker for details.")
        t1, t2, _ = st.columns([1, 1, 1.4])
        with t1:
            show_lines = st.toggle("Delivery assignments", value=True, key="res_lines")
        with t2:
            show_current = st.toggle("Current sites", value=False, key="res_current",
                                     help="Show where the naive layout would put warehouses.")
        fig = build_network_map(df, result, baseline=baseline, show_lines=show_lines,
                                show_current=show_current, height=520)
        stretch(st.plotly_chart, fig, config=CHART_CONFIG, theme=None, key="res_map")
        items = [("hub", "Proposed warehouse (larger = fuller)"),
                 ("dots", "Neighborhood, coloured by its warehouse (larger = more orders)", WAREHOUSE_COLORS[:3])]
        if show_lines:
            items.append(("line", "Delivery assignment", WAREHOUSE_COLORS[0]))
        if show_current:
            items.append(("ring", "Current site (naive layout)", CURRENT_SITE_COLOR))
        if not result["feasible"]:
            items.append(("dot", "Unserved neighborhood", UNSERVED_COLOR))
        legend(items)


def _comparison(result: dict, baseline: dict) -> None:
    card_header("Current (naive) vs. GRIDPOINT",
                "Both layouts use the same number of warehouses. The naive one puts them in the busiest neighborhoods.")
    b, r = baseline, result
    rows = [
        ["Distance per order", f"{b['avg_km_per_order']:.2f} km", f"{r['avg_km_per_order']:.2f} km",
         delta_chip(b["avg_km_per_order"], r["avg_km_per_order"])],
        ["Avg. delivery time", f"{b['avg_delivery_minutes']:.0f} min", f"{r['avg_delivery_minutes']:.0f} min",
         delta_chip(b["avg_delivery_minutes"], r["avg_delivery_minutes"])],
        ["Transportation cost", f"{inr(b['total_transport_cost'])}/day", f"{inr(r['total_transport_cost'])}/day",
         delta_chip(b["total_transport_cost"], r["total_transport_cost"])],
        ["Infrastructure cost", f"{inr(b['total_infra_cost'])}/month", f"{inr(r['total_infra_cost'])}/month",
         delta_chip(b["total_infra_cost"], r["total_infra_cost"])],
        ["Unserved orders", f"{b['unserved_orders']:,}/day", f"{r['unserved_orders']:,}/day",
         delta_chip(b["unserved_orders"], r["unserved_orders"])],
        ["Total cost (daily equivalent)", inr(b["total_cost"]), inr(r["total_cost"]),
         delta_chip(b["total_cost"], r["total_cost"])],
    ]
    comparison_table(["Measure", "Current (naive)", "GRIDPOINT", "Change"], rows, total_row=len(rows) - 1)
    st.caption("Distance is compared per order so a layout can't look better just by leaving neighborhoods unserved. "
               "All figures are estimates.")


def _why(df, result: dict, cfg: dict) -> None:
    card_header("Why each warehouse is where it is",
                "Warehouses are placed at the demand-weighted centre of the neighborhoods they serve.")
    ids = [w["warehouse_id"] for w in result["warehouses"]]
    choice = st.selectbox("Warehouse", ids, key="res_why", label_visibility="collapsed")
    idx = ids.index(choice)
    w = result["warehouses"][idx]
    served = [a for a in result["assignments"] if a["warehouse"] == idx]
    summary_rows([
        ("Location", f"{w['lat']:.4f}, {w['lon']:.4f}"),
        ("Neighborhoods served", str(len(served))),
        ("Orders per day", f"{w['assigned_orders']:,} of {int(w['capacity']):,} ({w['utilization'] * 100:.0f}%)"),
        ("Farthest neighborhood", f"{max((a['distance_km'] for a in served), default=0):.1f} km"),
    ])
    st.write("")
    st.info(explain_warehouse(w, result["assignments"], result["warehouses"], cfg["max_radius_km"]),
            icon=":material/lightbulb:")


def _assignments(df, result: dict) -> None:
    card_header("Delivery assignments", "Which warehouse serves each neighborhood, and how far and how long it takes.")
    stretch(st.dataframe, assignments_frame(df, result), hide_index=True,
            column_config={"Orders/day": st.column_config.NumberColumn(format="%d"),
                           "Distance (km)": st.column_config.NumberColumn(format="%.1f"),
                           "Est. delivery (min)": st.column_config.NumberColumn(format="%d")})
    mix = ", ".join(f"{n} \u00d7 {v.title()}" for v, n in sorted(result["vehicle_mix"].items()))
    st.caption(f"Daily fleet: {mix}. Vehicle mix is chosen per lane by cost-minimising fleet selection (see README).")


def render() -> None:
    df = get_data()
    stepper("results", {"locations": df is not None, "optimization": has_result()})
    head, action = st.columns([3, 1.2], vertical_alignment="center")
    with head:
        page_header("Results", "The recommended network and how it compares with the obvious layout.",
                    status=STATUS_PILLS[plan_state()])
    with action:
        if has_result():
            run_button("res_run")
    if not require_result("Run the optimization to see recommended warehouse sites, assignments and savings."):
        return

    result, baseline = st.session_state.optimized_result, st.session_state.baseline_result
    cfg = st.session_state.config
    error_banner()
    stale_banner()
    infeasible_banner(result)

    _kpis(result, baseline)
    _map_card(df, result, baseline)

    st.write("")
    with card("detail"):
        t_cmp, t_why, t_asg = st.tabs(["Before vs. after", "Why this location", "Assignments"])
        with t_cmp:
            _comparison(result, baseline)
        with t_why:
            _why(df, result, cfg)
        with t_asg:
            _assignments(df, result)

    st.write("")
    st.markdown("**Next: test the plan**")
    a, b, c, d = st.columns(4)
    with a:
        nav_button("What-if simulator", "what_if", key="res_whatif", icon=":material/science:")
    with b:
        nav_button("Disruption mode", "disruption", key="res_disrupt", icon=":material/warning:")
    with c:
        nav_button("Cost trade-off", "tradeoff", key="res_trade", icon=":material/compare_arrows:")
    with d:
        nav_button("Reports", "reports", key="res_reports", kind="primary", icon=":material/description:")


render()
