"""
Composite pieces used by several pages: navigation buttons, the shared
"Run optimization" control, empty/guard screens, and status banners.
"""

import streamlit as st

from core.data_model import load_demo_data
from .components import button, empty_state, status_pill, _e
from .state import (PAGES, STATUS_PILLS, execute_run, flash, get_data, has_result,
                    plan_state)


def go(page: str) -> None:
    st.switch_page(PAGES[page])


def nav_button(label: str, page: str, *, key: str, kind: str = "secondary",
               icon: str = None, disabled: bool = False, help: str = None) -> None:
    if button(label, key=key, kind=kind, icon=icon, disabled=disabled, help=help):
        go(page)


def status_tuple():
    return STATUS_PILLS[plan_state()]


def run_button(key: str) -> None:
    """
    The single 'Run optimization' control. Primary while there is something to
    run (never run, or inputs changed); secondary once the plan is current.
    Disabled, with a reason, until data is loaded.
    """
    state = plan_state()
    fresh = state in ("feasible", "infeasible")
    label = "Re-run optimization" if fresh else "Run optimization"
    clicked = button(
        label, key=key,
        kind="secondary" if fresh else "primary",
        icon=":material/refresh:" if fresh else ":material/play_arrow:",
        disabled=(state == "empty"),
        help="Load neighborhood data first." if state == "empty" else None,
    )
    if clicked:
        execute_run()


def load_demo_button(key: str, *, kind: str = "secondary") -> None:
    if button("Load demo data", key=key, kind=kind, icon=":material/database:"):
        st.session_state.neighborhoods_df = load_demo_data()
        flash("success", "Demo data loaded")
        st.rerun()


# --- Guard screens ------------------------------------------------------
def require_data() -> bool:
    """Render an empty state and return False when there is no data yet."""
    if get_data() is not None:
        return True
    empty_state(
        "No neighborhoods loaded yet",
        "Add the neighborhoods you deliver to, or start with the sample city to see how GRIDPOINT works.",
    )
    a, b, _ = st.columns([1, 1, 1.4])
    with a:
        load_demo_button("guard_demo", kind="primary")
    with b:
        nav_button("Add your own data", "locations", key="guard_locations", icon=":material/upload_file:")
    return False


def require_result(action_hint: str = "Run the optimization to see recommended warehouse sites.") -> bool:
    """Render an empty state and return False when there is no plan yet."""
    if not require_data():
        return False
    if has_result():
        return True
    empty_state("No plan yet", action_hint)
    a, b, _ = st.columns([1, 1, 1.4])
    with a:
        run_button("guard_run")
    with b:
        nav_button("Adjust settings", "optimization", key="guard_settings", icon=":material/tune:")
    return False


# --- Banners ------------------------------------------------------------
def error_banner() -> None:
    err = st.session_state.get("run_error")
    if err:
        st.error(
            "The optimization could not finish. Check your data and settings, then run it again.",
            icon=":material/error:",
        )
        with st.expander("Technical details"):
            st.code(err)


def stale_banner() -> None:
    """Warn when the visible plan no longer matches the current data or settings."""
    if plan_state() != "stale":
        return
    st.warning(
        "Your data or settings changed after this plan was calculated, so the numbers below "
        "may be out of date. Run the optimization again to refresh them.",
        icon=":material/update:",
    )


def infeasible_banner(result: dict) -> None:
    """Explain an infeasible plan and say how to fix it."""
    if result["feasible"]:
        return
    n = len(result["unserved_ids"])
    st.error(
        f"{n} neighborhood{'s' if n != 1 else ''} can't be served with the current limits "
        f"({result['unserved_orders']:,} orders/day). Add a warehouse, raise capacity, or widen the "
        "service radius on the Optimization page.",
        icon=":material/warning:",
    )


# --- Sidebar --------------------------------------------------------------
def sidebar_status() -> None:
    """Small always-visible summary under the navigation."""
    df = get_data()
    state = plan_state()
    kind, label = STATUS_PILLS[state]
    meta = st.session_state.get("result_meta")
    rows = [
        ("Neighborhoods", f"{len(df):,}" if df is not None else "\u2014"),
        ("Plan", status_pill(kind, label)),
    ]
    if meta and state != "empty":
        rows.append(("Last run", meta["ran_at"]))
    body = "".join(
        f'<div class="gp-side__row"><span>{_e(k)}</span><b>{v if k == "Plan" else _e(v)}</b></div>'
        for k, v in rows
    )
    st.sidebar.markdown(
        f'<div class="gp-side">{body}<div class="gp-side__note">Costs, CO\u2082 and times are '
        f'estimates from adjustable assumptions. Demo data is fictional.</div></div>',
        unsafe_allow_html=True,
    )
