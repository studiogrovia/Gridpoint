"""
Session state and workflow status.

The optimizer results in `st.session_state` are only trustworthy for the data
and settings they were computed from. We snapshot both when a run finishes so
every page can tell the user, honestly, when a plan is out of date instead of
showing numbers that no longer match the inputs.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from core.cost_model import DEFAULT_WAREHOUSE_COST, DEFAULT_FUEL_INDEX
from core.optimizer import optimize_network, baseline_network

# Page scripts, keyed by short name. app.py registers these with st.navigation.
PAGES = {
    "dashboard": "pages/dashboard.py",
    "locations": "pages/locations.py",
    "optimization": "pages/optimization.py",
    "results": "pages/results.py",
    "reports": "pages/reports.py",
    "what_if": "pages/what_if.py",
    "disruption": "pages/disruption.py",
    "tradeoff": "pages/tradeoff.py",
}

# Defaults tuned so the bundled demo dataset (~14,770 orders/day across 12
# neighborhoods) is FEASIBLE out of the box with 3 warehouses -- see
# core/optimizer.py's self-test (`python -m core.optimizer`) for the numbers.
DEFAULT_CONFIG = {
    "num_warehouses": 3,
    "capacity_per_warehouse": 5500,
    "max_radius_km": 20.0,
    "cost_per_warehouse": DEFAULT_WAREHOUSE_COST,
    "fuel_index": DEFAULT_FUEL_INDEX,
    "priority": "Cost",
}

# state -> (pill kind, label)
STATUS_PILLS = {
    "empty": ("neutral", "No data loaded"),
    "ready": ("info", "Ready to run"),
    "stale": ("warning", "Out of date"),
    "feasible": ("success", "Feasible plan"),
    "infeasible": ("danger", "Needs attention"),
}


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("config", DEFAULT_CONFIG.copy())
    ss.setdefault("neighborhoods_df", None)
    ss.setdefault("optimized_result", None)
    ss.setdefault("baseline_result", None)
    ss.setdefault("result_meta", None)
    ss.setdefault("run_error", None)
    ss.setdefault("_flash", None)


def show_flash() -> None:
    """
    Show a one-shot toast queued before an st.rerun(). Toasts fired right
    before a rerun get swallowed, so actions queue the message here instead.
    """
    flash = st.session_state.get("_flash")
    if flash:
        st.session_state["_flash"] = None
        kind, message = flash
        icon = ":material/check_circle:" if kind == "success" else ":material/error:"
        st.toast(message, icon=icon)


def flash(kind: str, message: str) -> None:
    st.session_state["_flash"] = (kind, message)


def data_signature(df):
    """A cheap fingerprint of the neighborhood data, used to detect edits."""
    if df is None or len(df) == 0:
        return None
    try:
        return int(pd.util.hash_pandas_object(df, index=True).sum())
    except Exception:
        return (len(df), float(df["daily_orders"].sum()))


def get_data():
    df = st.session_state.get("neighborhoods_df")
    return df if df is not None and len(df) > 0 else None


def plan_state() -> str:
    """One of: empty, ready, stale, feasible, infeasible."""
    ss = st.session_state
    df = get_data()
    if df is None:
        return "empty"
    result, meta = ss.get("optimized_result"), ss.get("result_meta")
    if result is None or meta is None:
        return "ready"
    if meta["data_sig"] != data_signature(df) or meta["config"] != ss.config:
        return "stale"
    return "feasible" if result["feasible"] else "infeasible"


def has_result() -> bool:
    ss = st.session_state
    return ss.get("optimized_result") is not None and ss.get("baseline_result") is not None


def execute_run() -> None:
    """
    Run the optimizer and its naive baseline with the current data/settings,
    store both, then rerun the page so every element reflects the new plan.
    Failures are kept in `run_error` and shown inline (not just as a toast).
    """
    ss = st.session_state
    df, cfg = get_data(), ss.config
    if df is None:
        return
    try:
        with st.spinner("Running optimization\u2026"):
            common = dict(
                num_warehouses=cfg["num_warehouses"],
                capacity_per_warehouse=cfg["capacity_per_warehouse"],
                max_radius_km=cfg["max_radius_km"],
                cost_per_warehouse=cfg["cost_per_warehouse"],
                fuel_index=cfg["fuel_index"],
            )
            result = optimize_network(df, priority=cfg["priority"], **common)
            baseline = baseline_network(df, **common)
    except Exception as exc:  # noqa: BLE001 - surface any failure to the user
        ss.run_error = str(exc) or exc.__class__.__name__
        flash("error", "Optimization failed")
        st.rerun()
        return

    ss.optimized_result = result
    ss.baseline_result = baseline
    ss.result_meta = {
        "data_sig": data_signature(df),
        "config": dict(cfg),
        "ran_at": datetime.now().strftime("%H:%M"),
    }
    ss.run_error = None
    flash("success", "Optimization complete")
    st.rerun()
