"""Optimization (step 2): set the limits, then run."""

import streamlit as st

from ui.components import button, card, card_header, page_header, stepper, summary_rows
from ui.format import inr
from ui.state import DEFAULT_CONFIG, STATUS_PILLS, get_data, has_result, plan_state
from ui.views import error_banner, nav_button, require_data, run_button, stale_banner

PRIORITIES = ["Cost", "Speed", "Sustainability"]
PRIORITY_HELP = [
    "Lowest total cost.",
    "Shortest average delivery time.",
    "Lowest estimated CO\u2082.",
]


def _reset_defaults() -> None:
    st.session_state.config = DEFAULT_CONFIG.copy()
    for key in [k for k in st.session_state if str(k).startswith("cfg_")]:
        del st.session_state[key]
    st.rerun()


def _form(cfg: dict, n_neighborhoods: int, total_orders: int) -> None:
    max_k = min(6, n_neighborhoods)

    with card("size"):
        card_header("Network size", "How many warehouses to build and how much each can handle.")
        if max_k >= 2:
            cfg["num_warehouses"] = st.slider(
                "Number of warehouses", 1, max_k, min(int(cfg["num_warehouses"]), max_k), key="cfg_k",
                help="More warehouses shorten deliveries but add rent. The Cost trade-off page shows the sweet spot.")
        else:
            cfg["num_warehouses"] = 1
            st.caption("With one neighborhood, the network has a single warehouse.")
        cfg["capacity_per_warehouse"] = st.number_input(
            "Capacity per warehouse (orders per day)", min_value=100, step=100,
            value=max(100, int(cfg["capacity_per_warehouse"])), key="cfg_capacity",
            help="The most daily orders one warehouse can handle. This is a hard limit.")
        # Live check: tell them now, not after they run.
        needed = -(-total_orders // int(cfg["capacity_per_warehouse"]))
        if cfg["num_warehouses"] < needed:
            st.warning(
                f"{total_orders:,} orders a day need at least {needed} warehouse{'s' if needed != 1 else ''} "
                f"at this capacity. Add a warehouse or raise capacity.", icon=":material/warning:")

    with card("rules"):
        card_header("Service rules", "How far a warehouse may deliver and what the plan should favour.")
        cfg["max_radius_km"] = st.slider(
            "Longest delivery distance (km)", 1.0, 40.0, float(cfg["max_radius_km"]), step=0.5, key="cfg_radius",
            help="A neighborhood farther than this from every warehouse is reported as unserved.")
        cfg["priority"] = st.radio(
            "Optimize for", PRIORITIES, index=PRIORITIES.index(cfg["priority"]), horizontal=True,
            captions=PRIORITY_HELP, key="cfg_priority",
            help="Used to choose between otherwise similar layouts.")

    with st.expander("Cost assumptions (optional, defaults are set)"):
        cfg["cost_per_warehouse"] = st.number_input(
            "Rent per warehouse (\u20b9 per month)", min_value=0, step=10_000,
            value=int(cfg["cost_per_warehouse"]), key="cfg_rent",
            help="Estimated monthly rent and running cost of one warehouse.")
        cfg["fuel_index"] = st.slider(
            "Fuel price index", 0.5, 2.0, float(cfg["fuel_index"]), step=0.05, key="cfg_fuel",
            help="1.0 is today's baseline price. 1.2 means fuel is 20% more expensive.")

    if button("Reset to defaults", key="cfg_reset", icon=":material/restart_alt:"):
        _reset_defaults()


def _summary(cfg: dict, total_orders: int) -> None:
    capacity = cfg["num_warehouses"] * int(cfg["capacity_per_warehouse"])
    used = total_orders / capacity * 100 if capacity else 0
    with card("summary"):
        card_header("Plan summary", "What you are about to run.")
        summary_rows([
            ("Daily demand", f"{total_orders:,} orders"),
            ("Total capacity", f"{capacity:,} orders"),
            ("Capacity in use", f"{used:.0f}%"),
            ("Warehouses", str(cfg["num_warehouses"])),
            ("Longest delivery", f"{cfg['max_radius_km']:g} km"),
            ("Optimize for", cfg["priority"]),
            ("Rent per warehouse", f"{inr(cfg['cost_per_warehouse'])} / month"),
        ])
        if used > 100:
            st.error("Capacity is below demand, so some neighborhoods will go unserved.", icon=":material/error:")
        elif used > 92:
            st.warning("Capacity is nearly full. Small demand changes could leave neighborhoods unserved.",
                       icon=":material/info:")
        else:
            st.success("Capacity covers demand.", icon=":material/check_circle:")
        st.write("")
        run_button("opt_run")
        if has_result():
            nav_button("View results", "results", key="opt_results",
                       kind="primary" if plan_state() in ("feasible", "infeasible") else "secondary",
                       icon=":material/arrow_forward:")


def render() -> None:
    df = get_data()
    stepper("optimization", {"locations": df is not None, "optimization": has_result()})
    page_header("Optimization", "Set your limits and run. Every field has a sensible default, so change only what matters.",
                status=STATUS_PILLS[plan_state()])
    if not require_data():
        return

    error_banner()
    stale_banner()
    cfg = st.session_state.config
    total_orders = int(df["daily_orders"].sum())

    form_col, summary_col = st.columns([1.6, 1], gap="large")
    with form_col:
        _form(cfg, len(df), total_orders)
    st.session_state.config = cfg
    with summary_col:
        _summary(cfg, total_orders)


render()
