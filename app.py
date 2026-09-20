"""
GRIDPOINT entry point.

Owns what is shared by every page: page config, theme, session defaults, the
grouped navigation and the sidebar status. The pages themselves live in pages/.

Run with:  streamlit run app.py
"""

from pathlib import Path

import streamlit as st

from ui.state import PAGES, init_state, show_flash
from ui.theme import inject_theme
from ui.views import sidebar_status

# Must be the first Streamlit *command* (imports above only define things).
st.set_page_config(
    page_title="GRIDPOINT",
    page_icon="\U0001F4E6",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_state()
inject_theme()

logo = Path(__file__).parent / "assets" / "logo.svg"
if logo.exists():
    st.logo(str(logo), size="large")

# The five main steps sit together; the scenario tools are grouped below them.
navigation = st.navigation(
    {
        "Workflow": [
            st.Page(PAGES["dashboard"], title="Dashboard", icon=":material/dashboard:", url_path="dashboard", default=True),
            st.Page(PAGES["locations"], title="Locations", icon=":material/pin_drop:", url_path="locations"),
            st.Page(PAGES["optimization"], title="Optimization", icon=":material/tune:", url_path="optimization"),
            st.Page(PAGES["results"], title="Results", icon=":material/assessment:", url_path="results"),
            st.Page(PAGES["reports"], title="Reports", icon=":material/description:", url_path="reports"),
        ],
        "Scenario tools": [
            st.Page(PAGES["what_if"], title="What-if simulator", icon=":material/science:", url_path="what-if"),
            st.Page(PAGES["disruption"], title="Disruption mode", icon=":material/warning:", url_path="disruption"),
            st.Page(PAGES["tradeoff"], title="Cost trade-off", icon=":material/compare_arrows:", url_path="trade-off"),
        ],
    }
)

show_flash()
navigation.run()
sidebar_status()  # after run() so it reflects anything the page just changed
