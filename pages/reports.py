"""Reports: charts explaining the plan, plus downloads to share it."""

import streamlit as st

from ui.charts import (CHART_CONFIG, cost_compare_chart, demand_chart, distance_chart,
                       utilization_chart)
from ui.components import card, card_header, kpi_grid, page_header, stretch
from ui.format import inr
from ui.metrics import plan_savings
from ui.state import STATUS_PILLS, plan_state
from ui.tables import assignments_frame, warehouses_frame
from ui.views import error_banner, infeasible_banner, require_result, run_button, stale_banner


def _summary_csv(result: dict, baseline: dict) -> str:
    sv = plan_savings(baseline, result)
    rows = [
        ("Warehouses", result["num_warehouses"]),
        ("Feasible (every neighborhood served)", "Yes" if result["feasible"] else "No"),
        ("Unserved orders per day", result["unserved_orders"]),
        ("Transportation cost (INR/day)", round(result["total_transport_cost"])),
        ("Infrastructure cost (INR/month)", round(result["total_infra_cost"])),
        ("Total cost, daily equivalent (INR)", round(result["total_cost"])),
        ("Naive layout total cost, daily equivalent (INR)", round(baseline["total_cost"])),
        ("Estimated savings (INR/day)", round(sv["daily"])),
        ("Estimated savings (INR/month)", round(sv["monthly"])),
        ("Distance per order (km)", round(result["avg_km_per_order"], 2)),
        ("Average delivery time (min)", round(result["avg_delivery_minutes"], 1)),
        ("Fuel (litres/day)", round(result["total_fuel_litres"], 1)),
        ("CO2 (kg/day)", round(result["total_co2_kg"], 1)),
    ]
    return "measure,value\n" + "\n".join(f'"{k}",{v}' for k, v in rows) + "\n"


def render() -> None:
    head, action = st.columns([3, 1.2], vertical_alignment="center")
    with head:
        page_header("Reports", "Charts that explain the plan, and files you can share.",
                    status=STATUS_PILLS[plan_state()])
    if not require_result("Run the optimization first. Reports are built from the current plan."):
        return
    with action:
        run_button("rep_run")

    df = st.session_state.neighborhoods_df
    result, baseline = st.session_state.optimized_result, st.session_state.baseline_result
    error_banner()
    stale_banner()
    infeasible_banner(result)

    mix = ", ".join(f"{n} \u00d7 {v.title()}" for v, n in sorted(result["vehicle_mix"].items()))
    kpi_grid([
        {"label": "CO\u2082 per day", "value": f"{result['total_co2_kg']:,.0f} kg",
         "help": "From per-vehicle emission factors documented in the README. Estimate only."},
        {"label": "Fuel per day", "value": f"{result['total_fuel_litres']:,.0f} L"},
        {"label": "Daily fleet", "value": mix or "\u2014", "text": True},
        {"label": "Total cost per day", "value": inr(result["total_cost"]),
         "sub": "Transport + rent, daily equivalent"},
    ], cols=4, compact=True)

    left, right = st.columns(2, gap="large")
    with left:
        with card("demand"):
            card_header("Demand by neighborhood", "Orders per day, highest first.")
            stretch(st.plotly_chart, demand_chart(df), config=CHART_CONFIG, theme=None, key="rep_demand")
    with right:
        with card("util"):
            card_header("Warehouse utilization", "Share of each warehouse's capacity in use. The dotted line is 100%.")
            stretch(st.plotly_chart, utilization_chart(result), config=CHART_CONFIG, theme=None, key="rep_util")

    st.write("")
    left, right = st.columns(2, gap="large")
    with left:
        with card("dist"):
            card_header("Delivery distance", "Road distance from each neighborhood to its warehouse.")
            if any(a["distance_km"] is not None for a in result["assignments"]):
                stretch(st.plotly_chart, distance_chart(result), config=CHART_CONFIG, theme=None, key="rep_dist")
            else:
                st.info("No neighborhoods are served yet, so there are no distances to chart.")
    with right:
        with card("cost"):
            card_header("Total cost per day", "Current (naive) layout vs. GRIDPOINT, as a daily equivalent.")
            stretch(st.plotly_chart, cost_compare_chart(baseline, result), config=CHART_CONFIG,
                    theme=None, key="rep_cost")

    st.write("")
    with card("downloads"):
        card_header("Download", "CSV files open in Excel or Google Sheets. All figures are estimates.")
        a, b, c = st.columns(3)
        downloads = [
            (a, "Assignments (CSV)", assignments_frame(df, result).to_csv(index=False), "gridpoint_assignments.csv", "dl_asg"),
            (b, "Warehouses (CSV)", warehouses_frame(result).to_csv(index=False), "gridpoint_warehouses.csv", "dl_wh"),
            (c, "Summary (CSV)", _summary_csv(result, baseline), "gridpoint_summary.csv", "dl_sum"),
        ]
        for col, label, data, name, key in downloads:
            with col:
                stretch(st.download_button, label, data=data, file_name=name, mime="text/csv",
                        icon=":material/download:", key=key)


render()
