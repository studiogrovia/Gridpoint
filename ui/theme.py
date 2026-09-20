"""
Design tokens and the global stylesheet for GRIDPOINT.

Colour, type and spacing decisions live here so every page looks like the same
product. Streamlit's native widgets are themed through `.streamlit/config.toml`;
this stylesheet only handles what that file cannot express (cards, KPI grids,
the step tracker, legends, skeletons, button states, responsive behaviour).

Selectors deliberately lean on stable hooks (`st-key-*` classes from
`st.container(key=...)`, `data-testid` attributes and our own `gp-*` classes).
If a future Streamlit release renames an internal hook, the affected rule
simply stops matching and the native styling takes over -- nothing breaks.
"""

import streamlit as st

# --- Colour ---------------------------------------------------------------
INK = "#0F2137"          # text, structure, the dark "savings" panel
INK_SOFT = "#4A5B70"     # secondary text (6.9:1 on white)
MUTED = "#5B6B80"        # captions, axis labels (5.4:1 on white)
PAPER = "#F5F7FA"        # page background
CARD = "#FFFFFF"
LINE = "#E2E8F0"
PRIMARY = "#2457D6"      # the one action colour (6.2:1 on white)
PRIMARY_HOVER = "#1B47B5"
PRIMARY_SOFT = "#E8EEFC"
SUCCESS = "#147D4F"
SUCCESS_SOFT = "#E5F5EC"
WARNING = "#9A5B00"
WARNING_SOFT = "#FFF3DC"
DANGER = "#B42318"
DANGER_SOFT = "#FDECEA"

# One colour per warehouse (Okabe-Ito, distinguishable with colour-vision
# deficiency). A neighborhood, its delivery line and its warehouse's
# utilisation bar all share the warehouse's colour.
WAREHOUSE_COLORS = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9"]
TRAFFIC_COLORS = {"Low": "#5B9BD5", "Medium": "#F0A030", "High": "#D0451B"}
UNSERVED_COLOR = "#6B7280"
CURRENT_SITE_COLOR = "#8A97A8"

FONT_STACK = ('"IBM Plex Sans", "Segoe UI", system-ui, -apple-system, Roboto, '
              '"Helvetica Neue", Arial, sans-serif')
PLOTLY_FONT = "IBM Plex Sans, Segoe UI, system-ui, Roboto, Helvetica, Arial, sans-serif"


def warehouse_color(warehouse_id) -> str:
    """Stable colour for a warehouse id such as 'W3' (colour survives a disruption re-plan)."""
    try:
        idx = int(str(warehouse_id).lstrip("Ww")) - 1
    except ValueError:
        idx = 0
    return WAREHOUSE_COLORS[idx % len(WAREHOUSE_COLORS)]


_VARS = f"""
:root {{
  --gp-ink: {INK}; --gp-ink-soft: {INK_SOFT}; --gp-muted: {MUTED};
  --gp-paper: {PAPER}; --gp-card: {CARD}; --gp-line: {LINE};
  --gp-primary: {PRIMARY}; --gp-primary-hover: {PRIMARY_HOVER}; --gp-primary-soft: {PRIMARY_SOFT};
  --gp-success: {SUCCESS}; --gp-success-soft: {SUCCESS_SOFT};
  --gp-warning: {WARNING}; --gp-warning-soft: {WARNING_SOFT};
  --gp-danger: {DANGER}; --gp-danger-soft: {DANGER_SOFT};
  --gp-font: {FONT_STACK};
  --gp-shadow-sm: 0 1px 2px rgba(15,33,55,.05);
  --gp-shadow: 0 1px 2px rgba(15,33,55,.06), 0 6px 20px rgba(15,33,55,.05);
}}
"""

# @import must precede every other rule, or browsers ignore it.
_FONT_IMPORT = '@import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap");'

_CSS = """
/* ---------- Base ---------- */
.stApp { background: var(--gp-paper); color: var(--gp-ink); }
.stApp, .stApp p, .stApp li, .stApp label, .stApp button, .stApp input, .stApp textarea,
.stApp select, .stApp table, [data-testid="stMarkdownContainer"],
[data-testid="stCaptionContainer"], [data-testid="stSidebar"] a { font-family: var(--gp-font); }
.stApp p, .stApp li { line-height: 1.55; }
[data-testid="stCaptionContainer"] { color: var(--gp-muted); line-height: 1.5; }

[data-testid="stMainBlockContainer"], .block-container {
  max-width: 1240px; padding: 3.5rem 2rem 4rem;
}
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"], .block-container { padding: 2.75rem 1rem 3rem; }
}

/* ---------- Page header ---------- */
.gp-head { margin: 0 0 1.25rem; }
.gp-head__row { display: flex; align-items: center; gap: .75rem; flex-wrap: wrap; }
.gp-head .gp-title { font-size: 1.875rem; line-height: 1.2; font-weight: 600;
  letter-spacing: -.015em; color: var(--gp-ink); margin: 0; padding: 0; }
.gp-head .gp-sub { margin: .45rem 0 0; color: var(--gp-muted); font-size: 1rem;
  line-height: 1.55; max-width: 68ch; }
@media (max-width: 640px) { .gp-head .gp-title { font-size: 1.5rem; } }

/* ---------- Status pill ---------- */
.gp-pill { display: inline-flex; align-items: center; gap: .4rem; padding: .2rem .7rem;
  border-radius: 999px; font-size: .8125rem; font-weight: 500; line-height: 1.5;
  white-space: nowrap; background: #EEF2F7; color: var(--gp-ink-soft); }
.gp-pill__dot { width: .5rem; height: .5rem; border-radius: 50%; background: currentColor; }
.gp-pill--success { background: var(--gp-success-soft); color: var(--gp-success); }
.gp-pill--warning { background: var(--gp-warning-soft); color: var(--gp-warning); }
.gp-pill--danger  { background: var(--gp-danger-soft);  color: var(--gp-danger); }
.gp-pill--info    { background: var(--gp-primary-soft); color: var(--gp-primary); }

/* ---------- Step tracker (Locations -> Optimization -> Results) ---------- */
.gp-steps { display: flex; align-items: center; gap: .625rem; margin: 0 0 1.5rem; }
.gp-step { display: flex; align-items: center; gap: .5rem; font-size: .9375rem;
  color: var(--gp-muted); white-space: nowrap; }
.gp-step__dot { width: 1.625rem; height: 1.625rem; border-radius: 50%; display: grid;
  place-items: center; font-size: .8125rem; font-weight: 600; background: #fff;
  border: 1.5px solid #C5CFDD; color: var(--gp-muted); }
.gp-step--done .gp-step__dot { background: var(--gp-success); border-color: var(--gp-success); color: #fff; }
.gp-step--done { color: var(--gp-ink-soft); }
.gp-step--current { color: var(--gp-ink); font-weight: 500; }
.gp-step--current .gp-step__dot { background: var(--gp-primary); border-color: var(--gp-primary); color: #fff; }
.gp-step__bar { flex: 1 1 1rem; min-width: .75rem; height: 2px; border-radius: 2px; background: var(--gp-line); }
.gp-step__bar--done { background: var(--gp-success); }
@media (max-width: 420px) { .gp-step { font-size: .875rem; gap: .35rem; } .gp-steps { gap: .4rem; } }

/* ---------- KPI grid ---------- */
.gp-kpis { display: grid; gap: 1rem; margin: 0 0 1.5rem; }
.gp-kpis--2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.gp-kpis--3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.gp-kpis--4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.gp-kpis--5 { grid-template-columns: repeat(5, minmax(0, 1fr)); }
@media (max-width: 1100px) {
  .gp-kpis--5 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .gp-kpis--4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .gp-kpis--3, .gp-kpis--4, .gp-kpis--5 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .gp-kpis { gap: .75rem; }
}
.gp-kpi { background: var(--gp-card); border: 1px solid var(--gp-line); border-radius: 14px;
  padding: 1rem 1.125rem; min-width: 0; box-shadow: var(--gp-shadow-sm); }
.gp-kpi__label { display: flex; align-items: center; gap: .4rem; font-size: .875rem;
  color: var(--gp-muted); line-height: 1.3; }
.gp-kpi__value { margin-top: .4rem; font-size: 1.75rem; line-height: 1.15; font-weight: 600;
  letter-spacing: -.01em; color: var(--gp-ink); font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere; }
.gp-kpi__sub { margin-top: .35rem; font-size: .8125rem; color: var(--gp-muted); line-height: 1.4; }
.gp-kpi--text .gp-kpi__value { font-size: 1.25rem; line-height: 1.3; }
.gp-kpi--positive .gp-kpi__value { color: var(--gp-success); }
.gp-kpi--negative .gp-kpi__value { color: var(--gp-danger); }
.gp-kpi--hero { grid-column: span 2; background: var(--gp-ink); border-color: var(--gp-ink);
  box-shadow: var(--gp-shadow); padding: 1.25rem 1.375rem; }
.gp-kpi--hero .gp-kpi__label, .gp-kpi--hero .gp-kpi__sub { color: #B9C6D8; }
.gp-kpi--hero .gp-kpi__value { color: #fff; font-size: 2.125rem; }
.gp-kpi--hero.gp-kpi--positive .gp-kpi__value { color: #7FE0B0; }
@media (max-width: 640px) { .gp-kpi--hero { grid-column: 1 / -1; } .gp-kpi__value { font-size: 1.5rem; } }
.gp-kpis--compact .gp-kpi { box-shadow: none; padding: .8rem 1rem; }
.gp-kpis--compact .gp-kpi__value { font-size: 1.25rem; margin-top: .25rem; }

/* ---------- Tooltip (hover on desktop, focus/tap on touch) ----------
   The bubble is anchored to its KPI card (not the icon) and spans the card's
   width, so it can never stick out past the screen edge and cause sideways
   scrolling on phones. */
.gp-kpi { position: relative; }
.gp-tip { display: inline-grid; place-items: center; width: 1rem; height: 1rem;
  border-radius: 50%; border: 1px solid #B4C0D0; color: var(--gp-muted); font-size: .6875rem;
  font-weight: 600; cursor: help; flex: none; }
.gp-tip:hover, .gp-tip:focus-visible { border-color: var(--gp-primary); color: var(--gp-primary); outline: none; }
.gp-tip::after { content: attr(data-tip); position: absolute; left: .625rem; right: .625rem; top: 2.5rem;
  z-index: 20; padding: .55rem .7rem; border-radius: 10px; background: var(--gp-ink); color: #fff;
  font-size: .8125rem; font-weight: 400; line-height: 1.45; text-align: left; box-shadow: var(--gp-shadow);
  visibility: hidden; opacity: 0; pointer-events: none; transform: translateY(-2px);
  transition: opacity .12s ease, transform .12s ease, visibility .12s; }
.gp-tip:hover::after, .gp-tip:focus-visible::after, .gp-tip:focus::after { visibility: visible; opacity: 1; transform: none; }
.gp-kpi--hero .gp-tip { border-color: #6F829B; color: #B9C6D8; }

/* ---------- Cards (st.container(key="gpcard_*")) ---------- */
[class*="st-key-gpcard"] { background: var(--gp-card); border: 1px solid var(--gp-line);
  border-radius: 16px; padding: 1.25rem 1.375rem; box-shadow: var(--gp-shadow); }
@media (max-width: 640px) { [class*="st-key-gpcard"] { padding: 1rem; border-radius: 14px; } }
.gp-card__title { font-size: 1.0625rem; font-weight: 600; line-height: 1.3; color: var(--gp-ink); margin: 0; }
.gp-card__desc { margin: .3rem 0 0; font-size: .875rem; color: var(--gp-muted); line-height: 1.5; max-width: 72ch; }

/* ---------- Savings panel (the one dark element) ---------- */
.gp-hero { background: var(--gp-ink); color: #fff; border-radius: 16px; padding: 1.5rem;
  box-shadow: var(--gp-shadow); }
.gp-hero__label { font-size: .9375rem; color: #B9C6D8; }
.gp-hero__value { margin-top: .4rem; font-size: 2.5rem; font-weight: 600; line-height: 1.1;
  letter-spacing: -.02em; font-variant-numeric: tabular-nums; color: #fff; }
.gp-hero__value--good { color: #7FE0B0; }
.gp-hero__sub { margin-top: .6rem; font-size: .9375rem; color: #B9C6D8; line-height: 1.5; }
@media (max-width: 640px) { .gp-hero__value { font-size: 2rem; } }

/* ---------- Map legend ---------- */
.gp-legend { display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; margin: .75rem 0 0;
  font-size: .875rem; color: var(--gp-ink-soft); }
.gp-legend__item { display: inline-flex; align-items: center; gap: .5rem; line-height: 1.3; }
.gp-sw { display: inline-block; flex: none; }
.gp-sw--dot { width: .75rem; height: .75rem; border-radius: 50%; }
.gp-sw--dots { display: inline-flex; gap: 2px; }
.gp-sw--dots i { width: .625rem; height: .625rem; border-radius: 50%; display: block; }
.gp-sw--hub { width: 1.125rem; height: 1.125rem; border-radius: 50%; background: var(--gp-ink);
  box-shadow: 0 0 0 3px #fff, 0 0 0 4px #C5CFDD; margin: 0 .2rem; }
.gp-sw--ring { width: .9rem; height: .9rem; border-radius: 50%; background: #fff; border: 3px solid var(--gp-ring, #8A97A8); }
.gp-sw--line { width: 1.25rem; height: 3px; border-radius: 2px; background: var(--gp-line-c, #0072B2); opacity: .7; }

/* ---------- Empty state ---------- */
.gp-empty { border: 1.5px dashed #C5CFDD; border-radius: 16px; background: var(--gp-card);
  padding: 2.25rem 1.5rem; text-align: center; margin: 0 0 1rem; }
.gp-empty__title { font-size: 1.1875rem; font-weight: 600; color: var(--gp-ink); line-height: 1.3; }
.gp-empty__body { margin: .5rem auto 0; max-width: 46ch; color: var(--gp-muted); font-size: .9375rem; line-height: 1.55; }

/* ---------- Welcome (first visit) ---------- */
.gp-welcome { background: var(--gp-card); border: 1px solid var(--gp-line); border-radius: 16px;
  padding: 2rem 2rem 1.75rem; box-shadow: var(--gp-shadow); margin: 0 0 1.25rem; }
.gp-welcome__title { font-size: 2rem; line-height: 1.2; font-weight: 600; letter-spacing: -.02em;
  max-width: 24ch; color: var(--gp-ink); }
.gp-welcome__lead { margin: .75rem 0 0; max-width: 60ch; color: var(--gp-ink-soft); font-size: 1.0625rem; line-height: 1.6; }
.gp-how { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; margin: 1.5rem 0 0; }
.gp-how__item { border-top: 2px solid var(--gp-line); padding-top: .85rem; }
.gp-how__n { font-size: .875rem; font-weight: 600; color: var(--gp-primary); }
.gp-how__t { margin-top: .15rem; font-weight: 600; color: var(--gp-ink); }
.gp-how__d { margin-top: .25rem; font-size: .9375rem; color: var(--gp-muted); line-height: 1.5; }
@media (max-width: 760px) { .gp-how { grid-template-columns: 1fr; } .gp-welcome { padding: 1.5rem 1.25rem; }
  .gp-welcome__title { font-size: 1.5rem; } }

/* ---------- Skeletons ---------- */
.gp-skel { border-radius: 12px; min-height: 1rem;
  background: linear-gradient(90deg, #E7ECF3 25%, #F3F6FA 37%, #E7ECF3 63%);
  background-size: 400% 100%; animation: gp-shimmer 1.4s ease infinite; }
@keyframes gp-shimmer { 0% { background-position: 100% 50%; } 100% { background-position: 0 50%; } }

/* ---------- Comparison table ---------- */
.gp-table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.gp-table { width: 100%; border-collapse: collapse; font-size: .9375rem; min-width: 30rem; }
.gp-table th { text-align: right; font-weight: 500; font-size: .875rem; color: var(--gp-muted);
  padding: .55rem .9rem; border-bottom: 1px solid var(--gp-line); white-space: nowrap; }
.gp-table td { text-align: right; padding: .75rem .9rem; border-bottom: 1px solid var(--gp-line);
  font-variant-numeric: tabular-nums; color: var(--gp-ink); white-space: nowrap; }
.gp-table th:first-child, .gp-table td:first-child { text-align: left; white-space: normal; }
.gp-table td:first-child { color: var(--gp-ink-soft); }
.gp-table tr:last-child td { border-bottom: none; }
.gp-table td.gp-strong { font-weight: 600; }
.gp-table tr.gp-total td { font-weight: 600; background: #F8FAFC; }
.gp-delta { display: inline-block; padding: .1rem .55rem; border-radius: 999px; font-size: .8125rem;
  font-weight: 500; background: #EEF2F7; color: var(--gp-ink-soft); }
.gp-delta--good { background: var(--gp-success-soft); color: var(--gp-success); }
.gp-delta--bad  { background: var(--gp-danger-soft);  color: var(--gp-danger); }

/* ---------- Summary rows (Optimization page) ---------- */
.gp-rows { margin: .75rem 0 0; }
.gp-row { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem;
  padding: .55rem 0; border-bottom: 1px solid var(--gp-line); font-size: .9375rem; }
.gp-row:last-child { border-bottom: none; }
.gp-row__k { color: var(--gp-muted); }
.gp-row__v { color: var(--gp-ink); font-weight: 500; font-variant-numeric: tabular-nums; text-align: right; }

/* ---------- Buttons ---------- */
.stButton > button, .stDownloadButton > button, [data-testid^="stBaseButton-"] {
  border-radius: 10px; font-weight: 500; min-height: 2.75rem; padding: .5rem 1.1rem;
  transition: background-color .15s ease, border-color .15s ease, box-shadow .15s ease, color .15s ease; }
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible, [data-testid^="stBaseButton-"]:focus-visible {
  outline: 3px solid rgba(36,87,214,.35); outline-offset: 2px; }
button[kind="primary"], [data-testid="stBaseButton-primary"] { background: var(--gp-primary);
  border: 1px solid var(--gp-primary); color: #fff; box-shadow: 0 1px 2px rgba(36,87,214,.35); }
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  background: var(--gp-primary-hover); border-color: var(--gp-primary-hover); color: #fff; }
button[kind="secondary"], [data-testid="stBaseButton-secondary"] { background: #fff;
  border: 1px solid #CBD5E1; color: var(--gp-ink); }
button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover {
  border-color: var(--gp-primary); color: var(--gp-primary); background: var(--gp-primary-soft); }
.stApp button:disabled, .stApp button[disabled] { opacity: .5; cursor: not-allowed; box-shadow: none; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { border-right: 1px solid var(--gp-line); }
[data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"] { border-radius: 10px; min-height: 2.5rem; }
[data-testid="stSidebarNavLink"][aria-current="page"], [data-testid="stSidebarNav"] a[aria-current="page"] {
  background: var(--gp-primary-soft); color: var(--gp-primary); font-weight: 600; }
.gp-side { margin: .5rem 0 0; padding-top: 1rem; border-top: 1px solid var(--gp-line);
  font-size: .8125rem; color: var(--gp-muted); line-height: 1.5; }
.gp-side__row { display: flex; justify-content: space-between; gap: .5rem; margin: 0 0 .35rem; }
.gp-side__row b { font-weight: 500; color: var(--gp-ink); text-align: right; }
.gp-side__note { margin-top: .75rem; }

/* ---------- Tabs, expanders, alerts, tables ---------- */
[data-baseweb="tab-list"] { gap: .25rem; }
button[data-baseweb="tab"] { font-weight: 500; padding: .6rem .9rem; min-height: 2.75rem; }
[data-testid="stExpander"] details { border-radius: 12px; border: 1px solid var(--gp-line); background: #fff; }
[data-testid="stAlert"] { border-radius: 12px; }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] { border-radius: 12px; overflow: hidden; }
[data-testid="stFileUploader"] section { border-radius: 12px; }

/* ---------- Motion ---------- */
@media (prefers-reduced-motion: reduce) {
  .stApp *, .gp-skel, .gp-tip::after { animation: none !important; transition: none !important; }
}
"""


def inject_theme() -> None:
    """Inject the global stylesheet. Called once per run from app.py."""
    st.markdown(f"<style>{_FONT_IMPORT}{_VARS}{_CSS}</style>", unsafe_allow_html=True)
